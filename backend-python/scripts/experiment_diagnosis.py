"""
诊断实验：定位「中文提问 → 法文资料」命中率低在哪一环。

首测（`docs/eval-report.md`）只测了 chunk_size，结论停在"跨语言语义对齐不足"。
本脚本把三个可疑变量**隔离**成可对照的条件（同一语料、同一 chunk_size、同一判定口径）：

  1. 语料污染：PyMuPDF 从这批 PDF 提取文本时把法语重音拆成「符号 + 基字母」
     （`général` → `g´en´eral`、`à` → `` `a ``、`reconnaître` → `reconnaˆıtre`）。
     条件：`raw`（PyMuPDF 原样提取）vs `repaired`（对 raw 调用**生产实现**
     `app.utils.text_utils.repair_broken_accents`）—— 复用生产实现，使诊断与线上同源。
  2. 检索度量：生产链路用 vec0 的 L2 距离，而实测向量**未归一化**
     （法文 chunk ‖v‖≈3.1、中文 query ‖v‖≈5.2）→ 距离混入范数项。
     条件：`L2`（现状，vec0 KNN）vs `cos`（自算余弦，同一索引不重建）。
  3. 查询语言：中文 query（现状）vs 法语 query（**同语言上界基线**）。
     若同语言也低，说明瓶颈不在"跨语言"，而在检索管线本身。

指标：HitRate@1/3/5/10/20、MRR、期望片段的最佳排名。排名分布用来区分
"排序信号弱"（命中片段排在第 6~20 名，放宽 k 即可救）与"真的召不到"（排名数百）。

本脚本只做诊断，**不改动生产链路**。用法（在 backend-python 目录下）：

    python scripts/experiment_diagnosis.py --docs-dir "D:/桌面/测试文件"
"""
import argparse
import json
import shutil
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # noqa: E402  # PyMuPDF：诊断需要「未修复」的原始提取
import numpy as np  # noqa: E402
from fastembed import TextEmbedding  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config.settings import EMBEDDING_DIMENSION, EMBEDDING_MODEL  # noqa: E402
from app.db.init_db import initialize_database, load_sqlite_vec_extension  # noqa: E402
from app.db.models import ChunkModel, EmbeddingVectorModel  # noqa: E402
from app.db.orm import create_database_engine, create_session_factory  # noqa: E402
from app.entities import Chunk, DocumentRecord, DocumentUnit  # noqa: E402
from app.enums import DocumentFileType  # noqa: E402
from app.parsers.pdf_parser import PDFParser  # noqa: E402
from app.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.repositories.document_repository import DocumentRepository  # noqa: E402
from app.repositories.document_unit_repository import DocumentUnitRepository  # noqa: E402
from app.repositories.embedding_repository import EmbeddingRepository  # noqa: E402
from app.services.chunk_service import ChunkService  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.utils.text_utils import repair_broken_accents  # noqa: E402
from app.rag.vector_index_builder import VectorIndexBuilder  # noqa: E402


# HitRate 曲线的 k 值
KS = (1, 3, 5, 10, 20)
# 排名诊断的检索深度
DEPTH = 50
# 模型的序列上限：超过它的片段会被 tokenizer 截断
MODEL_MAX_TOKENS = 128

# 中文提问 / 法语提问 → 期望命中的法文关键词（两套 query 一一对应，判定口径相同）
QUERIES_ZH: list[tuple[str, str]] = [
    ("什么是监督学习？", "apprentissage supervis"),
    ("k 近邻算法是怎么工作的？", "plus proches voisins"),
    ("决策树是怎么做分类的？", "arbre de décision"),
    ("随机森林是什么？", "forêts aléatoires"),
    ("如何评估一个机器学习模型的好坏？", "évaluation"),
    ("怎么让计算机自动从数据里学习规律？", "machine learning"),
    ("树搜索算法的基本原理是什么？", "recherche arborescente"),
    ("什么是可满足性问题？", "satisfi"),
    ("约束满足问题怎么求解？", "contraintes"),
    ("人工智能包含哪些子领域？", "sous-domaines"),
    ("课程整体会讲哪些内容？", "contenu"),
    ("分类和回归有什么区别？", "classification"),
]

