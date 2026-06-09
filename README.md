# Project-Plan-View

A local webpage backed by a FastAPI server that displays all my project ideas in one place. Browse, search, filter, and track the status of every plan — projects are stored in a MySQL database and served via a REST API.

## What's inside

| File / Folder | Purpose |
| --- | --- |
| `index.html` | The viewer app — served by FastAPI at `/`. |
| `server.py` | FastAPI application. Serves the UI and exposes the REST API. |
| `lib/database.py` | Async MySQL helpers (aiomysql). |
| `lib/models.py` | Pydantic request/response models. |
| `lib/parser.py` | Markdown parsing — title extraction, tag inference, entry building. |
| `schema.sql` | DDL for the `project_hub` MySQL database and `projects` table. |
| `build_manifest.py` | Legacy regenerator script (pre-backend). Kept for reference. |
| `pyproject.toml` | Project metadata and dependencies (managed with `uv`). |
| `.env.example` | Template for the required environment variables. |

## Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- A running MySQL instance (local or remote)

## First-time setup

### 1. Create the database

Run `schema.sql` against your MySQL server:

```bash
mysql -u youruser -p < schema.sql
```

This creates the `project_hub` database and the `projects` table.

### 2. Configure environment variables

Copy the example file and fill in your MySQL connection details:

```bash
cp .env.example .env
```

```ini
DB_HOST=192.168.x.x
DB_PORT=3306
DB_NAME=project_hub
DB_USER=youruser
DB_PASSWORD=yourpassword
```

### 3. Install dependencies

```bash
uv sync
```

## Running the app

The easiest way to launch the app is:

```bash
./run.sh
```

You can also use the underlying launcher directly:

```bash
uv run python -m launch --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser. The `--reload` flag restarts the server automatically when you edit Python files.

To bind to a specific host or port:

```bash
uv run python -m launch --host 0.0.0.0 --port 8080
```

## How to use it

1. Open [http://localhost:8000](http://localhost:8000) after starting the server.
2. Search across titles, summaries, tags, and full content using the bar at the top.
3. Click a tag chip or status chip to narrow the list.
4. Click any card to expand it — markdown renders inline with full syntax highlighting.
5. Click a status badge to change a project's status (Idea / In Progress / Done / Reference / Inspiration). Changes are written to the database immediately.
6. Toggle dark / light mode with the button in the header.

## Adding new project plans

### Upload individual files

Use the import UI in the browser to upload one or more `.md` files directly.

Or POST to the API directly:

```bash
curl -X POST http://localhost:8000/api/projects/import/file \
  -F "files=@my-plan.md"
```

### Scan a folder

POST the path of a local folder and the server will walk it and import every `.md` file it finds:

```bash
curl -X POST http://localhost:8000/api/projects/import/folder \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/your/plans"}'
```

### Frontmatter

Add YAML frontmatter to any markdown file to override auto-detected values:

```markdown
---
title: Display Title For The Card
status: Idea
tags: [Python, Web]
---
```

Without frontmatter the parser uses the first heading as the title, defaults the status to `Idea`, and infers tags from the file content.

## API reference

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/projects` | List all projects |
| `POST` | `/api/projects/import/file` | Import one or more uploaded `.md` files |
| `POST` | `/api/projects/import/folder` | Import all `.md` files from a server-side folder path |
| `PATCH` | `/api/projects/{id}/status` | Update a project's status |
| `DELETE` | `/api/projects/{id}` | Delete a project |

Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) and [http://localhost:8000/redoc](http://localhost:8000/redoc).

## Running tests

```bash
pytest
```

Tests use `httpx` and `pytest-asyncio`. No live database is required for the test suite.

## Tech stack

- **FastAPI** + **uvicorn** — API server and static file serving.
- **aiomysql** — Async MySQL driver.
- **Pydantic** — Request/response validation.
- **`marked`** — Markdown rendering in the browser (CDN).
- **`DOMPurify`** — Sanitizes rendered HTML (CDN).
- **`highlight.js`** — Code-block syntax highlighting (CDN).
- **`uv`** — Dependency management.

## Roadmap ideas

- Optional per-project "last touched" timestamp from file mtime.
- Export filtered view as a printable PDF.
- Multi-device status sync is now handled by the database — no extra work needed.
