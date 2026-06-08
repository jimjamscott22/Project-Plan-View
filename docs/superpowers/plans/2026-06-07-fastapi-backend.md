# Project Plan Hub — FastAPI Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI backend and MariaDB storage layer to the Project Plan Hub so every device on the home LAN sees all projects from a single source of truth, with a browser-based import panel replacing the manual `build_manifest.py` workflow.

**Architecture:** FastAPI serves `index.html` at `/` and exposes a REST API at `/api/*`. All project data lives in MariaDB. The existing markdown-parsing logic is extracted into `lib/parser.py` and reused by both the API and the refactored `build_manifest.py`. The frontend is modified in three narrow places: data loading, status sync, and the new Import panel.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, aiomysql, python-dotenv, python-multipart, uv (package manager), pytest + httpx (tests), MariaDB, vanilla JS (existing frontend).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `pyproject.toml` | uv project + dependencies |
| Create | `.env.example` | DB credential template |
| Create | `schema.sql` | MariaDB table definition |
| Create | `lib/__init__.py` | package marker |
| Create | `lib/parser.py` | All markdown parsing logic (extracted from `build_manifest.py`) |
| Create | `lib/models.py` | Pydantic request/response models |
| Create | `lib/database.py` | Async MariaDB pool + CRUD helpers |
| Create | `server.py` | FastAPI app — serves HTML + REST API |
| Create | `tests/__init__.py` | package marker |
| Create | `tests/conftest.py` | (empty — no shared fixtures yet) |
| Create | `tests/test_parser.py` | Unit tests for `lib/parser.py` |
| Create | `tests/test_server.py` | API tests using `TestClient` + mocked DB |
| Modify | `build_manifest.py` | Import from `lib/parser.py`; add `--import-to-db` flag |
| Modify | `index.html` | 3 targeted changes: `loadData()`, `setStatus()`, import panel |
| Update | `.gitignore` | Add `.env`, `__pycache__/`, `.venv/`, `*.pyc`, `.superpowers/` |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `schema.sql`
- Create: `lib/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "project-plan-hub"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "aiomysql",
  "python-dotenv",
  "python-multipart",
]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.env.example`**

```
DB_HOST=192.168.x.x
DB_PORT=3306
DB_NAME=project_hub
DB_USER=youruser
DB_PASSWORD=yourpassword
```

- [ ] **Step 3: Create `schema.sql`**

```sql
CREATE DATABASE IF NOT EXISTS project_hub
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE project_hub;

CREATE TABLE IF NOT EXISTS projects (
  id           VARCHAR(255) PRIMARY KEY,
  title        VARCHAR(500)  NOT NULL,
  filename     VARCHAR(500),
  status       VARCHAR(50)   DEFAULT 'Idea',
  tags         JSON,
  summary      TEXT,
  word_count   INT,
  content      LONGTEXT,
  imported_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

Apply it to MariaDB:
```bash
mysql -h <DB_HOST> -u <DB_USER> -p < schema.sql
```

- [ ] **Step 4: Create package markers and empty conftest**

Create `lib/__init__.py` — empty file.

Create `tests/__init__.py` — empty file.

Create `tests/conftest.py`:
```python
# No shared fixtures needed at this time.
```

- [ ] **Step 5: Update `.gitignore`**

Add to the end of `.gitignore` (create it if it doesn't exist):
```
.env
__pycache__/
.venv/
*.pyc
.superpowers/
```

- [ ] **Step 6: Install dependencies**

```bash
uv sync --group dev
```

Expected: uv creates `.venv/` and installs all packages. No errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example schema.sql lib/__init__.py tests/__init__.py tests/conftest.py .gitignore
git commit -m "chore: scaffold FastAPI project structure"
```

---

## Task 2: Parser Module (TDD)

**Files:**
- Create: `lib/parser.py`
- Create: `tests/test_parser.py`

This extracts all parsing logic from `build_manifest.py` into a testable module. Do not modify `build_manifest.py` yet — that happens in Task 6.

- [ ] **Step 1: Write failing tests**

Create `tests/test_parser.py`:

