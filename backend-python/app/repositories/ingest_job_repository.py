from sqlalchemy.orm import Session

from app.db.models import IngestJobModel
from app.entities import IngestJob
from app.enums import IngestJobStatus, IngestStage
from app.repositories.sqlite_helpers import datetime_value, json_object, json_value


class IngestJobRepository:
    """`ingest_jobs` 表的读写：上传任务的进度载体（见 docs/specs/us-stage1-upload-async.md §4）。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, job: IngestJob) -> IngestJob:
        model = self.session.get(IngestJobModel, job.id)
        if model is None:
            model = IngestJobModel(id=job.id, created_at=datetime_value(job.created_at))
            self.session.add(model)
        model.filename = job.filename
        model.workspace_id = job.workspace_id
        model.status = job.status.value
        model.stage = job.stage.value if job.stage is not None else None
        model.progress = job.progress
        model.error = job.error
        model.result_json = json_value(job.result)
        model.updated_at = datetime_value(job.updated_at)
        return job

    def get_by_id(self, job_id: str) -> IngestJob | None:
        model = self.session.get(IngestJobModel, job_id)
        if model is None:
            return None
        return IngestJob(
            id=model.id,
            filename=model.filename,
            workspace_id=model.workspace_id,
            status=IngestJobStatus(model.status),
            stage=IngestStage(model.stage) if model.stage is not None else None,
            progress=model.progress,
            error=model.error,
            result=json_object(model.result_json),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
