"""
上传任务服务：把"摄取"从 HTTP 请求里搬进后台线程池，并把进度写进 `ingest_jobs`。

分工（见 docs/specs/us-stage1-upload-async.md §3.4）：

- 本服务只管 **job 的生命周期**：受理 → 投递 → 记录阶段/进度 → 终态；
- 摄取本身仍由 `DocumentIngestService` 负责，本服务只是把它的阶段回调转成落库的进度。

⚠️ 进度写库与摄取**不在同一事务**（否则进度要等提交那一刻才可见，等于没有进度）。
代价是失败时进度停留在失败前的阶段 —— 那正是我们想要的信息："走到哪一步炸的"。
"""
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import datetime, timezone

from app.db.orm import SessionFactory
from app.entities import IngestJob
from app.enums import IngestJobStatus, IngestStage
from app.repositories.ingest_job_repository import IngestJobRepository
from app.services.document_ingest_service import DocumentIngestService

# 阶段权重：整体进度 = start + (end - start) × 该阶段完成度。
# 嵌入占 85%，因为耗时几乎都在那里（e5-large 实测约 200 ms/片段）。
_STAGE_PROGRESS: dict[IngestStage, tuple[float, float]] = {
    IngestStage.PARSING: (0.0, 0.10),
    IngestStage.EMBEDDING: (0.10, 0.95),
    IngestStage.PERSISTING: (0.95, 1.0),
}

# 嵌入是 CPU 密集的：再多的 worker 只会互相抢核，不会更快。
DEFAULT_MAX_WORKERS = 2


class IngestJobService:
    """受理上传、在后台执行摄取、并让进度可查询。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        ingest_service: DocumentIngestService,
        executor: Executor | None = None,
    ) -> None:
        """
        :param session_factory: 会话工厂（生产走 app/db/runtime，测试注入临时库）
        :param ingest_service: 真正干活的摄取流水线（**已注入 session_factory**，即完整摄取）
        :param executor: 执行器；默认线程池（测试注入同步/受控执行器，避免竞态与 sleep）
        """
        self.session_factory = session_factory
        self.ingest_service = ingest_service
        self.executor = executor or ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS)

    # ---- 对外：受理与查询 ----

    def submit(
        self,
        filename: str,
        content: bytes,
        *,
        workspace_id: str = "",
        title: str | None = None,
    ) -> IngestJob:
        """受理一次上传：先把 job 落库（queued），再投递到后台，**不等它跑完**。"""
        job = IngestJob(filename=filename, workspace_id=workspace_id)
        self._save(job)
        self.executor.submit(
            self.run,
            job.id,
            filename,
            content,
            workspace_id=workspace_id,
            title=title,
        )
        return job

    def get(self, job_id: str) -> IngestJob | None:
        """查任务当前状态；不存在返回 None（由 controller 映射成 404）。"""
        with self.session_factory() as session:
            return IngestJobRepository(session).get_by_id(job_id)

    # ---- 后台执行 ----

    def run(
        self,
        job_id: str,
        filename: str,
        content: bytes,
        *,
        workspace_id: str = "",
        title: str | None = None,
    ) -> None:
        """在工作线程里跑完整摄取。

        **不向外抛异常**：这里已经是"没人接得住"的地方（线程池 worker），
        错误必须落到 job 上由客户端轮询看到。
        """
        self._update(job_id, status=IngestJobStatus.RUNNING, stage=None, progress=0.0)

        try:
            result = self.ingest_service.ingest_document(
                filename,
                content,
                workspace_id=workspace_id,
                title=title,
                on_progress=lambda stage, ratio: self._report_progress(job_id, stage, ratio),
            )
        except Exception as exc:  # noqa: BLE001 —— worker 里必须兜住一切
            self._update(
                job_id,
                status=IngestJobStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )
            return

        self._update(
            job_id,
            status=IngestJobStatus.SUCCEEDED,
            stage=IngestStage.EMBEDDING,
            progress=1.0,
            result=self._summarize(result),
        )

    # ---- 内部 ----

    def _report_progress(self, job_id: str, stage: IngestStage, ratio: float) -> None:
        """把"某阶段的完成度"折算成整体进度。

        回调来自下游，越界值一律夹到 [0, 1]：进度条宁可停住，也不能出现负数或超过 100%。
        """
        start, end = _STAGE_PROGRESS[stage]
        clamped = max(0.0, min(1.0, ratio))
        self._update(job_id, stage=stage, progress=start + (end - start) * clamped)

    def _summarize(self, result: dict) -> dict:
        """把摄取结果转成**可 JSON 序列化**的摘要（实体换成 id 与计数），才存得进表。"""
        record = result["document_record"]
        return {
            "filename": result["filename"],
            "total_pages": result["total_pages"],
            "status": result["status"],
            "page_index_preview": result["page_index_preview"],
            "document_id": record.id,
            "document_units_count": len(result.get("document_units", [])),
            "chunks_created": result["chunks_created"],
            "elapsed_seconds": result["elapsed_seconds"],
        }

    def _save(self, job: IngestJob) -> None:
        with self.session_factory() as session:
            IngestJobRepository(session).save(job)
            session.commit()

    def _update(self, job_id: str, **fields: object) -> None:
        with self.session_factory() as session:
            repository = IngestJobRepository(session)
            job = repository.get_by_id(job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            job.updated_at = datetime.now(timezone.utc)
            repository.save(job)
            session.commit()