```python
from pathlib import Path

from lib.parser import (
    auto_tags,
    build_entry,
    extract_title,
    infer_status,
    parse_metadata,
    slugify,
    summarize,
)


def test_parse_metadata_full_frontmatter():
    text = "---\ntitle: My Project\nstatus: In Progress\ntags: [Python, Web]\n---\nContent"
    result = parse_metadata(text)
    assert result["title"] == "My Project"
    assert result["status"] == "In Progress"
    assert result["tags"] == ["Python", "Web"]


def test_parse_metadata_no_frontmatter():
    assert parse_metadata("# Just content") == {}


def test_extract_title_from_h1():
    text = "# Awesome Project\n\nSome content here"
    assert extract_title(text, Path("file.md"), {}) == "Awesome Project"


def test_extract_title_metadata_overrides_heading():
    text = "---\ntitle: Override\n---\n# Heading"
    assert extract_title(text, Path("file.md"), {"title": "Override"}) == "Override"


def test_extract_title_falls_back_to_filename():
    assert extract_title("no headings here", Path("my_project.md"), {}) == "My Project"


def test_auto_tags_python():
    assert "Python" in auto_tags("this project uses python and fastapi")


def test_auto_tags_ai():
    assert "AI/Agents" in auto_tags("uses an llm and claude api for agents")


def test_auto_tags_empty():
    assert auto_tags("just plain words with nothing special") == []


def test_summarize_returns_first_long_paragraph():
    text = "# Title\n\nThis is the first paragraph and it is long enough to be the summary.\n\nSecond paragraph."
    result = summarize(text)
    assert "first paragraph" in result
    assert "Second" not in result


def test_summarize_skips_code_blocks():
    text = "# Title\n\n```python\ncode here\n```\n\nFirst real paragraph with content."
    result = summarize(text)
    assert "real paragraph" in result
    assert "code" not in result


def test_slugify_spaces():
    assert slugify("My Cool Project") == "my-cool-project"


def test_slugify_special_chars():
    assert slugify("AI/ML Project!") == "ai-ml-project"


def test_build_entry_shape():
    entry = build_entry("test.md", "Test Project", "Idea", ["Python"], "# Test\n\nContent here")
    assert entry["id"] == "test-project"
    assert entry["title"] == "Test Project"
    assert entry["filename"] == "test.md"
    assert entry["status"] == "Idea"
    assert entry["tags"] == ["Python"]
    assert "summary" in entry
    assert entry["wordCount"] == 4
    assert entry["content"] == "# Test\n\nContent here"


def test_build_entry_auto_tags_when_no_manual_tags():
    entry = build_entry("test.md", "Test", "Idea", None, "this uses python and rust")
    assert "Python" in entry["tags"]
    assert "Rust" in entry["tags"]


def test_infer_status_from_metadata():
    assert infer_status(Path("file.md"), {"status": "Done"}) == "Done"


def test_infer_status_guide_filename():
    assert infer_status(Path("setup-guide.md"), {}) == "Reference"


def test_infer_status_default_idea():
    assert infer_status(Path("some-project.md"), {}) == "Idea"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'lib.parser'`

- [ ] **Step 3: Create `lib/parser.py`**