QUERIES_FR: list[tuple[str, str]] = [
    ("Qu'est-ce que l'apprentissage supervisé ?", "apprentissage supervis"),
    ("Comment fonctionne l'algorithme des plus proches voisins ?", "plus proches voisins"),
    ("Comment un arbre de décision réalise-t-il une classification ?", "arbre de décision"),
    ("Qu'est-ce qu'une forêt aléatoire ?", "forêts aléatoires"),
    ("Comment évaluer la qualité d'un modèle d'apprentissage ?", "évaluation"),
    ("Comment faire apprendre automatiquement des régularités à partir de données ?", "machine learning"),
    ("Quel est le principe de la recherche arborescente ?", "recherche arborescente"),
    ("Qu'est-ce qu'un problème de satisfiabilité ?", "satisfi"),
    ("Comment résoudre un problème de satisfaction de contraintes ?", "contraintes"),
    ("Quels sont les sous-domaines de l'intelligence artificielle ?", "sous-domaines"),
    ("Quel est le contenu général du cours ?", "contenu"),
    ("Quelle est la différence entre classification et régression ?", "classification"),
]

def fold(text: str) -> str:
    """宽松归一化，用于关键词匹配（与 experiment_chunk_size.py 保持同一口径）。"""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for symbol in "`´^~¸¨":
        text = text.replace(symbol, "")
    return " ".join(text.split()).lower()


def _truncation_max_length(truncation) -> int | None:
    """`Tokenizer.truncation` 在不同 tokenizers 版本里可能是 dict 或 TruncationParams。"""
    if truncation is None:
        return None
    if isinstance(truncation, dict):
        return truncation.get("max_length")
    return getattr(truncation, "max_length", None)


def token_lengths(tokenizer, texts: list[str]) -> list[int]:
    """统计文本的 token 数；**必须关掉 tokenizer 自带的截断**，否则测出的永远是 ≤ 上限。"""
    original = _truncation_max_length(tokenizer.truncation)
    try:
        tokenizer.enable_truncation(max_length=1_000_000)
        return [len(tokenizer.encode(text).ids) for text in texts]
    finally:
        if original is not None:
            tokenizer.enable_truncation(original)


def parse_documents(docs_dir: Path) -> list[tuple[str, list[dict]]]:
    """用 PyMuPDF **原样**提取页面文本，作为「未修复污染」的对照基线。

    生产 `PDFParser` 自 1.1.0 起已在解析阶段还原重音，所以这里直接调 PyMuPDF
    （等价于修复前的解析行为）；`repaired` 条件再对这批文本调用生产实现。
    """
    documents = []
    for pdf_path in sorted(docs_dir.glob("*.pdf")):
        pages = []
        with fitz.open(stream=pdf_path.read_bytes(), filetype="pdf") as document:
            for page_num in range(len(document)):
                text = document.load_page(page_num).get_text("text").strip()
                pages.append(
                    {
                        "page_number": page_num + 1,
                        "content": text,
                        "metadata": {"source_type": "pdf", "headings": []},
                    }
                )
        documents.append((pdf_path.name, pages))
        print(f"  解析 {pdf_path.name}：{len(pages)} 页")
    return documents


def verify_production_parser(
    docs_dir: Path,
    documents: list[tuple[str, list[dict]]],
) -> str:
    """确认生产 `PDFParser` 的输出 == 对 raw 文本调用 `repair_broken_accents` 的结果。

    这是"修复真的接进了生产链路"的校验：只要两者一致，本脚本测出的 `repaired`
    条件就是线上实际行为。
    """
    parser = PDFParser()
    checked_pages = 0
    for pdf_path, (_, raw_pages) in zip(sorted(docs_dir.glob("*.pdf")), documents):
        parsed_pages = parser.parse(pdf_path.read_bytes())
        if len(parsed_pages) != len(raw_pages):
            return f"❌ 页数不一致：{pdf_path.name}"
        for raw_page, parsed_page in zip(raw_pages, parsed_pages):
            expected = repair_broken_accents(raw_page["content"])[0]
            if parsed_page["content"] != expected:
                return f"❌ {pdf_path.name} 第 {raw_page['page_number']} 页：生产解析结果与修复函数不一致"
            if parsed_page["parser_version"] != "1.1.0":
                return f"❌ {pdf_path.name}：parser_version 不是 1.1.0"
            checked_pages += 1
    return f"✅ 生产 PDFParser 与 repair_broken_accents 完全一致（已比对 {checked_pages} 页）"


def with_text(chunk: Chunk, text: str) -> Chunk:
    """用替换后的文本重建 Chunk（保持 id / 溯源字段不变）。"""
    return chunk.model_copy(update={"text_content": text})


