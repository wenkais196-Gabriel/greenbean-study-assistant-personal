"""
L2 生成层评测：用**真实 LLM** 跑同一份 golden set，量化答案质量、拒答、工具循环与成本。

与 L1 的分工（见 eval/README.md）：

| | L1（run_eval.py） | L2（本脚本） |
|---|---|---|
| 测什么 | 正确片段有没有被召回 | 答案好不好、有没有编造、代价多大 |
| 要 LLM | 不要（零成本、完全可重复） | **要**（必须有已激活的 provider） |
| 指标 | HitRate@k / MRR | 引用精确率·召回率 / 拒答正确率 / 工具循环 / 延迟·token |

它走**完整问答链路**（`ChatService`：路由 → 检索 → Agent（含有界工具循环）→ 带来源回答），
与线上是同一套代码。因此需要有已激活的 LLM provider —— 在界面「设置」里配置并激活，或调
`POST /api/providers/{id}/activate`。**没有激活配置时直接报错退出**，不静默跳过：
静默跳过会让人以为"跑过了"，而实际上一个数都没有。

拒答判定同时用**两种口径**并报告一致性（口径本身可不可信也是结论的一部分）：
- 启发式：答案里出现明确的拒答措辞（零成本、可重复，但措辞多变时会误判）；
- LLM-as-judge：让模型判定"是否复述了资料里没有的信息"（更准，代价是每条多一次调用）。

用法：
    # 先配好并激活一个模型，然后：
    python eval/run_eval_l2.py --docs-dir "<含 PDF 的语料目录>" --out docs/eval-report-l2.md
    python eval/run_eval_l2.py --docs-dir "<语料目录>" --limit 5   # 小样本试跑
"""
import argparse
import asyncio
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_DIR))

# 本脚本会打印 ✅/⚠️，Windows 的 GBK 控制台重定向时会直接崩 —— 显式声明 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from run_eval import GOLDEN_SET_PATH, REPO_ROOT, build_index, load_golden_set  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.config.settings import DATABASE_NAME, DATA_DIR  # noqa: E402
from app.db.init_db import load_sqlite_vec_extension  # noqa: E402
from app.db.models import DocumentRecordModel  # noqa: E402
from app.db.orm import create_database_engine, create_session_factory  # noqa: E402
from app.providers.registry import ProviderNotFoundError, ProviderRegistry  # noqa: E402
from app.repositories.provider_config_repository import ProviderConfigRepository  # noqa: E402
from app.schemas.chat_schema import ChatRequest  # noqa: E402
from app.services.chat_service import ChatService  # noqa: E402
from app.services.trace_recorder import TraceRecorder  # noqa: E402

# 每个条目用独立的会话 ID：避免上一条的历史（指代、引用）影响下一条
SESSION_ID = "l2-eval"

# 启发式拒答信号：模型明确说"资料里没有"时的常见措辞（中 / 英 / 法）
REFUSAL_MARKERS = (
    "无法回答", "无法确定", "无法判断", "资料中没有", "资料中未", "没有找到",
    "未提及", "未涉及", "不足以", "不知道", "没有相关内容",
    "cannot find", "can't find", "no information", "not mentioned", "insufficient",
    "je ne peux pas", "ne figure pas", "aucune information",
)

# 工具调用的 span 名（见 app/agents/chat_agent.py）
TOOL_SPAN_NAME = "greenbean.tool.call"

# 答案正文里的来源标记（`ContextBuilder.render()` 的产物）：`[来源 1]` / `[来源 1, 第3页]`
SOURCE_MARKER = re.compile(r"来源\s*(\d+)")

@dataclass
class ItemOutcome:
    """一条 query 的一次真实问答，连同可量化的观测值。"""

    entry_id: str
    query: str
    type: str
    answer: str
    cited: set[tuple[str, int | None]]
    expected: set[tuple[str, int]]
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    tool_calls: int
    tool_errors: int
    refused_heuristic: bool
    refused_judge: bool | None
    trace_id: str | None
    error: str | None = None

def production_db_path() -> Path:
    """后端进程用的生产库路径。

    后端由 `scripts/run_demo.py` 以 **backend-python** 为 cwd 启动，而
    `settings.DATA_DIR = "data"` 是相对路径 —— 库因此固定在 `backend-python/data/`。
    评测脚本常从仓库根运行，这里显式拼绝对路径，避免读到仓库根下那个**空的** data/。
    """
    return REPO_ROOT / "backend-python" / DATA_DIR / DATABASE_NAME

