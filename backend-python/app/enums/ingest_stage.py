from enum import Enum


class IngestStage(str, Enum):
    """摄取流水线上可被观测的阶段。

    进度按阶段分段加权（权重在 `app/services/ingest_job_service.py`）：
    嵌入占大头，因为它就是耗时的那一段（e5-large 实测约 200 ms/片段）。
    """

    PARSING = "parsing"
    PERSISTING = "persisting"
    EMBEDDING = "embedding"
