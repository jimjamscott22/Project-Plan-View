from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from lib.database import delete_project, get_all_projects, update_project_status, upsert_project
from lib.models import FolderScanRequest, ImportResult, StatusUpdate
from lib.parser import build_entry, extract_title, infer_status, parse_metadata

app = FastAPI(title="Project Plan Hub")

_BASE = Path(__file__).parent
_VALID_STATUSES = {"Idea", "In Progress", "Done", "Reference", "Inspiration"}


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(_BASE / "index.html")


@app.get("/api/projects")
async def list_projects() -> dict:
    projects = await get_all_projects()
    return {"version": 1, "generated": date.today().isoformat(), "projects": projects}


@app.post("/api/projects/import/file")
async def import_files(files: list[UploadFile] = File(...)) -> ImportResult:
    added, errors = 0, []
    for f in files:
        try:
            content = (await f.read()).decode("utf-8", errors="replace")
            path = Path(f.filename or "upload.md")
            meta = parse_metadata(content)
            manual_tags = meta.get("tags")
            entry = build_entry(
                f.filename or "upload.md",
                extract_title(content, path, meta),
                infer_status(path, meta),
                manual_tags if isinstance(manual_tags, list) else None,
                content,
            )
            await upsert_project(entry)
            added += 1
        except Exception as exc:
            errors.append(f"{f.filename}: {exc}")
    return ImportResult(added=added, errors=errors)


@app.post("/api/projects/import/folder")
async def import_folder(req: FolderScanRequest) -> ImportResult:
    folder = Path(req.path).expanduser()
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {req.path}")
    added, errors = 0, []
    for md_path in sorted(folder.rglob("*.md")):
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace")
            meta = parse_metadata(content)
            manual_tags = meta.get("tags")
            entry = build_entry(
                str(md_path),
                extract_title(content, md_path, meta),
                infer_status(md_path, meta),
                manual_tags if isinstance(manual_tags, list) else None,
                content,
            )
            await upsert_project(entry)
            added += 1
        except Exception as exc:
            errors.append(f"{md_path.name}: {exc}")
    return ImportResult(added=added, errors=errors)


@app.patch("/api/projects/{project_id}/status")
async def set_status(project_id: str, body: StatusUpdate) -> dict:
    if body.status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
    updated = await update_project_status(project_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@app.delete("/api/projects/{project_id}")
async def remove_project(project_id: str) -> dict:
    deleted = await delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}
