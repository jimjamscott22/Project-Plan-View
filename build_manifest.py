"""Build projects.json from the Project Plan Files folder.

Reads every .md file (plus the .docx and the SCOUT zip's markdown),
auto-detects tech tags, gives each project a stable id, and writes a
single JSON manifest the HTML viewer loads at runtime.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

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


def parse_metadata(text: str) -> dict[str, str | list[str]]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    metadata: dict[str, str | list[str]] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if key == "tags":
            value = value.strip("[]")
            metadata[key] = [tag.strip().strip("\"'") for tag in value.split(",") if tag.strip()]
        elif key in {"title", "status"}:
            metadata[key] = value
    return metadata


def strip_markdown(value: str) -> str:
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"\*([^*]+)\*", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"^[^\w]+", "", value).strip()
    return value


def title_from_filename(path: Path) -> str:
    title = path.stem.replace("_", " ").replace("-", " ")
    title = re.sub(r"\b(mistral|plan|project|prompt)\b", "", title, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", title).strip().title()


def is_good_title(title: str) -> bool:
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


def extract_title(text: str, path: Path, metadata: dict[str, str | list[str]]) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title:
        return title

    headings = []
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
            name = strip_markdown(name_match.group(1))
            if is_good_title(name):
                return name

        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        heading = strip_markdown(match.group(2))
        if not heading:
            continue
        if "project name" in heading.lower() and ":" in heading:
            project_name = heading.split(":", 1)[1].strip()
            if is_good_title(project_name):
                return project_name
        if is_good_title(heading):
            headings.append((level, heading))

    for level, heading in headings:
        if level == 1:
            return heading
    if headings:
        return headings[0][1]
    return title_from_filename(path)


def infer_status(path: Path, metadata: dict[str, str | list[str]]) -> str:
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
    paragraphs, buf, in_code = [], [], False
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
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def relative_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_docx(path: Path) -> str:
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


def read_zip_md(zip_path: Path):
    out = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.filename.lower().endswith(".md"):
                content = z.read(info).decode("utf-8", errors="replace")
                out.append((Path(info.filename).name, content))
    return out


def build_entry(filename, title, status, manual_tags, content):
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


def build_markdown_entry(path: Path):
    content = path.read_text(encoding="utf-8", errors="replace")
    metadata = parse_metadata(content)
    tags = metadata.get("tags")
    return build_entry(
        relative_name(path, PLANS_DIR),
        extract_title(content, path, metadata),
        infer_status(path, metadata),
        tags if isinstance(tags, list) else None,
        content,
    )


def build_docx_entry(path: Path):
    content = read_docx(path)
    metadata = parse_metadata(content)
    tags = metadata.get("tags")
    return build_entry(
        relative_name(path, PLANS_DIR),
        extract_title(content, path, metadata),
        infer_status(path, metadata),
        tags if isinstance(tags, list) else None,
        content,
    )


def build_zip_entries(path: Path):
    entries = []
    for inner_name, content in read_zip_md(path):
        inner_path = Path(inner_name)
        metadata = parse_metadata(content)
        tags = metadata.get("tags")
        entries.append(build_entry(
            f"{relative_name(path, PLANS_DIR)}/{inner_name}",
            extract_title(content, inner_path, metadata),
            infer_status(inner_path, metadata),
            tags if isinstance(tags, list) else None,
            content,
        ))
    return entries


def main():
    if not PLANS_DIR.exists():
        raise SystemExit(f"Plans folder not found: {PLANS_DIR}")

    projects = []
    for path in sorted(PLANS_DIR.rglob("*.md"), key=lambda p: relative_name(p, PLANS_DIR).lower()):
        projects.append(build_markdown_entry(path))

    for path in sorted(PLANS_DIR.rglob("*.docx"), key=lambda p: relative_name(p, PLANS_DIR).lower()):
        projects.append(build_docx_entry(path))

    for path in sorted(PLANS_DIR.rglob("*.zip"), key=lambda p: relative_name(p, PLANS_DIR).lower()):
        projects.extend(build_zip_entries(path))

    pi_path = IDEAS_DIR / "Project_Ideas.md"
    if pi_path.exists():
        projects.append(build_entry(
            "Project_Ideas.md", "General Project Idea List", "Inspiration",
            ["Inspiration"], pi_path.read_text(encoding="utf-8", errors="replace"),
        ))

    status_order = {"In Progress": 0, "Idea": 1, "Reference": 2, "Inspiration": 3, "Done": 4}
    projects.sort(key=lambda p: (status_order.get(p["status"], 9), p["title"].lower()))

    manifest = {
        "version": 1,
        "generated": date.today().isoformat(),
        "projects": projects,
    }
    json_text = json.dumps(manifest, indent=2)
    OUT_PATH.write_text(json_text, encoding="utf-8")
    # Also emit projects.js so the viewer works when opened via file:// (no fetch)
    OUT_JS_PATH.write_text(
        "// Auto-generated by build_manifest.py - do not edit by hand.\n"
        "window.PROJECTS_DATA = " + json_text + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(projects)} projects -> {OUT_PATH}")
    print(f"Wrote loader script         -> {OUT_JS_PATH}")


if __name__ == "__main__":
    main()
