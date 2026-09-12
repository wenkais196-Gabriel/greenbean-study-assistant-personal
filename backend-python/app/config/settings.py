"""
Python 后端的集中运行配置。

⚠️ 这些是**起点值**，不是定论：切块参数与 embedding 模型都将由评测集 A/B 调整
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
