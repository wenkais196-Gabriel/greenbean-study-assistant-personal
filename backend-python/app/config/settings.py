"""
Python 后端的集中运行配置。

⚠️ 这些是**起点值**，不是定论：切块参数、检索参数与 embedding 模型都将由评测集 A/B 调整
（见 planning/12-路线图v2 §3.3、planning/08 §2.2）。
"""

# ---- 本地数据 ----
DATA_DIR = "data"
DATABASE_NAME = "greenbean-study-assistant.sqlite3"

# ---- 向量化 ----
# 模型选型（2026-09-12 由 MiniLM-L12-v2 换为 e5-large，依据 docs/retrieval-diagnosis.md §3.7 的对照）：
# - 命中率：中文 @5 50% → 66.7%、@20 91.7% → 100%；法语 @5（同语言基线）50% → 83.3%
# - 序列上限：512 token（MiniLM 只有 128，会截断 39.5% 的片段 —— 换模型即消除该张力）
# - 代价（本机 CPU 实测）：模型 0.22 GB → 2.2 GB；query 嵌入 P50 4 ms → 30 ms（每次问答都付）；
#   408 个片段建索引 7 s → 112 s（一次性成本，上传后需给用户进度反馈）
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSION = 1024

# e5 系列要求给 query / passage 加前缀，否则效果明显低于其应有水平（见 §3.7 的实验口径）。
# 前缀在**送模型前**拼接，不写进 chunk 存储文本；换成不需要前缀的模型时置空即可。
EMBEDDING_QUERY_PREFIX = "query: "
EMBEDDING_PASSAGE_PREFIX = "passage: "

# 嵌入输入的字符上限：只为拦住异常超长文本，正常 chunk（DEFAULT_CHUNK_SIZE）不会被动到。
# 序列上限不再是问题：e5-large 是 512 token（≈2200 字符），500 字符的 chunk 远未触顶。
MAX_EMBED_CHARS = 1000

# 分批嵌入的批大小：这个参数**只为让进度可见**（每批结束报一次进度），不改变嵌入结果。
# 16 片段 × 约 200 ms/片段 ≈ 3 s 一次回调：进度条动得起来，批开销也还不显眼。
# 调大 → 回调更稀疏（大文档会长时间不动）；调小 → 每批的固定开销占比上升。
EMBEDDING_BATCH_SIZE = 16

# ---- 切块（按字符计）----
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120

# ---- 检索 ----
# top_k：诊断实验（docs/retrieval-diagnosis.md §3.2）显示中文提问 HitRate@5 仅 50%，
# 放宽到 @20 达 83.3%（修重音后 91.7%）—— 失败样本大多排在第 6~20 名，不是召不回来，
# 因此由 5 上调到 20。代价是进入上下文的片段变多 —— 由 ContextBuilder 的
# CONTEXT_MAX_CHARS 预算裁剪兜底（超预算的片段整片丢弃）。
RETRIEVAL_TOP_K = 20

# max_distance：默认为 None（先不过滤），阈值必须由评测数据决定。
# ⚠️ 距离口径是 vec0 默认的**非平方 L2（欧氏距离）**，不是平方 L2 ——
# 实测与自算平方 L2 偏差 9.906、与自算欧氏距离偏差 0.000001，设阈值时按这个口径。
RETRIEVAL_MAX_DISTANCE: float | None = None

# ---- Agent 工具循环 ----
# 问答 Agent 最多让模型调用几轮工具（每轮可能调用多个工具）。这是硬终止条件：
# 模型一直要工具也不会无限循环，超限后强制用已有上下文直答（见 docs/specs/us-stage2-agent-tool-loop.md）。
MAX_TOOL_ROUNDS = 3

# 单个工具调用的执行超时：本地检索是毫秒级，这里只防"工具实现卡死"的异常情况；
# 超时按执行失败处理 → 降级直答。
TOOL_TIMEOUT_SECONDS = 10.0

# 工具结果回喂给模型的字符上限（近似）：单个工具结果再长也不会撑爆上下文。
# 4000 字符 ≈ 950 token（按法文 4.3 字符/token 估），远小于 CONTEXT_MAX_CHARS。
TOOL_RESULT_MAX_CHARS = 4000

# ---- 上下文组装 ----
# 进入 LLM 的上下文规模上限（按字符近似）：法文实测约 4.3 字符/token，
# 8000 字符 ≈ 1900 token，给 8k 上下文窗口的模型留出 query / 历史 / 输出的余量。
# ⚠️ 实测（docs/retrieval-diagnosis.md §3.6）：top_k=20 的真实召回合计只有约 7800 字符
# （片段平均 376 字符，而非 chunk_size 上限 500），**当前不会触发裁剪** ——
# 它是防异常超长的保险，不是生效的约束；要真正控规模得先按 provider 窗口收紧这个值。
# 近似规模控制（不加载 tokenizer）；精确 token 预算应由 provider 的上下文窗口决定。
CONTEXT_MAX_CHARS = 8000

# ---- API ----
# 允许跨域的前端来源：vite dev server（vite.config.ts 固定 5173）与 Tauri 壳。
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
]

# ---- 可观测性 ----
# 结构化 trace 的总开关：关闭时不写任何 span、也不提供查询（见 docs/specs/us-stage1-trace.md AC9）。
# 目前是全量记录（一次提问 4 条 span、一次上传 4 条）—— 本地单机够用；
# 高流量下应改为按比例采样，而不是靠这个开关一刀切。
TRACE_ENABLED = True
