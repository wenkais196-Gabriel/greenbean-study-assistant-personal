"""
L1 检索层评测：对 golden set 用**生产链路**跑一遍，算出检索命中率并列出失败案例。

为什么必须走生产链路（真解析 → 真切块 → 真嵌入 → 真检索），而不是像实验脚本那样
自己拼一套：自己拼出来的那一套测的不是线上行为，调参结论就不能直接搬到生产。
见 planning/10 §1「把评测拆成两层，让 L1 完全离线可重复」——L1 不调用任何 LLM，零成本、确定性。

判定口径（比首测收紧，首测的期望片段集合 p50=7、max=26，等于"沾边就算命中"）：
  命中 = 召回片段里存在 (文档名相同 **且** 页码落在 expected_sources.pages 内) 的一条。
  页码是硬条件 —— 因为本项目的 chunk 是按页（DocumentUnit）切出来的，页 ↔ 片段一一对应。

脚本同时做**评测集自检**：检查每条 query 的 expected_keywords 是否真的出现在期望页的片段文本里。
首轮报告栽在"关键词根本找不到却被当成未命中"，这个自检就是防止重蹈覆辙。

用法：
    python eval/run_eval.py --docs-dir "D:/桌面/测试文件"
    python eval/run_eval.py --docs-dir "D:/桌面/测试文件" --out docs/eval-report-golden.md
"""
import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend-python"))

# 本脚本会打印 ✅/⚠️，Windows 的 GBK 控制台重定向时会直接崩 —— 显式声明 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402

from app.config.settings import (  # noqa: E402
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
)
from app.db.init_db import initialize_database, load_sqlite_vec_extension  # noqa: E402
from app.db.models import (  # noqa: E402
    ChunkModel,
    DocumentRecordModel,
    DocumentUnitModel,
)
from app.db.orm import create_database_engine, create_session_factory  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.repositories.embedding_repository import EmbeddingRepository  # noqa: E402
from app.services.document_ingest_service import DocumentIngestService  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.jsonl"
KS = (1, 3, 5, 10, 20)
MAX_K = max(KS)
EVALUABLE_TYPES = ("fact", "cross_page", "terminology")


@dataclass
class ItemResult:
    """一条 query 的评测结果。"""

    entry: dict
    # 期望来源在召回列表里的最佳名次（1-based）；None = 前 MAX_K 条里都没出现
    best_rank: int | None
    top_hits: list[tuple[str, int | None]] = field(default_factory=list)

    @property
    def query_id(self) -> str:
        return self.entry["id"]

    @property
    def query_type(self) -> str:
        return self.entry["type"]

    def hit_at(self, k: int) -> bool:
        return self.best_rank is not None and self.best_rank <= k


def load_golden_set(path: Path) -> list[dict]:
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("golden set 里有重复的 id")
    return entries