```python
import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)

TAG_RULES = [
    (r"\brust\b|cargo|axum|aes-gcm|tauri", "Rust"),
    (r"\bpython\b|fastapi|flask|pyside|django|\buv\b|typer|pytest", "Python"),
    (r"\bnode\.?js\b|express|nestjs|npm install", "Node.js"),
    (r"\breact\b|vite|tailwind|cytoscape|tanstack", "Web"),
    (r"\bcli\b|command line|terminal|clap", "CLI"),
    (r"\bai\b|\bllm\b|claude|gpt|gemini|ollama|anthropic|agent", "AI/Agents"),
    (r"security|osint|vault|secret|encrypt|threat|firewall|pcap|wireshark", "Security"),
    (r"docker|kubernetes|microservice|kafka|rabbitmq", "DevOps"),
    (r"sqlite|postgresql|mongodb|graph|chart|analytics|dashboard", "Data"),
    (r"emulator|6502|low-level|systemd|raspberry pi", "Systems"),
    (r"desktop|pyside|pyqt|tauri", "Desktop"),
    (r"network|tailscale|wireguard|dns|proxy", "Network"),
]


def auto_tags(text: str) -> list[str]:
    found = []
    low = text.lower()
    for pattern, tag in TAG_RULES:
        if re.search(pattern, low) and tag not in found:
            found.append(tag)
    return found


def parse_metadata(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    metadata: dict = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if key == "tags":
            value = value.strip("[]")
            metadata[key] = [t.strip().strip("\"'") for t in value.split(",") if t.strip()]
        elif key in {"title", "status"}:
            metadata[key] = value
    return metadata


def _strip_markdown(value: str) -> str:
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"\*([^*]+)\*", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    return re.sub(r"^[^\w]+", "", value).strip()


def _title_from_filename(path: Path) -> str:
    title = path.stem.replace("_", " ").replace("-", " ")
    title = re.sub(r"\b(mistral|plan|project|prompt)\b", "", title, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", title).strip().title()


def _is_good_title(title: str) -> bool:
    low = title.lower()
    if len(title) > 80:
        return False
    if "http://" in low or "https://" in low:
        return False
    if low in {"project plan & spec sheet", "requirements", "core idea"}:
        return False
    if low.startswith("use a programming language"):
        return False
    return True


def extract_title(text: str, path: Path, metadata: dict) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title:
        return title

    headings: list[tuple[int, str]] = []
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        name_match = re.match(r"^(?:\*\*)?Name:(?:\*\*)?\s*(.+)$", stripped, re.IGNORECASE)
        if name_match:
            name = _strip_markdown(name_match.group(1))
            if _is_good_title(name):
                return name
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        heading = _strip_markdown(match.group(2))
        if not heading:
            continue
        if "project name" in heading.lower() and ":" in heading:
            project_name = heading.split(":", 1)[1].strip()
            if _is_good_title(project_name):
                return project_name
        if _is_good_title(heading):
            headings.append((level, heading))

    for level, heading in headings:
        if level == 1:
            return heading
    if headings:
        return headings[0][1]
    return _title_from_filename(path)


def infer_status(path: Path, metadata: dict) -> str:
    status = metadata.get("status")
    if isinstance(status, str) and status:
        return status
    name = path.name.lower()
    if name in {"new-projects.md", "project_ideas.md", "project-ideas.md"}:
        return "Inspiration"
    if "guide" in name or "setup" in name or "reference" in name:
        return "Reference"
    return "Idea"


def summarize(text: str, max_chars: int = 220) -> str:
    lines = text.splitlines()
    paragraphs: list[str] = []
    buf: list[str] = []
    in_code = False
    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not s or s.startswith("#") or s.startswith(">") or s.startswith("|") or s.startswith("---"):
            if buf:
                paragraphs.append(" ".join(buf).strip())
                buf = []
            continue
        s = re.sub(r"^[\-\*]\s+", "", s)
        s = re.sub(r"^\d+\.\s+", "", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        buf.append(s)
    if buf:
        paragraphs.append(" ".join(buf).strip())
    for p in paragraphs:
        if len(p) >= 80:
            return (p[: max_chars - 1] + "…") if len(p) > max_chars else p
    for p in paragraphs:
        if p:
            return (p[: max_chars - 1] + "…") if len(p) > max_chars else p
    return "(no summary available)"


def slugify(name: str) -> str:
    s = name.lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def build_entry(
    filename: str,
    title: str,
    status: str,
    manual_tags: list[str] | None,
    content: str,
) -> dict:
    tags = manual_tags if manual_tags else auto_tags(content)
    return {
        "id": slugify(title),
        "title": title,
        "filename": filename,
        "status": status,
        "tags": tags,
        "summary": summarize(content),
        "wordCount": len(content.split()),
        "content": content,
    }
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: All 16 tests pass.

- [ ] **Step 5: Commit**

```bash
git add lib/parser.py tests/test_parser.py
git commit -m "feat: add parser module extracted from build_manifest"
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `lib/models.py`

- [ ] **Step 1: Create `lib/models.py`**

```python
from pydantic import BaseModel


class StatusUpdate(BaseModel):
    status: str


class FolderScanRequest(BaseModel):
    path: str


class ImportResult(BaseModel):
    added: int
    errors: list[str] = []
```

- [ ] **Step 2: Commit**

```bash
git add lib/models.py
git commit -m "feat: add Pydantic models"
```

---

## Task 4: Database Module

**Files:**
- Create: `lib/database.py`

