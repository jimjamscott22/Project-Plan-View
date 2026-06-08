from pydantic import BaseModel


class StatusUpdate(BaseModel):
    status: str


class FolderScanRequest(BaseModel):
    path: str


class ImportResult(BaseModel):
    added: int
    errors: list[str] = []