def chunk_lookup(session) -> dict[str, tuple[str, int | None]]:
    """chunk_id → (原始文件名, 页码)：判定命中要按「文档 + 页」比对。"""
    rows = session.execute(
        select(
            ChunkModel.id,
            DocumentRecordModel.original_filename,
            DocumentUnitModel.page_number,
        )
        .join(DocumentUnitModel, ChunkModel.document_unit_id == DocumentUnitModel.id)
        .join(DocumentRecordModel, DocumentUnitModel.document_id == DocumentRecordModel.id)
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


def page_texts(session) -> dict[tuple[str, int | None], str]:
    """(文档名, 页码) → 该页所有片段拼起来的文本，供评测集自检用。"""
    rows = session.execute(
        select(
            DocumentRecordModel.original_filename,
            DocumentUnitModel.page_number,
            ChunkModel.text_content,
        )
        .join(DocumentUnitModel, ChunkModel.document_unit_id == DocumentUnitModel.id)
        .join(DocumentRecordModel, DocumentUnitModel.document_id == DocumentRecordModel.id)
    ).all()
    merged: dict[tuple[str, int | None], str] = {}
    for filename, page, text in rows:
        merged[(filename, page)] = merged.get((filename, page), "") + "\n" + (text or "")
    return merged


def build_index(docs_dir: Path, workdir: Path):
    """用生产服务把全部 PDF 摄取进临时库，返回 (engine, session_factory, embedding_service)。"""
    initialization = initialize_database(
        data_dir=workdir,
        database_name="eval.sqlite3",
        embedding_dimension=EMBEDDING_DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        initialization.database_path, sqlite_vec_loader=load_sqlite_vec_extension
    )
    session_factory = create_session_factory(engine)
    embedding_service = EmbeddingService(dimension=EMBEDDING_DIMENSION)
    service = DocumentIngestService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_dimension=EMBEDDING_DIMENSION,
    )

    for pdf in sorted(docs_dir.glob("*.pdf")):
        started = time.perf_counter()
        outcome = service.ingest_document(pdf.name, pdf.read_bytes())
        print(
            f"  摄取 {pdf.name}：{outcome['total_pages']} 页 / "
            f"{outcome['chunks_created']} 片段（{time.perf_counter() - started:.1f}s）"
        )
    return engine, session_factory, embedding_service


def evaluate_entry(entry: dict, hits, lookup: dict[str, tuple[str, int | None]]) -> ItemResult:
    expected = entry["expected_sources"]
    best_rank: int | None = None
    top_hits: list[tuple[str, int | None]] = []

    for rank, hit in enumerate(hits, start=1):
        filename, page = lookup.get(hit.chunk_id, ("?", None))
        if len(top_hits) < 5:
            top_hits.append((filename, page))
        if best_rank is None and any(
            source["doc"] == filename and page in source["pages"] for source in expected
        ):
            best_rank = rank

    return ItemResult(entry=entry, best_rank=best_rank, top_hits=top_hits)


def normalize(text: str) -> str:
    """折叠空白 + casefold。

    两个都必须做，否则会把"其实有"判成"找不到"：
    - **空白**：PDF 提取的文本里，同一个短语常被换行拆开；chunk 更是保留了原换行
      （首轮报告正是栽在这里，见 docs/eval-report.md §1.1 的方法学教训）。
    - **大小写**：原文写 "Apprentissage"（句首大写），小写关键词严格匹配会漏。
    """
    return " ".join(text.split()).casefold()


def validate_golden_set(entries: list[dict], texts: dict[tuple[str, int | None], str]) -> list[str]:
    """评测集自检：每条 query 的 expected_keywords 是否真出现在期望页里。

    首轮报告把"关键词根本找不到"当成"未命中"，方向直接测反。这里把它变成硬检查：
    找不到就报出来，让人先判断是评测集写错了，还是检索出了问题。
    """
    problems: list[str] = []
    for entry in entries:
        if entry["type"] == "no_answer":
            continue
        for source in entry["expected_sources"]:
            haystack = normalize(
                "\n".join(texts.get((source["doc"], page), "") for page in source["pages"])
            )
            missing = [
                kw
                for kw in entry.get("expected_keywords", [])
                if normalize(kw) not in haystack
            ]
            if missing:
                problems.append(
                    f"{entry['id']}（{entry['type']}）：{source['doc']} 的第 "
                    f"{source['pages']} 页里找不到 {missing}"
                )
    return problems


def check_no_answer_entries(entries: list[dict], texts: dict[tuple[str, int | None], str]) -> list[str]:
    """no_answer 的前提是"资料里真的没有" —— 用整库文本反查一遍，避免把有答案的问题当拒答题。

    用**词边界**匹配：不加边界时 "ECTS" 会命中 "factuellement incorrects"、"mail" 会命中
    "Mailly"（教师姓氏），假警报一堆，真问题反而被淹没。
    """
    whole_corpus = normalize("\n".join(texts.values()))
    suspicious: list[str] = []
    for entry in entries:
        if entry["type"] != "no_answer":
            continue
        for keyword in entry.get("must_not_appear", []):
            if re.search(rf"\b{re.escape(normalize(keyword))}\b", whole_corpus):
                suspicious.append(f"{entry['id']}：{keyword!r} 其实出现在语料里")
    return suspicious