No dedicated unit tests — this module is thin CRUD over aiomysql and is covered by the server tests in Task 5 via mocks. The real DB is validated during the one-time migration in Task 6.

- [ ] **Step 1: Create `lib/database.py`**

```python
import json
import os

import aiomysql
from dotenv import load_dotenv

load_dotenv()

_pool: aiomysql.Pool | None = None

_STATUS_ORDER = "FIELD(status,'In Progress','Idea','Reference','Inspiration','Done')"


async def _get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            db=os.environ["DB_NAME"],
            autocommit=True,
            charset="utf8mb4",
        )
    return _pool


def _row_to_project(row: dict) -> dict:
    tags = row.get("tags")
    if isinstance(tags, str):
        tags = json.loads(tags)
    return {
        "id": row["id"],
        "title": row["title"],
        "filename": row["filename"] or "",
        "status": row["status"],
        "tags": tags or [],
        "summary": row["summary"] or "",
        "wordCount": row["word_count"],
        "content": row["content"] or "",
    }


async def get_all_projects() -> list[dict]:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                f"SELECT * FROM projects ORDER BY {_STATUS_ORDER}, title"
            )
            rows = await cur.fetchall()
    return [_row_to_project(r) for r in rows]


async def upsert_project(entry: dict) -> None:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO projects
                  (id, title, filename, status, tags, summary, word_count, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  title      = VALUES(title),
                  filename   = VALUES(filename),
                  tags       = VALUES(tags),
                  summary    = VALUES(summary),
                  word_count = VALUES(word_count),
                  content    = VALUES(content)
                """,
                (
                    entry["id"],
                    entry["title"],
                    entry["filename"],
                    entry["status"],
                    json.dumps(entry["tags"]),
                    entry["summary"],
                    entry["wordCount"],
                    entry["content"],
                ),
            )


async def update_project_status(project_id: str, status: str) -> bool:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE projects SET status = %s WHERE id = %s",
                (status, project_id),
            )
            return cur.rowcount > 0


async def delete_project(project_id: str) -> bool:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM projects WHERE id = %s", (project_id,)
            )
            return cur.rowcount > 0
```

- [ ] **Step 2: Commit**

```bash
git add lib/database.py
git commit -m "feat: add async MariaDB database module"
```

---

## Task 5: FastAPI Server (TDD)

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_server.py`:

```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

SAMPLE_PROJECT = {
    "id": "my-project",
    "title": "My Project",
    "filename": "my.md",
    "status": "Idea",
    "tags": ["Python"],
    "summary": "A test project",
    "wordCount": 10,
    "content": "# My Project\n\nContent here.",
}


@patch("server.get_all_projects", new_callable=AsyncMock)
def test_list_projects_returns_manifest_shape(mock_get):
    mock_get.return_value = [SAMPLE_PROJECT]
    r = client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert "generated" in body
    assert body["projects"] == [SAMPLE_PROJECT]


