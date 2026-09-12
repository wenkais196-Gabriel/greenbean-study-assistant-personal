"""
阶段 1 收尾实验：chunk_size 对「中文提问 → 法文资料」检索命中率的影响。

回答 planning/STATUS.md §五 的两条假设：
  #1 中文 query 能否检索到法文 chunk（跨语言语义检索是否真的有效）
  #7 chunk_size 该取多少（模型最大序列 128 tokens ≈ 法语 512 字符，而默认是 800 字符）

用法（在 backend-python 目录下）：
    python scripts/experiment_chunk_size.py --docs-dir "D:/桌面/测试文件"
    python scripts/experiment_chunk_size.py --docs-dir ... --sizes 300,500,800 --top-k 5

口径说明（重要）：
  - 「命中率」= 命中 / **可判定样本**（有期望来源的 query）；
  - 关键词在提取文本里找不到的 query 记为**无法判定**，不计入分母 ——
    否则会把"评测本身没构造好"误算成"检索失败"。
  - Window 上若临时库文件被占用，清理会跳过，不影响结果。

注意：首次运行会下载 embedding 模型（约 0.22 GB），之后走本地缓存。
"""
import argparse
import shutil
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config.settings import EMBEDDING_DIMENSION, EMBEDDING_MODEL  # noqa: E402
from app.db.init_db import initialize_database, load_sqlite_vec_extension  # noqa: E402
from app.db.models import ChunkModel  # noqa: E402
from app.db.orm import create_database_engine, create_session_factory  # noqa: E402
from app.entities import Chunk, DocumentRecord, DocumentUnit  # noqa: E402
from app.enums import DocumentFileType  # noqa: E402
from app.parsers.pdf_parser import PDFParser  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.rag.vector_index_builder import VectorIndexBuilder  # noqa: E402
from app.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.repositories.document_repository import DocumentRepository  # noqa: E402
from app.repositories.document_unit_repository import DocumentUnitRepository  # noqa: E402
from app.repositories.embedding_repository import EmbeddingRepository  # noqa: E402
from app.services.chunk_service import ChunkService  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402