def hit_rates(results: list[ItemResult]) -> dict[int, float]:
    if not results:
        return {k: 0.0 for k in KS}
    return {k: sum(1 for r in results if r.hit_at(k)) / len(results) for k in KS}


def mrr(results: list[ItemResult]) -> float:
    if not results:
        return 0.0
    return sum(1.0 / r.best_rank for r in results if r.best_rank) / len(results)


def render_report(
    results: list[ItemResult],
    problems: list[str],
    docs_dir: Path,
    no_answer_flags: list[str],
    total_entries: int,
) -> str:
    evaluable = [r for r in results if r.query_type in EVALUABLE_TYPES]
    lines: list[str] = []
    lines.append("# L1 检索评测报告（golden set）\n")
    lines.append(
        f"> 数据集：**{total_entries} 条**（{len(evaluable)} 条可评测 + "
        f"{total_entries - len(evaluable)} 条 no_answer，后者不进 L1 命中率）"
    )
    lines.append(
        f"> 语料：`{docs_dir}` ｜模型：`{EMBEDDING_MODEL}`（{EMBEDDING_DIMENSION} 维）"
        f"｜切块：`chunk_size={DEFAULT_CHUNK_SIZE}` / `overlap={DEFAULT_CHUNK_OVERLAP}`"
    )
    lines.append(f"> 检索深度：`top_k={MAX_K}`｜命中判定：**文档名 + 页码**同时匹配\n")

    lines.append("## 1. 总览\n")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    overall = hit_rates(evaluable)
    for k in KS:
        lines.append(f"| HitRate@{k} | **{overall[k]:.1%}** |")
    lines.append(f"| MRR | **{mrr(evaluable):.3f}** |")
    lines.append("")

    lines.append("## 2. 按类型\n")
    by_type = {t: [r for r in evaluable if r.query_type == t] for t in EVALUABLE_TYPES}
    lines.append("| 类型 | 条数 | " + " | ".join(f"@{k}" for k in KS) + " | MRR |")
    lines.append("|---|---|" + "---|" * (len(KS) + 1))
    for query_type, items in by_type.items():
        if not items:
            continue
        rates = hit_rates(items)
        cells = " | ".join(f"{rates[k]:.0%}" for k in KS)
        lines.append(
            f"| {query_type} | {len(items)} | {cells} | {mrr(items):.3f} |"
        )
    lines.append("")

    failures = [r for r in evaluable if not r.hit_at(5)]
    lines.append(f"## 3. 失败案例（HitRate@5 未命中，{len(failures)} 条）\n")
    if not failures:
        lines.append("无。\n")
    else:
        lines.append("| id | 类型 | 提问 | 期望来源 | 最佳名次 | 实际 top-3 |")
        lines.append("|---|---|---|---|---|---|")
        for item in sorted(failures, key=lambda r: (r.best_rank is None, r.best_rank or 0)):
            expected = "；".join(
                f"{s['doc']} p{s['pages']}" for s in item.entry["expected_sources"]
            )
            found = "；".join(f"{name} p{page}" for name, page in item.top_hits[:3])
            rank = "未召回（>%d）" % MAX_K if item.best_rank is None else str(item.best_rank)
            lines.append(
                f"| {item.query_id} | {item.query_type} | {item.entry['query']} | "
                f"{expected} | {rank} | {found} |"
            )
        lines.append("")

    lines.append("## 4. 排名分布（全部可评测条目）\n")
    distribution: dict[str, list[str]] = {"第 1 名": [], "第 2-5 名": [], "第 6-20 名": [], "未召回": []}
    for item in evaluable:
        rank = item.best_rank
        if rank is None:
            distribution["未召回"].append(item.query_id)
        elif rank == 1:
            distribution["第 1 名"].append(item.query_id)
        elif rank <= 5:
            distribution["第 2-5 名"].append(item.query_id)
        else:
            distribution["第 6-20 名"].append(item.query_id)
    lines.append("| 桶 | 条数 | id |")
    lines.append("|---|---|---|")
    for bucket, ids in distribution.items():
        lines.append(f"| {bucket} | {len(ids)} | {' '.join(ids) or '—'} |")
    lines.append("")

    lines.append("## 5. 评测集自检（口径验证）\n")
    if problems:
        lines.append("⚠️ 以下条目的 `expected_keywords` 在期望页里**找不到**，需要先确认是评测集写错还是语料问题：\n")
        for problem in problems:
            lines.append(f"- {problem}")
    else:
        lines.append("✅ 每条可评测 query 的 `expected_keywords` 都能在期望页的片段文本里找到。")
    lines.append("")
    if no_answer_flags:
        lines.append("⚠️ no_answer 条目的反查命中（这些题可能其实有答案）：\n")
        for flag in no_answer_flags:
            lines.append(f"- {flag}")
    else:
        lines.append("✅ no_answer 条目未在语料中反查出答案（`must_not_appear` 均未出现）。")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="L1 检索层评测（golden set，零 LLM 成本）")
    parser.add_argument("--docs-dir", required=True, help="包含法语课程 PDF 的目录")
    parser.add_argument("--golden-set", default=str(GOLDEN_SET_PATH), help="golden set 路径（JSONL）")
    parser.add_argument("--out", default="", help="报告输出路径（Markdown）；不传则打印到 stdout")
    parser.add_argument(
        "--gate-hit-rate-5",
        type=float,
        default=None,
        help="门禁模式：评测集自检失败 exit 2；HitRate@5 低于该值 exit 1；否则 exit 0",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        raise SystemExit(f"目录不存在：{docs_dir}")

    entries = load_golden_set(Path(args.golden_set))
    print(f"golden set：{len(entries)} 条")

    workdir = Path(tempfile.mkdtemp(prefix="gb-eval-"))
    print(f"临时库目录：{workdir}")
    engine = None
    try:
        print("\n构建索引（走生产链路：真解析 → 真切块 → 真嵌入）……")
        engine, session_factory, embedding_service = build_index(docs_dir, workdir)

        with session_factory() as session:
            lookup = chunk_lookup(session)
            texts = page_texts(session)
            repository = EmbeddingRepository(session, embedding_dimension=EMBEDDING_DIMENSION)
            retriever = Retriever(embedding_service, top_k=MAX_K)

            results: list[ItemResult] = []
            print("\n逐条检索……")
            for entry in entries:
                if entry["type"] == "no_answer":
                    continue
                hits = retriever.retrieve(repository, entry["query"])
                results.append(evaluate_entry(entry, hits, lookup))

        problems = validate_golden_set(entries, texts)
        no_answer_flags = check_no_answer_entries(entries, texts)

        report = render_report(results, problems, docs_dir, no_answer_flags, len(entries))
    finally:
        if engine is not None:
            engine.dispose()
        # 临时库只是评测的中间产物，跑完即弃（与 production data/ 无关）
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n报告已写入：{args.out}")
    else:
        print("\n" + report)

    if args.gate_hit_rate_5 is not None:
        if problems or no_answer_flags:
            print("\n❌ 门禁失败：评测集自检未通过（见上方警告）")
            raise SystemExit(2)
        overall = hit_rates(results)
        rate_at_5 = overall[5]
        if rate_at_5 < args.gate_hit_rate_5:
            print(
                f"\n❌ 门禁失败：HitRate@5 = {rate_at_5:.1%}，"
                f"低于阈值 {args.gate_hit_rate_5:.1%}"
            )
            raise SystemExit(1)
        print(
            f"\n✅ 门禁通过：HitRate@5 = {rate_at_5:.1%}"
            f"（阈值 {args.gate_hit_rate_5:.1%}）"
        )


if __name__ == "__main__":
    main()
