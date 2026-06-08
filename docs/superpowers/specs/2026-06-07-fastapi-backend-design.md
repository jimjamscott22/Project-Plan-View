# Project Plan Hub — FastAPI Backend Design

**Date:** 2026-06-07
**Status:** Approved

## Overview

Add a FastAPI backend to the existing Project Plan Hub so that all project data is stored centrally in a MariaDB database. Any device on the home LAN can open the viewer in a browser and see every project, regardless of where the original markdown files live. Status changes sync to the DB instead of staying in localStorage.

## Goals

- All projects visible from any device on the home LAN
- Import markdown files via a browser-based file picker or server-side folder scan
- Cross-platform: backend runs on Linux (Raspberry Pi) and Windows
- MariaDB connection configured via `.env` — no hardcoded paths or credentials
- Minimal changes to the existing viewer UI and UX

## Non-Goals

- Internet / external access (LAN-only)
- Real-time collaboration or websockets
- User authentication
- Supporting file formats other than `.md` (for now)

## Architecture

```
Project-Plan-View/
├── .env                        # DB credentials (never committed)
├── .env.example                # Template with placeholder values
├── pyproject.toml              # uv-managed dependencies
├── server.py                   # FastAPI app entry point
├── lib/
│   ├── database.py             # Async MariaDB connection pool + query helpers
│   ├── parser.py               # Markdown parsing (extracted from build_manifest.py)
│   └── models.py               # Pydantic request/response models
├── index.html                  # Existing viewer — modified for API
├── build_manifest.py           # Kept as one-time bulk migration tool
├── projects.js                 # No longer used at runtime (kept for offline fallback)
└── projects.json               # No longer used at runtime (kept for offline fallback)
```

**Runtime:** `uv run uvicorn server:app --host 0.0.0.0 --port 8000`

All devices open `http://<machine-ip>:8000` in a browser. FastAPI serves `index.html` as a static file and exposes the REST API.

## MariaDB Schema

```sql
CREATE DATABASE IF NOT EXISTS project_hub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

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
  imported_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

IDs are stable slugs derived from the title (same logic as the current `build_manifest.py`). Re-importing a file with the same title upserts the row — it does not create a duplicate.

## Environment Configuration

`.env` file alongside `server.py`:

```
DB_HOST=192.168.x.x
DB_PORT=3306
DB_NAME=project_hub
DB_USER=youruser
DB_PASSWORD=yourpassword
```

`.env.example` is committed to the repo as a template. `.env` is in `.gitignore`.

## API Endpoints

| Method   | Path                              | Description                                  |
|----------|-----------------------------------|----------------------------------------------|
| `GET`    | `/api/projects`                   | Return all projects as JSON                  |
| `POST`   | `/api/projects/import/file`       | Upload one or more `.md` files (multipart)   |
| `POST`   | `/api/projects/import/folder`     | Scan a folder path on the server             |
| `PATCH`  | `/api/projects/{id}/status`       | Update a project's status                    |
| `DELETE` | `/api/projects/{id}`              | Remove a project from the DB                 |

`GET /api/projects` returns the same shape as the current `projects.json` manifest so frontend changes are minimal.

## Import Flow

### File picker (browser → server)
1. User opens Import panel, clicks "Add Files" drop zone or browses
2. Browser sends selected `.md` files as multipart form data to `POST /api/projects/import/file`
3. Server reads file content, runs it through `lib/parser.py` (title extraction, auto-tagging, summarization)
4. Each file is upserted into the `projects` table
5. Response includes count of files added/updated; UI refreshes the project list

### Folder scan (path string → server)
1. User types a folder path into the "Scan Folder" input and clicks "Scan Folder"
2. Browser sends `{ "path": "/home/user/plans" }` to `POST /api/projects/import/folder`
3. Server walks the folder recursively for `.md` files, parses each one, upserts all into DB
4. Response includes count of files found and processed; UI refreshes

## Frontend Changes

The existing `index.html` is modified in three places only:

1. **Data loading**: `loadData()` fetches `GET /api/projects` instead of reading `window.PROJECTS_DATA` from `projects.js`. The offline fallback to `projects.js` is removed (the server is the source of truth).
2. **Status changes**: `setStatus()` calls `PATCH /api/projects/{id}/status` instead of writing to `localStorage`. `localStorage` status overrides are dropped.
3. **Import button + panel**: A new "Import" button is added to the header. Clicking it toggles an Import panel below the header with the side-by-side layout (file drop zone on the left, folder path input + Scan button on the right).

All other behaviour — search, tag/status filtering, markdown rendering, expand/collapse, dark/light toggle, word count — is unchanged.

## Parser Module (`lib/parser.py`)

Extracts the existing logic from `build_manifest.py` into importable functions:

- `parse_metadata(text)` — reads YAML-ish frontmatter
- `extract_title(text, path, metadata)` — heading / Name: field / filename fallback
- `infer_status(path, metadata)` — frontmatter status or filename heuristic
- `auto_tags(text)` — regex-based tag detection
- `summarize(text)` — first substantial paragraph, max 220 chars
- `slugify(name)` — stable ID from title
- `build_entry(...)` — assembles a project dict from the above

`build_manifest.py` is refactored to import from `lib/parser.py` so the logic lives in one place.

## Migration (One-Time)

On first setup, run:

```bash
# Uses PROJECT_PLANS_DIR env var (or its default) to locate your existing files
uv run python build_manifest.py --import-to-db
```

This reads the existing markdown files using the same folder logic as before, runs them through `lib/parser.py`, and bulk-inserts them into MariaDB. After that, `build_manifest.py` is not part of the normal workflow — importing is done through the UI.

## Dependencies (`pyproject.toml`)

```toml
[project]
name = "project-plan-hub"
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "aiomysql",
  "python-dotenv",
  "python-multipart",
]
```

## Running the Server

```bash
# Install dependencies
uv sync

# Start (development)
uv run uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Start (production / Pi)
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Access from any LAN device: `http://<server-ip>:8000`

## `.gitignore` additions

```
.env
__pycache__/
.venv/
*.pyc
.superpowers/
```
