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
