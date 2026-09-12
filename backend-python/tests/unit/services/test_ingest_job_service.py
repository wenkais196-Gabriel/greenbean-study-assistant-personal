"""
IngestJobService 单元测试：job 生命周期、进度折算与失败路径。

用真 SQLite（`Base.metadata.create_all`，不需要 sqlite-vec）+ 假摄取服务，
既不起线程池、也不加载模型。

**执行器是测试的一部分**：`submit` 的职责只是"受理 + 投递"，
所以凡是断言中间状态的用例都注入 `RecordingExecutor`，再由测试自己决定何时 `run`。

对应规格：docs/specs/us-stage1-upload-async.md（AC1–AC6）
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.entities import DocumentRecord, DocumentUnit
from app.enums import IngestJobStatus, IngestStage
from app.services.ingest_job_service import IngestJobService


# ---- 假执行器：一个只记录、一个立即执行 ----


class RecordingExecutor:
    """只记录投递、不执行 —— 用来观察「受理但还没开工」的状态。"""

    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple, dict]] = []

    def submit(self, fn, /, *args, **kwargs):
        self.calls.append((fn, args, kwargs))
        return None


class InlineExecutor:
    """原地执行，让 submit 之后状态已经尘埃落定 —— 便于断言终态。"""

    def submit(self, fn, /, *args, **kwargs):
        fn(*args, **kwargs)
        return None


# ---- 假摄取服务 ----


class FakeIngestService:
    def __init__(self, *, progress=(), result=None, error=None) -> None:
        self.progress = list(progress)
        self.result = result if result is not None else make_summary()
        self.error = error

    def ingest_document(self, filename, content, *, on_progress=None, **kwargs):
        for stage, ratio in self.progress:
            if on_progress is not None:
                on_progress(stage, ratio)
        if self.error is not None:
            raise self.error
        return dict(self.result)


def make_record() -> DocumentRecord:
    return DocumentRecord(
        workspace_id="ws-1",
        title="cours",
        original_filename="cours.pdf",
        file_type="pdf",
        file_path="",
    )


def make_summary(record: DocumentRecord | None = None) -> dict:
    """构造 `DocumentIngestService.ingest_document` 的真实返回形状。"""
    record = record or make_record()
    return {
        "filename": "cours.pdf",
        "total_pages": 2,
        "status": "parsed_successfully",
        "page_index_preview": [{"page_number": 1, "char_count": 10, "source_type": "pdf"}],
        "document_record": record,
        "document_units": [
            DocumentUnit(document_id=record.id, sequence_index=0, text_content="a"),
            DocumentUnit(document_id=record.id, sequence_index=1, text_content="b"),
        ],
        "chunks_created": 7,
        "elapsed_seconds": 3.3,
    }


def expected_summary(record: DocumentRecord) -> dict:
    """job 里存的是**可序列化摘要**：实体换成 id 与计数。"""
    return {
        "filename": "cours.pdf",
        "total_pages": 2,
        "status": "parsed_successfully",
        "page_index_preview": [{"page_number": 1, "char_count": 10, "source_type": "pdf"}],
        "document_id": record.id,
        "document_units_count": 2,
        "chunks_created": 7,
        "elapsed_seconds": 3.3,
    }


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'jobs.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


def make_service(session_factory, ingest_service, executor=None) -> IngestJobService:
    """默认 `RecordingExecutor`：测试自己决定何时真正执行，避免与 submit 抢顺序。"""
    return IngestJobService(
        session_factory=session_factory,
        ingest_service=ingest_service,
        executor=executor if executor is not None else RecordingExecutor(),
    )


# ========== AC1：受理即返回 ==========


def test_submit_creates_a_queued_job_before_any_work_starts(session_factory):
    executor = RecordingExecutor()
    service = make_service(session_factory, FakeIngestService(), executor)

    job = service.submit("cours.pdf", b"pdf-bytes", workspace_id="ws-1")

    assert job.status is IngestJobStatus.QUEUED
    assert job.stage is None
    assert job.progress == 0.0
    assert executor.calls and executor.calls[0][1][0] == job.id, "任务应被投递出去"

    stored = service.get(job.id)
    assert stored is not None, "受理后必须能从库里查回来（重启也不丢）"
    assert stored.filename == "cours.pdf"
    assert stored.workspace_id == "ws-1"
    assert stored.status is IngestJobStatus.QUEUED


def test_submit_uses_a_thread_pool_executor_by_default(session_factory, monkeypatch):
    """不注入 executor 时用线程池 —— 上传请求不该等摄取跑完。"""
    created: list[dict] = []

    class FakeThreadPoolExecutor:
        def __init__(self, **kwargs) -> None:
            created.append(kwargs)

        def submit(self, fn, /, *args, **kwargs):
            return None

    monkeypatch.setattr(
        "app.services.ingest_job_service.ThreadPoolExecutor", FakeThreadPoolExecutor
    )

    IngestJobService(
        session_factory=session_factory,
        ingest_service=FakeIngestService(),
    )

    assert created == [{"max_workers": 2}]


# ========== AC3 / AC6：成功终态与摘要 ==========


def test_run_marks_job_running_before_ingest_starts(session_factory):
    seen: list[IngestJobStatus] = []
    holder: dict[str, str] = {}

    class ProbeIngestService(FakeIngestService):
        def ingest_document(self, filename, content, *, on_progress=None, **kwargs):
            seen.append(service.get(holder["id"]).status)  # type: ignore[union-attr]
            return dict(self.result)

    service = make_service(session_factory, ProbeIngestService())
    job = service.submit("cours.pdf", b"pdf-bytes")
    holder["id"] = job.id

    service.run(job.id, "cours.pdf", b"pdf-bytes")

    assert seen == [IngestJobStatus.RUNNING], "开工前必须先落 running，否则客户端看不出在跑"

    stored = service.get(job.id)
    assert stored is not None
    assert stored.status is IngestJobStatus.SUCCEEDED
    assert stored.progress == 1.0
    assert stored.error is None


def test_succeeded_job_carries_a_serializable_summary(session_factory):
    record = make_record()
    service = make_service(session_factory, FakeIngestService(result=make_summary(record)))

    job = service.submit("cours.pdf", b"pdf-bytes")
    service.run(job.id, "cours.pdf", b"pdf-bytes")

    stored = service.get(job.id)
    assert stored is not None
    assert stored.result == expected_summary(record), "实体必须换成 id 与计数，才存得进表"


def test_submit_then_inline_run_reaches_succeeded(session_factory):
    """配合默认线程池的等价行为：投递即执行时，submit 返回后就是终态。"""
    service = make_service(
        session_factory, FakeIngestService(), executor=InlineExecutor()
    )

    job = service.submit("cours.pdf", b"pdf-bytes")

    assert service.get(job.id).status is IngestJobStatus.SUCCEEDED  # type: ignore[union-attr]


# ========== AC4：失败可见，但不抛给上传请求 ==========


def test_run_records_failure_without_raising(session_factory):
    service = make_service(
        session_factory,
        FakeIngestService(error=ValueError("解析器无法解析该文件")),
    )

    job = service.submit("cours.pdf", b"broken")
    service.run(job.id, "cours.pdf", b"broken")  # 不得向外抛：worker 里没人接

    stored = service.get(job.id)
    assert stored is not None
    assert stored.status is IngestJobStatus.FAILED
    assert stored.error is not None and "解析器无法解析该文件" in stored.error
    assert stored.result is None


# ========== AC6 / AC7：进度单调不减、按阶段加权 ==========


def test_progress_is_monotonic_and_weighted_by_stage(session_factory):
    observed: list[float] = []
    stages: list[IngestStage | None] = []
    holder: dict[str, str] = {}

    class ProbeIngestService(FakeIngestService):
        def ingest_document(self, filename, content, *, on_progress=None, **kwargs):
            for stage, ratio in [
                (IngestStage.PARSING, 0.0),
                (IngestStage.PARSING, 1.0),
                (IngestStage.EMBEDDING, 0.0),
                (IngestStage.EMBEDDING, 0.5),
                (IngestStage.EMBEDDING, 1.0),
                (IngestStage.PERSISTING, 0.0),
                (IngestStage.PERSISTING, 1.0),
            ]:
                on_progress(stage, ratio)
                snapshot = service.get(holder["id"])
                observed.append(snapshot.progress)
                stages.append(snapshot.stage)
            return dict(self.result)

    service = make_service(session_factory, ProbeIngestService())
    job = service.submit("cours.pdf", b"pdf-bytes")
    holder["id"] = job.id

    service.run(job.id, "cours.pdf", b"pdf-bytes")

    assert observed == sorted(observed), "进度只能前进，不能回退"
    assert observed == pytest.approx([0.0, 0.10, 0.10, 0.525, 0.95, 0.95, 1.0])
    assert stages == [
        IngestStage.PARSING,
        IngestStage.PARSING,
        IngestStage.EMBEDDING,
        IngestStage.EMBEDDING,
        IngestStage.EMBEDDING,
        IngestStage.PERSISTING,
        IngestStage.PERSISTING,
    ]


def test_progress_ratio_is_clamped_to_the_unit_interval(session_factory):
    """回调来自下游，越界值不该把进度写成负数或超过 1。"""
    observed: list[float] = []
    holder: dict[str, str] = {}

    class ProbeIngestService(FakeIngestService):
        def ingest_document(self, filename, content, *, on_progress=None, **kwargs):
            on_progress(IngestStage.EMBEDDING, -1.0)
            observed.append(service.get(holder["id"]).progress)
            on_progress(IngestStage.EMBEDDING, 42.0)
            observed.append(service.get(holder["id"]).progress)
            return dict(self.result)

    service = make_service(session_factory, ProbeIngestService())
    job = service.submit("cours.pdf", b"pdf-bytes")
    holder["id"] = job.id

    service.run(job.id, "cours.pdf", b"pdf-bytes")

    assert observed == pytest.approx([0.10, 0.95]), (
        "越界值夹到嵌入阶段的区间两端（0.10~0.95）"
    )


# ========== AC5：未知任务 ==========


def test_get_returns_none_for_an_unknown_job(session_factory):
    service = make_service(session_factory, FakeIngestService())

    assert service.get("does-not-exist") is None


def test_run_on_an_unknown_job_is_a_no_op(session_factory):
    """worker 拿到的 job 可能已被清理：更新一个不存在的任务不该抛异常。"""
    service = make_service(session_factory, FakeIngestService())

    service.run("does-not-exist", "cours.pdf", b"pdf-bytes")

    assert service.get("does-not-exist") is None