@dataclass
class Index:
    variant: str
    chunk_count: int
    session_factory: object
    engine: object


def build_index(
    documents: list[tuple[str, list[dict]]],
    *,
    chunk_size: int,
    variant: str,
    workdir: Path,
    embedding_service: EmbeddingService,
) -> Index:
    """按 variant 处理语料文本，切块、嵌入并写入临时库。"""
    result = initialize_database(
        data_dir=workdir / variant,
        database_name="diagnosis.sqlite3",
        embedding_dimension=EMBEDDING_DIMENSION,
    )
    engine = create_database_engine(
        result.database_path, sqlite_vec_loader=load_sqlite_vec_extension
    )
    session_factory = create_session_factory(engine)
    chunk_service = ChunkService(chunk_size=chunk_size, chunk_overlap=max(1, chunk_size // 8))
    builder = VectorIndexBuilder(embedding_service, embedding_model=EMBEDDING_MODEL)

    total = 0
    with session_factory() as session:  # type: ignore[operator]
        for filename, pages in documents:
            record = DocumentRecord(
                workspace_id="diagnosis",
                title=filename,
                original_filename=filename,
                file_type=DocumentFileType.PDF,
                file_path=filename,
                page_count=len(pages),
            )
            DocumentRepository(session).save(record)

            unit_repository = DocumentUnitRepository(session)
            units = []
            for index, page in enumerate(pages):
                unit = DocumentUnit(
                    document_id=record.id,
                    sequence_index=index,
                    text_content=page.get("content", ""),
                    page_number=page.get("page_number"),
                    metadata_json=page.get("metadata"),
                )
                unit_repository.save(unit)
                units.append(unit)

            chunks = chunk_service.split_units(units)
            if variant == "repaired":
                chunks = [with_text(chunk, repair_broken_accents(chunk.text_content)[0]) for chunk in chunks]
            ChunkRepository(session).save_batch(chunks)

            repository = EmbeddingRepository(session, embedding_dimension=EMBEDDING_DIMENSION)
            total += builder.build_for_chunks(repository, chunks)
        session.commit()

    return Index(variant=variant, chunk_count=total, session_factory=session_factory, engine=engine)


def load_vectors(session) -> tuple[list[str], np.ndarray]:
    """从权威表读出全部向量（用于自算 cosine 与范数诊断）。"""
    rows = session.execute(
        select(EmbeddingVectorModel.chunk_id, EmbeddingVectorModel.vector_json)
    ).all()
    ids = [row[0] for row in rows]
    matrix = np.array([json.loads(row[1]) for row in rows], dtype=np.float64)
    return ids, matrix


def rank_of(expected_ids: set[str], ordered_ids: list[str]) -> int | None:
    for position, chunk_id in enumerate(ordered_ids, start=1):
        if chunk_id in expected_ids:
            return position
    return None


@dataclass
class Condition:
    variant: str
    metric: str
    language: str
    hits_at: dict[int, int]
    decided: int
    mrr: float
    ranks: list[int | None]
    expected_sizes: list[int] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.variant}/{self.metric}/{self.language}"

    def hit_rate(self, k: int) -> float:
        return self.hits_at[k] / self.decided if self.decided else 0.0


def evaluate_condition(
    *,
    variant: str,
    metric: str,
    language: str,
    queries: list[tuple[str, str]],
    embedding_service: EmbeddingService,
    repository: EmbeddingRepository,
    chunk_text: dict[str, str],
    ids: list[str],
    normalized: np.ndarray,
) -> Condition:
    hits_at = {k: 0 for k in KS}
    decided = 0
    mrr_total = 0.0
    ranks: list[int | None] = []
    expected_sizes: list[int] = []

    for query, keyword in queries:
        expected_ids = {
            chunk_id for chunk_id, text in chunk_text.items() if fold(keyword) in text
        }
        if not expected_ids:
            ranks.append(None)
            continue
        decided += 1
        expected_sizes.append(len(expected_ids))

        query_vector = np.array(embedding_service.embed_query(query), dtype=np.float64)
        if metric == "L2":
            # 与生产链路一致：vec0 的 KNN，按距离升序
            hits = repository.search_similar(list(query_vector), top_k=DEPTH)
            ordered = [chunk_id for chunk_id, _ in hits]
        elif metric == "cos":
            scores = normalized @ (query_vector / np.linalg.norm(query_vector))
            ordered = [ids[i] for i in np.argsort(-scores)[:DEPTH]]
        else:
            raise ValueError(f"未知度量：{metric}")

        rank = rank_of(expected_ids, ordered)
        ranks.append(rank)
        if rank is not None:
            mrr_total += 1.0 / rank
            for k in KS:
                if rank <= k:
                    hits_at[k] += 1

    return Condition(
        variant=variant,
        metric=metric,
        language=language,
        hits_at=hits_at,
        decided=decided,
        mrr=mrr_total / decided if decided else 0.0,
        ranks=ranks,
        expected_sizes=expected_sizes,
    )


def describe_vec0_distance(
    repository: EmbeddingRepository,
    matrix: np.ndarray,
    ids: list[str],
    query_vector: np.ndarray,
) -> str:
    """确认 vec0 返回的距离是平方 L2 还是非平方 L2 —— 阈值语义依赖这一口径。"""
    hits = repository.search_similar(list(query_vector), top_k=3)
    if not hits:
        return "vec0 未返回结果"
    squared = ((matrix - query_vector) ** 2).sum(axis=1)
    by_id = {chunk_id: float(squared[i]) for i, chunk_id in enumerate(ids)}
    diff_squared = max(abs(by_id[chunk_id] - distance) for chunk_id, distance in hits)
    diff_plain = max(abs(by_id[chunk_id] ** 0.5 - distance) for chunk_id, distance in hits)
    verdict = "平方 L2" if diff_squared <= diff_plain else "**非平方 L2（欧氏距离）**"
    return (
        f"vec0 距离 vs 自算平方 L2 偏差 {diff_squared:.6f}，vs 自算欧氏距离偏差 {diff_plain:.6f}"
        f" → vec0 返回的是 {verdict}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="跨语言检索命中率低——根因诊断实验")
    parser.add_argument("--docs-dir", required=True, help="包含法语课程 PDF 的目录")
    parser.add_argument("--chunk-size", type=int, default=500, help="切块大小（字符），默认 500")
    parser.add_argument(
        "--cache-dir",
        default=str(Path.home() / ".cache" / "fastembed"),
        help="fastembed 模型缓存目录",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        raise SystemExit(f"目录不存在：{docs_dir}")

    print(f"模型：{EMBEDDING_MODEL}（{EMBEDDING_DIMENSION} 维，序列上限 {MODEL_MAX_TOKENS} token）")
    print(f"资料目录：{docs_dir}")

    print("\n解析文档（PyMuPDF 原样提取＝未修复基线）……")
    documents = parse_documents(docs_dir)

    print("\n校验修复已接入生产链路……")
    print("  " + verify_production_parser(docs_dir, documents))

    print("\n统计语料污染与 token 长度……")
    repaired_count = 0
    for _, pages in documents:
        for page in pages:
            text = page.get("content", "")
            if text.strip():
                repaired_count += repair_broken_accents(text)[1]

    chunk_service = ChunkService(
        chunk_size=args.chunk_size, chunk_overlap=max(1, args.chunk_size // 8)
    )
    raw_texts: list[str] = []
    for _, pages in documents:
        for page in pages:
            text = page.get("content", "")
            if text.strip():
                for start, end in chunk_service._split_spans(text):
                    raw_texts.append(text[start:end])
    print(f"  语料字符数：{sum(len(t) for t in raw_texts)}（{len(raw_texts)} 个 chunk）")
    print(f"  重音拆裂修复处数：{repaired_count}（按页面文本统计，不含 chunk overlap 重复）")

    embedding_service = EmbeddingService(
        model_factory=lambda name: TextEmbedding(name, cache_dir=args.cache_dir)
    )
    embedding_service.embed_texts(["warmup"])  # 触发模型加载，让后续耗时只计推理
    tokenizer = embedding_service._get_model().model.tokenizer  # type: ignore[attr-defined]

    token_counts = {
        "raw": token_lengths(tokenizer, raw_texts),
        "repaired": token_lengths(tokenizer, [repair_broken_accents(text)[0] for text in raw_texts]),
    }

    workdir = Path(tempfile.mkdtemp(prefix="gb-diagnosis-"))
    conditions: list[Condition] = []
    norms: dict[str, tuple[float, float]] = {}
    vec0_check = ""
    try:
        for variant in ("raw", "repaired"):
            print(f"\n构建索引：{variant}……")
            index = build_index(
                documents,
                chunk_size=args.chunk_size,
                variant=variant,
                workdir=workdir,
                embedding_service=embedding_service,
            )
            tokens = token_counts[variant]
            print(
                f"  {index.chunk_count} 个片段已入库"
                f"（token p50={int(np.percentile(tokens, 50))} "
                f"p90={int(np.percentile(tokens, 90))} max={max(tokens)}）"
            )

            with index.session_factory() as session:  # type: ignore[operator]
                repository = EmbeddingRepository(session, embedding_dimension=EMBEDDING_DIMENSION)
                ids, matrix = load_vectors(session)
                chunk_rows = session.execute(
                    select(ChunkModel.id, ChunkModel.text_content)
                ).all()
                chunk_text = {row[0]: fold(row[1]) for row in chunk_rows}

                norms_vector = np.linalg.norm(matrix, axis=1)
                norms[variant] = (
                    float(np.percentile(norms_vector, 50)),
                    float(np.percentile(norms_vector, 90)),
                )
                normalized = matrix / norms_vector[:, None]

                if not vec0_check:
                    probe_vector = np.array(
                        embedding_service.embed_query(QUERIES_ZH[0][0]), dtype=np.float64
                    )
                    vec0_check = describe_vec0_distance(repository, matrix, ids, probe_vector)

                for language, queries in (("zh", QUERIES_ZH), ("fr", QUERIES_FR)):
                    for metric in ("L2", "cos"):
                        condition = evaluate_condition(
                            variant=variant,
                            metric=metric,
                            language=language,
                            queries=queries,
                            embedding_service=embedding_service,
                            repository=repository,
                            chunk_text=chunk_text,
                            ids=ids,
                            normalized=normalized,
                        )
                        conditions.append(condition)
                        print(
                            f"  {condition.label}: "
                            + " ".join(f"@{k}={condition.hit_rate(k):.0%}" for k in KS)
                            + f" MRR={condition.mrr:.3f}"
                        )
            index.engine.dispose()  # type: ignore[attr-defined]
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    # ---- 报告 ----
    print("\n" + "=" * 100)
    print("诊断结果")
    print("=" * 100)
    print(f"\nchunk_size={args.chunk_size}，检索深度={DEPTH}，判定口径=关键词包含（空白折叠）")
    print("\n语料 token 长度（**已关闭 tokenizer 自带的截断**，按 chunk 统计）：")
    for variant, tokens in token_counts.items():
        over = sum(1 for n in tokens if n > MODEL_MAX_TOKENS)
        print(
            f"  {variant:<9}: p50={int(np.percentile(tokens, 50))} "
            f"p90={int(np.percentile(tokens, 90))} max={max(tokens)}，"
            f"超过 {MODEL_MAX_TOKENS} token（会被截断）的片段 {over}/{len(tokens)}"
            f"（{over / len(tokens):.1%}）"
        )
    print(
        f"\n向量范数 p50/p90：raw {norms['raw'][0]:.2f}/{norms['raw'][1]:.2f}，"
        f"repaired {norms['repaired'][0]:.2f}/{norms['repaired'][1]:.2f}"
        f"\n{vec0_check}"
    )
    expected_all = [size for condition in conditions for size in condition.expected_sizes]
    print(
        f"\n判定口径松紧：期望片段集合大小 p50={int(np.median(expected_all))} "
        f"min={min(expected_all)} max={max(expected_all)}（集合越大越容易命中）"
    )

    header = (
        f"{'条件':<22}"
        + "".join(f"{'@' + str(k):>8}" for k in KS)
        + f"{'MRR':>9}{'中位排名':>10}{'最深排名':>10}"
    )
    print("\n" + header)
    print("-" * len(header))
    for condition in conditions:
        found = sorted(rank for rank in condition.ranks if rank is not None)
        print(
            f"{condition.label:<22}"
            + "".join(f"{condition.hit_rate(k):>7.1%} " for k in KS)
            + f"{condition.mrr:>8.3f}"
            f"{int(np.median(found)) if found else 0:>10}"
            f"{max(found) if found else 0:>10}"
        )

    print(f"\n逐条明细（排名 = 期望片段在 top-{DEPTH}（cos 为全量）里的最佳位置，N = 未召回到）：")
    for condition in conditions:
        detail = " ".join("N" if rank is None else str(rank) for rank in condition.ranks)
        print(f"  {condition.label:<22}{detail}")


if __name__ == "__main__":
    main()