@patch("server.upsert_project", new_callable=AsyncMock)
def test_import_file_returns_added_count(mock_upsert):
    mock_upsert.return_value = None
    r = client.post(
        "/api/projects/import/file",
        files=[("files", ("test.md", b"# Test Project\n\nContent here.", "text/markdown"))],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == 1
    assert body["errors"] == []


def test_import_folder_nonexistent_path_returns_400():
    r = client.post(
        "/api/projects/import/folder",
        json={"path": "/absolutely/nonexistent/path/xyz123"},
    )
    assert r.status_code == 400


@patch("server.update_project_status", new_callable=AsyncMock)
def test_set_status_ok(mock_update):
    mock_update.return_value = True
    r = client.patch("/api/projects/my-project/status", json={"status": "Done"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@patch("server.update_project_status", new_callable=AsyncMock)
def test_set_status_not_found(mock_update):
    mock_update.return_value = False
    r = client.patch("/api/projects/ghost/status", json={"status": "Done"})
    assert r.status_code == 404


def test_set_status_rejects_invalid_value():
    r = client.patch("/api/projects/my-project/status", json={"status": "Bogus"})
    assert r.status_code == 422


@patch("server.delete_project", new_callable=AsyncMock)
def test_delete_project_ok(mock_delete):
    mock_delete.return_value = True
    r = client.delete("/api/projects/my-project")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@patch("server.delete_project", new_callable=AsyncMock)
def test_delete_project_not_found(mock_delete):
    mock_delete.return_value = False
    r = client.delete("/api/projects/ghost")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Create `server.py`**

```python
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
```

- [ ] **Step 4: Run all tests — verify they pass**

```bash
uv run pytest -v
```

Expected: All tests in `test_parser.py` and `test_server.py` pass.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add FastAPI server with REST API"
```

---

## Task 6: Refactor `build_manifest.py`

**Files:**
- Modify: `build_manifest.py`

Import parsing functions from `lib/parser.py` instead of defining them inline. Add `--import-to-db` flag for the one-time migration.

- [ ] **Step 1: Replace `build_manifest.py`**

```python
"""Build projects.json from the Project Plan Files folder.

Run normally to regenerate projects.js and projects.json.
Run with --import-to-db to bulk-insert into MariaDB instead.
"""

import argparse
import asyncio
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

from lib.parser import build_entry, extract_title, infer_status, parse_metadata

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PLANS_DIR = (
    Path.home()
    / "OneDrive - Cayuga Community College"
    / "Documents"
    / "Code"
    / "Project Plan Files"
)
DEFAULT_IDEAS_DIR = DEFAULT_PLANS_DIR.parent / "Project Ideas"

PLANS_DIR = Path(os.environ.get("PROJECT_PLANS_DIR", DEFAULT_PLANS_DIR)).expanduser()
IDEAS_DIR = Path(os.environ.get("PROJECT_IDEAS_DIR", DEFAULT_IDEAS_DIR)).expanduser()
OUT_PATH = SCRIPT_DIR / "projects.json"
OUT_JS_PATH = SCRIPT_DIR / "projects.js"


def _relative_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _read_zip_md(zip_path: Path):
    out = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.filename.lower().endswith(".md"):
                content = z.read(info).decode("utf-8", errors="replace")
                out.append((Path(info.filename).name, content))
    return out


def _build_markdown_entry(path: Path):
    content = path.read_text(encoding="utf-8", errors="replace")
    meta = parse_metadata(content)
    tags = meta.get("tags")
    return build_entry(
        _relative_name(path, PLANS_DIR),
        extract_title(content, path, meta),
        infer_status(path, meta),
        tags if isinstance(tags, list) else None,
        content,
    )


def _build_docx_entry(path: Path):
    content = _read_docx(path)
    meta = parse_metadata(content)
    tags = meta.get("tags")
    return build_entry(
        _relative_name(path, PLANS_DIR),
        extract_title(content, path, meta),
        infer_status(path, meta),
        tags if isinstance(tags, list) else None,
        content,
    )


def _build_zip_entries(path: Path):
    entries = []
    for inner_name, content in _read_zip_md(path):
        inner_path = Path(inner_name)
        meta = parse_metadata(content)
        tags = meta.get("tags")
        entries.append(build_entry(
            f"{_relative_name(path, PLANS_DIR)}/{inner_name}",
            extract_title(content, inner_path, meta),
            infer_status(inner_path, meta),
            tags if isinstance(tags, list) else None,
            content,
        ))
    return entries


def _collect_projects() -> list[dict]:
    if not PLANS_DIR.exists():
        raise SystemExit(f"Plans folder not found: {PLANS_DIR}")

    projects: list[dict] = []
    for path in sorted(PLANS_DIR.rglob("*.md"), key=lambda p: _relative_name(p, PLANS_DIR).lower()):
        projects.append(_build_markdown_entry(path))
    for path in sorted(PLANS_DIR.rglob("*.docx"), key=lambda p: _relative_name(p, PLANS_DIR).lower()):
        projects.append(_build_docx_entry(path))
    for path in sorted(PLANS_DIR.rglob("*.zip"), key=lambda p: _relative_name(p, PLANS_DIR).lower()):
        projects.extend(_build_zip_entries(path))

    pi_path = IDEAS_DIR / "Project_Ideas.md"
    if pi_path.exists():
        projects.append(build_entry(
            "Project_Ideas.md", "General Project Idea List", "Inspiration",
            ["Inspiration"], pi_path.read_text(encoding="utf-8", errors="replace"),
        ))

    status_order = {"In Progress": 0, "Idea": 1, "Reference": 2, "Inspiration": 3, "Done": 4}
    projects.sort(key=lambda p: (status_order.get(p["status"], 9), p["title"].lower()))
    return projects


async def _import_all_to_db(projects: list[dict]) -> None:
    from lib.database import upsert_project
    for p in projects:
        await upsert_project(p)
        print(f"  Imported: {p['title']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or import project manifest")
    parser.add_argument(
        "--import-to-db",
        action="store_true",
        help="Insert projects into MariaDB (requires .env with DB credentials)",
    )
    args = parser.parse_args()

    projects = _collect_projects()

    if args.import_to_db:
        print(f"Importing {len(projects)} projects into MariaDB...")
        asyncio.run(_import_all_to_db(projects))
        print("Done.")
        return

    manifest = {"version": 1, "generated": date.today().isoformat(), "projects": projects}
    json_text = json.dumps(manifest, indent=2)
    OUT_PATH.write_text(json_text, encoding="utf-8")
    OUT_JS_PATH.write_text(
        "// Auto-generated by build_manifest.py - do not edit by hand.\n"
        "window.PROJECTS_DATA = " + json_text + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(projects)} projects -> {OUT_PATH}")
    print(f"Wrote loader script         -> {OUT_JS_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to confirm nothing broke**

```bash
uv run pytest -v
```

Expected: All tests still pass.

- [ ] **Step 3: Run one-time migration** (requires `.env` with real DB credentials and `PLANS_DIR` to exist)

```bash
uv run python build_manifest.py --import-to-db
```

Expected: Each project prints `Imported: <title>`, then `Done.`

- [ ] **Step 4: Commit**

```bash
git add build_manifest.py
git commit -m "refactor: build_manifest imports from lib/parser, adds --import-to-db"
```

---

## Task 7: Frontend — Data Loading and Status Sync

**Files:**
- Modify: `index.html`

Three targeted changes. Do not touch anything else in the file.

- [ ] **Step 1: Replace `loadData()` (lines 476–484)**

Find and replace this block:

```javascript
async function loadData() {
  if (window.PROJECTS_DATA) return window.PROJECTS_DATA;
  // Fallback: try fetch (works when served by a local server)
  try {
    const r = await fetch('projects.json');
    if (r.ok) return await r.json();
  } catch (e) { /* ignored */ }
  return null;
}
```

Replace with:

```javascript
async function loadData() {
  const r = await fetch('/api/projects');
  if (!r.ok) throw new Error(`API error: ${r.status}`);
  return await r.json();
}
```

- [ ] **Step 2: Remove `statusOverrides` from STATE (line 454)**

Find:
```javascript
  statusOverrides: JSON.parse(localStorage.getItem('pph.statusOverrides') || '{}'),
```

Delete that line entirely. The STATE object should end with:
```javascript
const STATE = {
  data: null,
  query: '',
  activeTags: new Set(),
  activeStatuses: new Set(),
  openCards: new Set(),
};
```

- [ ] **Step 3: Replace `currentStatus()` and `setStatus()` (lines 543–551)**

Find:
```javascript
function currentStatus(p) {
  return STATE.statusOverrides[p.id] || p.status;
}
function setStatus(p, newStatus) {
  if (newStatus === p.status) delete STATE.statusOverrides[p.id];
  else STATE.statusOverrides[p.id] = newStatus;
  localStorage.setItem('pph.statusOverrides', JSON.stringify(STATE.statusOverrides));
}
```

Replace with:
```javascript
function currentStatus(p) {
  return p.status;
}
function setStatus(p, newStatus) {
  fetch(`/api/projects/${p.id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: newStatus }),
  }).then(r => {
    if (r.ok) { p.status = newStatus; render(); }
  });
}
```

- [ ] **Step 4: Update boot sequence (lines 734–748)**

Find:
```javascript
(async () => {
  STATE.data = await loadData();
  if (!STATE.data) {
    document.getElementById('cards').innerHTML = `
      <div class="empty">
        <h2>Could not load project data</h2>
        <p>Expected <code>projects.js</code> or <code>projects.json</code> alongside this HTML file.</p>
        <p>Re-run <code>build_manifest.py</code> to regenerate.</p>
      </div>`;
    document.getElementById('metaCount').textContent = '';
    return;
  }
  render();
})();
```

Replace with:
```javascript
(async () => {
  try {
    STATE.data = await loadData();
  } catch (e) {
    document.getElementById('cards').innerHTML = `
      <div class="empty">
        <h2>Could not connect to server</h2>
        <p>Make sure the Project Plan Hub server is running.</p>
        <p>Start it with: <code>uv run uvicorn server:app --host 0.0.0.0 --port 8000</code></p>
      </div>`;
    document.getElementById('metaCount').textContent = '';
    return;
  }
  render();
})();
```

- [ ] **Step 5: Start the server and verify the viewer loads**

First copy `.env.example` to `.env` and fill in your real DB credentials.

```bash
cp .env.example .env
# edit .env with real values
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser. Expected: viewer loads showing all imported projects, no console errors.

