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

# ---- 切块（按字符计）----
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120
