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