# 中文提问 → 期望命中的法文关键词（用于自动判定"哪些 chunk 是正确答案"）
QUERIES: list[tuple[str, str]] = [
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


def fold(text: str) -> str:
    """宽松归一化，用于关键词匹配。

    要处理两种 PDF 提取带来的失真：
      1. 重音被拆成独立符号（`à` → `` `a ``、`général` → `g´en´eral`）；
      2. 幻灯片标题被换行切开（`Recherche\\nArborescente`）。
    """
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for symbol in "`´^~¸¨":
        text = text.replace(symbol, "")
    return " ".join(text.split()).lower()


@dataclass
class ExperimentResult:
    chunk_size: int
    chunk_count: int
    hits: int
    decided: int
    undecidable: int
    per_query: list[tuple[str, bool | None, float | None]]

    @property
    def hit_rate(self) -> float:
        return self.hits / self.decided if self.decided else 0.0


def load_documents(docs_dir: Path) -> list[tuple[str, list[dict]]]:
    """解析目录下的全部 PDF，返回 [(文件名, PageIndex 列表)]。"""
    parser = PDFParser()
    documents = []
    for pdf_path in sorted(docs_dir.glob("*.pdf")):
        pages = parser.parse(pdf_path.read_bytes())
        documents.append((pdf_path.name, pages))
        print(f"  解析 {pdf_path.name}：{len(pages)} 页")
    return documents


def build_index(
    documents: list[tuple[str, list[dict]]],
    chunk_size: int,
    workdir: Path,
    embedding_service: EmbeddingService,
) -> tuple[int, object, object]:
    """把文档切块、嵌入并写入临时数据库；返回 (片段总数, session_factory, engine)。"""
    result = initialize_database(
        data_dir=workdir / f"size-{chunk_size}",
        database_name="experiment.sqlite3",
        embedding_dimension=EMBEDDING_DIMENSION,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    session_factory = create_session_factory(engine)
    chunk_service = ChunkService(
        chunk_size=chunk_size,
        chunk_overlap=max(1, chunk_size // 8),
    )
    builder = VectorIndexBuilder(embedding_service, embedding_model=EMBEDDING_MODEL)

    chunk_total = 0
    for filename, pages in documents:
        with session_factory() as session:
            record = DocumentRecord(
                workspace_id="experiment",
                title=filename,
                original_filename=filename,
                file_type=DocumentFileType.PDF,
                file_path=filename,
                page_count=len(pages),
            )
            DocumentRepository(session).save(record)

            unit_repository = DocumentUnitRepository(session)
            units = [
                DocumentUnit(
                    document_id=record.id,
                    sequence_index=index,
                    text_content=page.get("content", ""),
                    page_number=page.get("page_number"),
                    metadata_json=page.get("metadata"),
                )
                for index, page in enumerate(pages)
            ]
            for unit in units:
                unit_repository.save(unit)

            chunks: list[Chunk] = chunk_service.split_units(units)
            ChunkRepository(session).save_batch(chunks)

            repository = EmbeddingRepository(session, embedding_dimension=EMBEDDING_DIMENSION)
            builder.build_for_chunks(repository, chunks)
            session.commit()
            chunk_total += len(chunks)

    print(f"  chunk_size={chunk_size}：{chunk_total} 个片段已入库")
    return chunk_total, session_factory, engine


def evaluate(
    session: Session,
    chunk_size: int,
    chunk_count: int,
    top_k: int,
    embedding_service: EmbeddingService,
) -> ExperimentResult:
    """对全部中文 query 跑检索，判定期望来源是否落在 top-k 内。"""
    rows = session.execute(select(ChunkModel.id, ChunkModel.text_content)).all()
    folded = {row[0]: fold(row[1]) for row in rows}

    repository = EmbeddingRepository(session, embedding_dimension=EMBEDDING_DIMENSION)
    retriever = Retriever(embedding_service, top_k=top_k)

    per_query: list[tuple[str, bool | None, float | None]] = []
    hits = 0
    decided = 0
    undecidable = 0
    for query, keyword in QUERIES:
        expected_ids = {
            chunk_id for chunk_id, text in folded.items() if fold(keyword) in text
        }
        if not expected_ids:
            undecidable += 1
            per_query.append((query, None, None))
            continue

        decided += 1
        retrieved = retriever.retrieve(repository, query)
        matched = [hit for hit in retrieved if hit.chunk_id in expected_ids]
        found = bool(matched)
        hits += int(found)
        per_query.append((query, found, matched[0].distance if matched else None))

    return ExperimentResult(
        chunk_size=chunk_size,
        chunk_count=chunk_count,
        hits=hits,
        decided=decided,
        undecidable=undecidable,
        per_query=per_query,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="chunk_size × 跨语言检索命中率实验")
    parser.add_argument("--docs-dir", required=True, help="包含法语课程 PDF 的目录")
    parser.add_argument("--sizes", default="300,500,800", help="逗号分隔的 chunk_size 列表")
    parser.add_argument("--top-k", type=int, default=5, help="检索 top-k（默认 5）")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        raise SystemExit(f"目录不存在：{docs_dir}")

    sizes = [int(value) for value in args.sizes.split(",")]
    print(f"模型：{EMBEDDING_MODEL}（{EMBEDDING_DIMENSION} 维）")
    print(f"资料目录：{docs_dir}")

    print("解析文档……")
    documents = load_documents(docs_dir)

    # 复用同一个 service，避免每个 chunk_size 都重新加载模型
    embedding_service = EmbeddingService()

    results: list[ExperimentResult] = []
    workdir = Path(tempfile.mkdtemp(prefix="gb-experiment-"))
    try:
        for size in sizes:
            print(f"\n构建 chunk_size={size} 的索引……")
            chunk_total, session_factory, engine = build_index(
                documents, size, workdir, embedding_service
            )
            with session_factory() as session:
                result = evaluate(session, size, chunk_total, args.top_k, embedding_service)
            engine.dispose()
            results.append(result)
            print(
                f"  HitRate@{args.top_k} = {result.hit_rate:.1%}"
                f"（{result.hits}/{result.decided} 可判定，另 {result.undecidable} 条无法判定）"
            )
    finally:
        # Windows 上 sqlite 文件可能仍被占用，清理失败不影响实验结果
        shutil.rmtree(workdir, ignore_errors=True)

    print("\n" + "=" * 78)
    print(f"结论：HitRate@{args.top_k}（中文提问 → 法文资料，仅计可判定样本）")
    print("=" * 78)
    print(f"{'chunk_size':>12} {'片段数':>10} {'命中':>6} {'可判定':>8} {'命中率':>8} {'无法判定':>10}")
    for result in results:
        print(
            f"{result.chunk_size:>12} {result.chunk_count:>10} "
            f"{result.hits:>6} {result.decided:>8} "
            f"{result.hit_rate:>7.1%} {result.undecidable:>10}"
        )

    print("\n逐条明细：")
    for result in results:
        print(f"\n-- chunk_size={result.chunk_size} --")
        for query, found, distance in result.per_query:
            if found is None:
                mark, detail = "无法判定", "关键词不在提取文本里"
            elif found:
                mark, detail = "命中", f"距离={distance:.3f}" if distance is not None else ""
            else:
                mark, detail = "未中", "有期望来源但未召回到"
            print(f"  [{mark}] {query}  ({detail})")


if __name__ == "__main__":
    main()