def activate_provider() -> str:
    """从生产库读激活配置并装进 `ProviderRegistry`，返回模型名。

    评测本身用临时库，但 provider 配置在**生产库**（界面写进去的那份）—— 只读它。
    """
    db_path = production_db_path()
    if not db_path.exists():
        raise SystemExit(
            f"找不到生产库：{db_path}。"
            "先启动后端（python scripts/run_demo.py），在界面「设置」里配置并激活一个模型。"
        )

    engine = create_database_engine(db_path, sqlite_vec_loader=load_sqlite_vec_extension)
    try:
        with create_session_factory(engine)() as session:
            config = ProviderConfigRepository(session).get_active()
    finally:
        engine.dispose()

    if config is None:
        raise SystemExit(
            "没有已激活的模型配置。\n"
            "请先启动前后端（python scripts/run_demo.py），在界面「设置」里填写并激活一个\n"
            "OpenAI 兼容端点，或用 POST /api/providers/{id}/activate 激活后再跑 L2。"
        )

    try:
        ProviderRegistry.activate(config)
    except ProviderNotFoundError as exc:  # pragma: no cover - 防御分支
        raise SystemExit(f"激活模型失败：{exc}") from exc

    return f"{config.display_name}（{config.model_id} @ {config.api_host}）"

def document_filenames(session_factory) -> dict[str, str]:
    """文档 ID → **原始文件名**。

    必须用 `original_filename` 而不是 `title`：golden set 的 `expected_sources.doc`
    写的是含扩展名的文件名，而 `title` 是摄取时由文件名推导并**去掉扩展名**的
    （`os.path.splitext(filename)[0]`）—— 用 title 比对会一条都对不上。
    """
    with session_factory() as session:
        rows = session.execute(
            select(DocumentRecordModel.id, DocumentRecordModel.original_filename)
        ).all()
    return {row[0]: row[1] for row in rows}

def expected_pairs(entry: dict) -> set[tuple[str, int]]:
    """期望来源集合：`(文档名, 页码)`。"""
    pairs: set[tuple[str, int]] = set()
    for source in entry.get("expected_sources") or []:
        for page in source.get("pages") or []:
            pairs.add((source["doc"], page))
    return pairs

def cited_by_answer(
    answer: str, sources: list[dict], filenames: dict[str, str]
) -> set[tuple[str, int | None]]:
    """答案正文里 `[来源 N]` **实际指到**的来源。

    不能用 `source_context` 代替：那是**检索上下文**（`top_k=20` 条全在里面），
    拿它算精确率会把「检索多给了几条」记成「回答引错了」。
    `ContextBuilder.render()` 写的 `[来源 N]` 是 1-based，对应 `sources[N-1]`。
    """
    cited: set[tuple[str, int | None]] = set()
    for raw_index in SOURCE_MARKER.findall(answer):
        index = int(raw_index) - 1
        if 0 <= index < len(sources):
            source = sources[index]
            document_id = source.get("document_id") or ""
            cited.add((filenames.get(document_id, document_id), source.get("page_number")))
    return cited

def looks_like_refusal(answer: str) -> bool:
    """启发式拒答判定：答案里出现明确的"资料里没有"措辞。"""
    lowered = answer.lower()
    return any(marker.lower() in lowered for marker in REFUSAL_MARKERS)

async def judge_refusal(provider, question: str, answer: str) -> bool | None:
    """LLM-as-judge：判定这次回答是否在"资料里没有答案"时诚实地拒答了。

    返回 None 表示判定本身失败（调用异常或返回不可解析）——**不猜**，
    让报告把它单列出来，而不是混进"拒答/未拒答"里。
    """
    prompt = (
        "你在评估一个课程资料问答助手是否诚实地拒答。\n"
        "规则：如果提供的资料里没有足够信息回答问题，助手应当明确表示无法回答/资料中没有，"
        "而不是编造或用常识补全。\n\n"
        f"【问题】{question}\n"
        f"【助手回答】{answer}\n\n"
        "请只回一个词：REFUSED（诚实拒答）或 ANSWERED（给出了实质性回答）。"
    )
    try:
        result = await provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
    except Exception:
        return None

    text = (result.content or "").strip().upper()
    if "REFUSED" in text:
        return True
    if "ANSWERED" in text:
        return False
    return None