- [ ] **Step 6: Verify status changes sync to DB**

Click a status badge on any card, change it. Reload the page (`http://localhost:8000`). Expected: the new status persists — it's in MariaDB, not localStorage.

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "feat: wire frontend to /api instead of projects.js, sync status to DB"
```

---

## Task 8: Frontend — Import Panel

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add CSS for the import panel**

Inside the `<style>` block, before the closing `</style>` tag, add:

```css
/* ─────── Import panel ─────── */
.import-panel {
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.import-inner {
  max-width: 1100px; margin: 0 auto;
  padding: 16px 24px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
}
.import-col > .label {
  display: block; margin-bottom: 10px;
}
.drop-zone {
  border: 1.5px dashed var(--border);
  border-radius: var(--radius);
  padding: 24px;
  text-align: center;
  background: var(--bg-elev);
  cursor: pointer;
  transition: border-color .15s;
}
.drop-zone.drag-over { border-color: var(--accent); }
.drop-zone .drop-icon { font-size: 24px; margin-bottom: 8px; }
.drop-zone p { margin: 4px 0; color: var(--text); font-size: 13px; }
.link-btn {
  background: none; border: none; color: var(--accent);
  cursor: pointer; font: inherit; font-size: 13px;
  text-decoration: underline; padding: 0;
}
.folder-scan {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.folder-input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  padding: 8px 10px;
  font-family: var(--mono); font-size: 13px;
  width: 100%;
  box-sizing: border-box;
}
.folder-input:focus { outline: none; border-color: var(--accent); }
.import-action-btn {
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: var(--radius-sm);
  padding: 8px;
  font: inherit; font-size: 13px;
  cursor: pointer;
  transition: background .15s, color .15s;
}
.import-action-btn:hover { background: var(--accent); color: #fff; }
.import-msg {
  max-width: 1100px; margin: 0 auto;
  padding: 0 24px 12px;
  font-size: 13px; color: var(--text-dim);
  min-height: 20px;
}
.import-msg.ok { color: var(--status-done-fg); }
.import-msg.err { color: var(--status-insp-fg); }
@media (max-width: 600px) {
  .import-inner { grid-template-columns: 1fr; padding-left: 16px; padding-right: 16px; }
}
```

- [ ] **Step 2: Add Import button to the header**

Find the header button group (around line 411):
```html
    <button class="icon-btn" id="expandAllBtn" title="Expand / collapse all">
```

Insert this button immediately before it:
```html
    <button class="icon-btn" id="importBtn" title="Import projects">
      ⬆ Import
    </button>
```

- [ ] **Step 3: Add import panel HTML after `</header>`**

Find `</header>` and insert immediately after it:
```html
<section id="importPanel" class="import-panel" hidden>
  <div class="import-inner">
    <div class="import-col">
      <span class="label">Add Files</span>
      <div class="drop-zone" id="dropZone">
        <input type="file" id="fileInput" multiple accept=".md" hidden>
        <div class="drop-icon">📄</div>
        <p>Drop .md files here or <button class="link-btn" id="browseBtn">browse</button></p>
        <p style="font-size:11px;color:var(--text-muted)">Supports multiple files at once</p>
      </div>
    </div>
    <div class="import-col">
      <span class="label">Scan Folder</span>
      <div class="folder-scan">
        <p style="font-size:11px;color:var(--text-muted);margin:0">Folder path on this machine</p>
        <input id="folderPath" class="folder-input" type="text" placeholder="/home/user/projects">
        <button class="import-action-btn" id="scanBtn">Scan Folder</button>
      </div>
    </div>
  </div>
  <div id="importMsg" class="import-msg"></div>
</section>
```

- [ ] **Step 4: Add import panel JavaScript**

Find the `/* ─────── Boot ─────── */` comment in the `<script>` block. Insert the following block immediately before it:

```javascript
/* ─────── Import panel ─────── */
document.getElementById('importBtn').onclick = () => {
  const panel = document.getElementById('importPanel');
  panel.hidden = !panel.hidden;
};

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

document.getElementById('browseBtn').onclick = () => fileInput.click();

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', async e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  await _uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', async () => {
  await _uploadFiles(fileInput.files);
  fileInput.value = '';
});

async function _uploadFiles(fileList) {
  const form = new FormData();
  for (const f of fileList) form.append('files', f);
  _showImportMsg('Uploading…', '');
  try {
    const r = await fetch('/api/projects/import/file', { method: 'POST', body: form });
    const data = await r.json();
    if (r.ok) {
      _showImportMsg(`Added ${data.added} project(s).${data.errors.length ? ' Some errors — check console.' : ''}`, 'ok');
      if (data.errors.length) console.warn('Import errors:', data.errors);
      await _refreshProjects();
    } else {
      _showImportMsg(`Upload failed: ${data.detail || r.status}`, 'err');
    }
  } catch (e) {
    _showImportMsg('Upload failed — check server connection.', 'err');
  }
}

document.getElementById('scanBtn').onclick = async () => {
  const path = document.getElementById('folderPath').value.trim();
  if (!path) return;
  _showImportMsg('Scanning…', '');
  try {
    const r = await fetch('/api/projects/import/folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const data = await r.json();
    if (r.ok) {
      _showImportMsg(`Scanned — added ${data.added} project(s).`, 'ok');
      await _refreshProjects();
    } else {
      _showImportMsg(`Error: ${data.detail}`, 'err');
    }
  } catch (e) {
    _showImportMsg('Scan failed — check server connection.', 'err');
  }
};

function _showImportMsg(text, cls) {
  const el = document.getElementById('importMsg');
  el.textContent = text;
  el.className = 'import-msg' + (cls ? ' ' + cls : '');
}

async function _refreshProjects() {
  STATE.data = await loadData();
  render();
}
```

- [ ] **Step 5: Smoke test the import panel**

With the server running (`uv run uvicorn server:app --host 0.0.0.0 --port 8000`):

1. Open `http://localhost:8000`
2. Click **⬆ Import** — panel slides open showing two columns
3. Drop a `.md` file onto the drop zone — message shows `Added 1 project(s).`, project list refreshes
4. Type a folder path into "Scan Folder" and click **Scan Folder** — message shows count, list refreshes
5. Click **⬆ Import** again — panel closes

- [ ] **Step 6: Test on a second device**

From another device on the same LAN, open `http://<server-ip>:8000`. Expected: same project list, same status values. Import a file from that device — it appears on both devices after refresh.

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "feat: add import panel with file picker and folder scan"
```

---

## Self-Review Checklist

- [x] **Spec coverage**
  - Goals: LAN visibility ✓ (FastAPI on `--host 0.0.0.0`), file + folder import ✓ (Tasks 5 + 8), cross-platform ✓ (Python + browser), `.env` config ✓ (Task 1 + 4), minimal UI change ✓ (Tasks 7 + 8)
  - API endpoints: all 5 implemented in `server.py` ✓
  - `lib/parser.py` extraction ✓ (Task 2), `build_manifest.py` refactor ✓ (Task 6), `--import-to-db` ✓ (Task 6)
  - Side-by-side import panel layout ✓ (Task 8)
  - Status synced to DB, localStorage removed ✓ (Task 7)
  - `uv` used throughout ✓
  - `.env.example` committed ✓ (Task 1)
  - Schema SQL committed ✓ (Task 1)
  - `.gitignore` updated ✓ (Task 1)

- [x] **No placeholders** — all steps contain actual code or exact commands.

- [x] **Type consistency** — `build_entry()` returns a dict with `wordCount` (camelCase) everywhere; `_row_to_project()` in `database.py` maps `word_count` → `wordCount`; server tests use `wordCount` in `SAMPLE_PROJECT`.
