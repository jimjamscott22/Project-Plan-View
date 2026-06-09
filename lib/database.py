import json
import os

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    import aiomysql

# dotenv is optional at runtime for environments that set env vars elsewhere.
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - fallback when python-dotenv not installed
    def load_dotenv() -> None:  # type: ignore
        return None

load_dotenv()

_pool: "aiomysql.Pool | None" = None

_STATUS_ORDER = "FIELD(status,'In Progress','Idea','Reference','Inspiration','Done')"


async def _get_pool() -> "aiomysql.Pool":
    global _pool
    if _pool is None:
        aiomysql = importlib.import_module("aiomysql")
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