async def run_item(service: ChatService, entry: dict, filenames: dict[str, str], recorder) -> ItemOutcome:
    """跑一条 query 的完整问答链路，并把观测值收齐。"""
    started = time.perf_counter()
    response = await service.answer(ChatRequest(session_id=SESSION_ID, query=entry["query"]))
    latency_ms = (time.perf_counter() - started) * 1000

    tool_calls = 0
    tool_errors = 0
    if recorder is not None and response.trace_id:
        for span in recorder.get_trace(response.trace_id):
            if span.span_name == TOOL_SPAN_NAME:
                tool_calls += 1
                if span.status.value == "error":
                    tool_errors += 1

    return ItemOutcome(
        entry_id=entry["id"],
        query=entry["query"],
        type=entry["type"],
        answer=response.answer,
        cited=cited_by_answer(response.answer, response.source_context or [], filenames),
        expected=expected_pairs(entry),
        latency_ms=latency_ms,
        input_tokens=getattr(response.usage, "input_tokens", None),
        output_tokens=getattr(response.usage, "output_tokens", None),
        tool_calls=tool_calls,
        tool_errors=tool_errors,
        refused_heuristic=looks_like_refusal(response.answer),
        refused_judge=None,
        trace_id=response.trace_id,
    )

def percentile(values: list[float], ratio: float) -> float:
    """简单分位数（样本量是几十条，不需要插值花活）。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * ratio))
    return ordered[index]

def citation_metrics(outcomes: list[ItemOutcome]) -> dict[str, float]:
    """引用质量的一组口径。

    只给「按 (文档, 页) 严格比对」的精确率会**低估**引用质量：实测偏差里
    「文档不同」是 0 条 —— 模型从没引错资料，只是习惯把内容相邻的页一起标上，
    而那些页不在 golden set 标定的「标准答案页」里。所以同时给三个口径：

    - `precision` / `recall`：严格按 (文档, 页) 比对；
    - `document_hit_rate`：引用的来源里落在**期望文档**的比例（只看文档、不看页）；
    - `intersecting_rate`：至少引到一个期望页的条目占比（会话级「有没有指对地方」）。
    """
    evaluable = [item for item in outcomes if item.expected and item.error is None]
    if not evaluable:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "document_hit_rate": 0.0,
            "intersecting_rate": 0.0,
            "evaluable": 0.0,
        }

    hits = sum(len(item.cited & item.expected) for item in evaluable)
    cited_total = sum(len(item.cited) for item in evaluable)
    expected_total = sum(len(item.expected) for item in evaluable)

    cited_docs_total = 0
    cited_docs_in_expected = 0
    for item in evaluable:
        expected_docs = {doc for doc, _ in item.expected}
        for doc, _page in item.cited:
            cited_docs_total += 1
            if doc in expected_docs:
                cited_docs_in_expected += 1

    intersecting = sum(1 for item in evaluable if item.cited & item.expected)

    return {
        "precision": hits / cited_total if cited_total else 0.0,
        "recall": hits / expected_total if expected_total else 0.0,
        "document_hit_rate": (
            cited_docs_in_expected / cited_docs_total if cited_docs_total else 0.0
        ),
        "intersecting_rate": intersecting / len(evaluable),
        "evaluable": float(len(evaluable)),
    }


def citation_gap_summary(outcomes: list[ItemOutcome]) -> dict[str, int]:
    """引用偏差的**构成**：同文档页不同 vs 文档不同。

    这一个统计用来回答「精确率低是口径窄还是真引错」—— 光看百分数分不出来：
    偏差几乎都是「同文档、页不同」，说明答案引的是内容相邻的页，多半是 golden set 的
    期望页集合偏窄（口径问题）；大量「文档不同」才是真的引用偏差。
    """
    summary = {"same_document": 0, "other_document": 0}
    for item in outcomes:
        if item.error is not None or not item.expected:
            continue
        if not (item.cited - item.expected):
            continue
        cited_docs = {doc for doc, _ in item.cited}
        expected_docs = {doc for doc, _ in item.expected}
        key = "same_document" if cited_docs & expected_docs else "other_document"
        summary[key] += 1
    return summary


def citation_gaps(
    outcomes: list[ItemOutcome], limit: int = 10
) -> list[tuple[str, str, str, str]]:
    """偏差明细：条目 / 答案引到的来源 / 期望来源 / 偏差类型（取前 limit 条）。"""

    def fmt(pairs: set[tuple[str, int | None]]) -> str:
        ordered = sorted(pairs, key=lambda pair: (pair[0], -1 if pair[1] is None else pair[1]))
        return "、".join(
            f"{doc} p{page}" if page is not None else f"{doc} p?" for doc, page in ordered
        )

    rows: list[tuple[str, str, str, str]] = []
    for item in outcomes:
        if item.error is not None or not item.expected:
            continue
        if not (item.cited - item.expected):
            continue
        cited_docs = {doc for doc, _ in item.cited}
        expected_docs = {doc for doc, _ in item.expected}
        kind = "同文档，页不同" if cited_docs & expected_docs else "文档不同"
        rows.append((item.entry_id, fmt(item.cited), fmt(item.expected), kind))
    return rows[:limit]


def refusal_metrics(outcomes: list[ItemOutcome]) -> dict[str, float]:
    """拒答正确率（no_answer 题）与误拒率（可评测题）。两种口径各算一遍。"""
    no_answer = [item for item in outcomes if item.type == "no_answer" and item.error is None]
    evaluable = [item for item in outcomes if item.type != "no_answer" and item.error is None]

    def rate(items: list[ItemOutcome], field: str) -> float:
        judged = [item for item in items if getattr(item, field) is not None]
        if not judged:
            return 0.0
        return sum(1 for item in judged if getattr(item, field)) / len(judged)

    return {
        "no_answer_total": float(len(no_answer)),
        "refusal_rate_heuristic": rate(no_answer, "refused_heuristic"),
        "refusal_rate_judge": rate(no_answer, "refused_judge"),
        "false_refusal_rate_heuristic": rate(evaluable, "refused_heuristic"),
        "false_refusal_rate_judge": rate(evaluable, "refused_judge"),
    }

def agreement(outcomes: list[ItemOutcome]) -> tuple[int, int]:
    """两种拒答口径在全部都判定成功的条目上的分歧数 / 可比总数。"""
    compared = [
        item
        for item in outcomes
        if item.error is None and item.refused_judge is not None
    ]
    conflicts = sum(
        1 for item in compared if item.refused_heuristic != item.refused_judge
    )
    return conflicts, len(compared)

def render_report(
    outcomes: list[ItemOutcome], model_label: str, docs_dir: Path, judge_enabled: bool
) -> str:
    metrics = citation_metrics(outcomes)
    precision = metrics["precision"]
    recall = metrics["recall"]
    evaluable_count = int(metrics["evaluable"])
    with_citations = sum(
        1 for item in outcomes if item.expected and item.cited and item.error is None
    )
    gap_summary = citation_gap_summary(outcomes)
    gaps = citation_gaps(outcomes)
    refusal = refusal_metrics(outcomes)
    conflicts, compared = agreement(outcomes)

    latencies = [item.latency_ms for item in outcomes if item.error is None]
    input_tokens = [item.input_tokens for item in outcomes if item.input_tokens is not None]
    output_tokens = [item.output_tokens for item in outcomes if item.output_tokens is not None]
    total_tools = sum(item.tool_calls for item in outcomes)
    total_tool_errors = sum(item.tool_errors for item in outcomes)
    with_tools = sum(1 for item in outcomes if item.tool_calls > 0)
    failures = [item for item in outcomes if item.error is not None]

    lines: list[str] = []
    lines.append("# L2 生成层评测报告")
    lines.append("")
    lines.append(f"- 语料目录：`{docs_dir}`")
    lines.append(f"- 模型：{model_label}")
    lines.append(f"- 样本：{len(outcomes)} 条（可评测 {evaluable_count}，no_answer "
                 f"{int(refusal['no_answer_total'])}）")
    lines.append(f"- LLM-as-judge：{'开启' if judge_enabled else '关闭'}")
    lines.append("")
    lines.append("> ⚠️ 生成层有随机性（temperature > 0），同一份 golden set 两次结果不会逐字相同；")
    lines.append("> 引用/拒答的数字应看**量级与分层**，不要当成精确常数。")
    lines.append("")

    lines.append("## 一、引用准确率")
    lines.append("")
    lines.append("| 指标 | 值 | 口径 |")
    lines.append("|---|---|---|")
    lines.append(f"| 引用精确率 | **{precision:.1%}** | 答案 `[来源 N]` 指到的来源中，属于期望来源的比例 |")
    lines.append(f"| 引用召回率 | **{recall:.1%}** | 期望来源里被答案正文引用到的比例 |")
    lines.append(
        f"| 文档命中率 | **{metrics['document_hit_rate']:.1%}** |"
        " 答案引用的来源落在期望**文档**里的比例（只看文档、不看页） |"
    )
    lines.append(
        f"| 至少引到一个期望页 | **{metrics['intersecting_rate']:.1%}** |"
        " 引用的页里至少有一个是标准答案页的条目占比 |"
    )
    lines.append("")
    lines.append(f"| 答案带来源标记的题数 | {with_citations} / {evaluable_count} | 完全没写 `[来源 N]` 的答案不进精确率分母 |")
    lines.append("")
    lines.append("> **口径**：统计的是答案**正文里写的** `[来源 N]`，不是 `source_context` ——")
    lines.append("> 后者是 top_k 条检索上下文，拿它算精确率会把「检索多给了几条」记成「回答引错了」。")
    lines.append("> `[来源 N]` 与 `sources[N-1]` 一一对应（`ContextBuilder.render()` 的 1-based 标记）。")
    lines.append("")
    lines.append("### 偏差构成（回答「精确率低是口径窄还是真引错」）")
    lines.append("")
    lines.append("| 类型 | 条数 | 读法 |")
    lines.append("|---|---|---|")
    lines.append(
        f"| 同文档、页不同 | {gap_summary['same_document']} |"
        " 内容相邻的页，多半是期望页集合偏窄（口径问题） |"
    )
    lines.append(
        f"| 文档不同 | {gap_summary['other_document']} | 更可能是真的引用偏差 |"
    )
    lines.append("")
    if gaps:
        lines.append("| 条目 | 答案引到的来源 | 期望来源 | 类型 |")
        lines.append("|---|---|---|---|")
        for entry_id, cited, expected, kind in gaps:
            lines.append(f"| `{entry_id}` | {cited} | {expected} | {kind} |")
        lines.append("")
    lines.append("")

    lines.append("## 二、拒答（两种口径对比）")
    lines.append("")
    lines.append("| 指标 | 启发式 | LLM-as-judge |")
    lines.append("|---|---|---|")
    lines.append(
        f"| no_answer 拒答正确率 | {refusal['refusal_rate_heuristic']:.1%} "
        f"| {refusal['refusal_rate_judge']:.1%} |"
    )
    lines.append(
        f"| 可评测题误拒率 | {refusal['false_refusal_rate_heuristic']:.1%} "
        f"| {refusal['false_refusal_rate_judge']:.1%} |"
    )
    lines.append("")
    if compared:
        lines.append(
            f"两种口径在 {compared} 条可比样本上**分歧 {conflicts} 条**"
            f"（{conflicts / compared:.1%}）。分歧越大，越说明单靠启发式不可靠 —— "
            "这本身就是一条结论。"
        )
    else:
        lines.append("两种口径没有可比样本（judge 未开启或判定全部失败）。")
    lines.append("")

    lines.append("## 三、工具循环（回答假设 #11）")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 发生过工具调用的题数 | {with_tools} / {len(outcomes)} |")
    lines.append(f"| 工具调用总次数 | {total_tools} |")
    lines.append(f"| 工具调用失败次数 | {total_tool_errors} |")
    lines.append("")
    lines.append("> 工具调用次数为 0 不一定意味着「没触发工具循环」——也可能是模型直接放弃了调用，或工具失败后降级直答。")

    lines.append("")

    lines.append("## 四、延迟与成本（回答假设 #9）")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 端到端延迟 P50 | {percentile(latencies, 0.5):.0f} ms |")
    lines.append(f"| 端到端延迟 P95 | {percentile(latencies, 0.95):.0f} ms |")
    if input_tokens:
        lines.append(f"| 输入 token 平均 | {sum(input_tokens) / len(input_tokens):.0f} |")
        lines.append(f"| 输出 token 平均 | {sum(output_tokens) / len(output_tokens):.0f} |"
                     if output_tokens else "| 输出 token 平均 | provider 未回传 |")
    else:
        lines.append("| token 用量 | provider 未回传，拿不到成本数据 |")
    lines.append("")
    lines.append("> 延迟是**不含流式**的整段等待（从提问到拿到完整回答），与首字延迟 TTFT 不是一回事。")
    lines.append("")

    lines.append("## 五、失败案例")
    lines.append("")
    if failures:
        for item in failures:
            lines.append(f"- `{item.entry_id}`（{item.type}）：{item.query}\n  - 错误：{item.error}")
    else:
        lines.append("没有执行失败的样本。")
    lines.append("")

    lines.append("## 六、限制")
    lines.append("")
    lines.append(f"1. 样本 {len(outcomes)} 条，且 query 由项目作者构造（有「照着目录出题」的偏易倾向）；")
    lines.append("2. 生成层有随机性，跨次比较需谨慎；")
    lines.append("3. 引用口径只看「引用到的页是否在期望页内」，**没有**判定「答案的每句话都被引用支持」（faithfulness）——那需要更细的 judge，见 planning/10；")

    lines.append("4. 拒答的启发式口径依赖措辞，judge 口径依赖模型自身判断，两者都非金标准。")
    lines.append("")
    return "\n".join(lines)

async def run(args) -> tuple[list[ItemOutcome], str]:
    entries = load_golden_set(Path(args.golden_set))
    if args.limit:
        entries = entries[: args.limit]
    print(f"golden set：{len(entries)} 条")

    model_label = activate_provider()
    print(f"模型：{model_label}")

    workdir = Path(tempfile.mkdtemp(prefix="gb-l2-"))
    print(f"临时库目录：{workdir}")
    engine = None
    outcomes: list[ItemOutcome] = []
    try:
        print("\n构建索引（与 L1 同一条生产链路：真解析 → 真切块 → 真嵌入）……")
        engine, session_factory, embedding_service = build_index(Path(args.docs_dir), workdir)
        filenames = document_filenames(session_factory)

        # trace 写进**临时库**，不要污染生产库（评测产物与生产数据分开）
        recorder = TraceRecorder(session_factory=session_factory)
        service = ChatService(
            session_factory=session_factory,
            embedding_service=embedding_service,
            trace_recorder=recorder,
        )
        provider = ProviderRegistry.get_active()

        print("\n逐条真实问答（含工具循环）……")
        for index, entry in enumerate(entries, start=1):
            try:
                outcome = await run_item(service, entry, filenames, recorder)
            except Exception as exc:
                outcomes.append(
                    ItemOutcome(
                        entry_id=entry["id"], query=entry["query"], type=entry["type"],
                        answer="", cited=set(), expected=expected_pairs(entry),
                        latency_ms=0.0, input_tokens=None, output_tokens=None,
                        tool_calls=0, tool_errors=0, refused_heuristic=False,
                        refused_judge=None, trace_id=None,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                print(f"  [{index}/{len(entries)}] {entry['id']} ✗ 失败")
                continue

            if args.judge:
                outcome.refused_judge = await judge_refusal(provider, entry["query"], outcome.answer)

            state = "拒答" if outcome.refused_heuristic else "作答"
            print(
                f"  [{index}/{len(entries)}] {entry['id']} ✓ {state}"
                f" / 工具 {outcome.tool_calls} 次 / {outcome.latency_ms:.0f} ms"
            )
            outcomes.append(outcome)
    finally:
        if engine is not None:
            engine.dispose()
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)

    return outcomes, model_label

def main() -> None:
    parser = argparse.ArgumentParser(description="L2 生成层评测（需要已激活的 LLM provider）")
    parser.add_argument("--docs-dir", required=True, help="包含法语课程 PDF 的目录")
    parser.add_argument("--golden-set", default=str(GOLDEN_SET_PATH), help="golden set 路径（JSONL）")
    parser.add_argument("--out", default="", help="报告输出路径（Markdown）；不传则打印到 stdout")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（试跑用）")
    parser.add_argument("--no-judge", dest="judge", action="store_false", help="跳过 LLM-as-judge")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        raise SystemExit(f"目录不存在：{docs_dir}")

    outcomes, model_label = asyncio.run(run(args))
    report = render_report(outcomes, model_label, docs_dir, args.judge)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n报告已写入：{args.out}")
    else:
        print("\n" + report)

if __name__ == "__main__":
    main()
