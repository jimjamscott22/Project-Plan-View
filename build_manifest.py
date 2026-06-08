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
