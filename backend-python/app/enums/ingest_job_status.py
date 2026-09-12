from enum import Enum


class IngestJobStatus(str, Enum):
    """一次上传摄取任务的生命周期状态（见 docs/specs/us-stage1-upload-async.md）。"""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
