"""
Python 后端的集中运行配置。

⚠️ 这些是**起点值**，不是定论：切块参数、检索参数与 embedding 模型都将由评测集 A/B 调整
（见 planning/12-路线图v2 §3.3、planning/08 §2.2）。
"""

# ---- 本地数据 ----
DATA_DIR = "data"
DATABASE_NAME = "greenbean-study-assistant.sqlite3"

# ---- 向量化 ----
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384

# 嵌入输入的字符上限：只为拦住异常超长文本，正常 chunk（DEFAULT_CHUNK_SIZE）不会被动到。
# ⚠️ 注意：模型自身还有 128 token 的序列上限，与 DEFAULT_CHUNK_SIZE 存在张力，
# 详见 docs/specs/us-stage1-embedding.md §12 —— 该问题要靠评测用数据解决，不能靠这里截断。
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
