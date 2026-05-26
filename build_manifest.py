"""Build projects.json from the Project Plan Files folder.

Reads every .md file (plus the .docx and the SCOUT zip's markdown),
auto-detects tech tags, gives each project a stable id, and writes a
single JSON manifest the HTML viewer loads at runtime.
"""

import json
import re
import zipfile
from datetime import date
from pathlib import Path

from docx import Document

PLANS_DIR = Path("/sessions/determined-inspiring-davinci/mnt/Project Plan Files")
IDEAS_DIR = Path("/sessions/determined-inspiring-davinci/mnt/Project Ideas")
OUT_PATH = Path("/sessions/determined-inspiring-davinci/mnt/Project Ideas/projects.json")
OUT_JS_PATH = Path("/sessions/determined-inspiring-davinci/mnt/Project Ideas/projects.js")

PROJECTS = [
    ("AGENT-orch-plan.md",            "CodeCouncil - Multi-Agent CLI Orchestrator", "Idea", ["Python", "CLI", "AI/Agents"]),
    ("AI-Packet-Analyzer-Plan.md",    "AI Packet Analyzer",                          "Idea", ["Python", "Security", "AI/Agents", "Web"]),
    ("AI_Agent_Installation_Guide.md","AI Agent Installation Guide",                 "Reference", ["AI/Agents", "CLI"]),
    ("Apple-Health-Data-Analyzer-Plan.md", "Apple Health Data Analyzer",             "Idea", ["Python", "Desktop", "Data"]),
    ("Codebase_Analyzer_Plan.md",     "The-Visualizer - FastAPI Codebase Visualizer","Idea", ["Python", "Web", "Data"]),
    ("E-Commerce-Platform-Plan_mistral.md", "Scalable E-Commerce Microservices",     "Idea", ["Node.js", "Web", "DevOps"]),
    ("GitHub-User-Activity-Project.md", "GitHub User Activity CLI",                  "Idea", ["CLI", "Web"]),
    ("NES-EMU-plan.md",               "NES Emulator (from scratch)",                 "Idea", ["Rust", "Systems"]),
    ("New-Projects.md",               "High-Value Vibe-Coding App Ideas",            "Inspiration", ["AI/Agents", "Security", "Web"]),
    ("Tauri-setup-guide.md",          "Tauri + FastAPI Setup Guide",                 "Reference", ["Rust", "Web", "Desktop", "Python"]),
    ("md_preview_server_prompt.md",   "Markdown Preview Server (uv)",                "Idea", ["Python", "Web"]),
    ("static_site_gen_plan.md",       "Static Markdown Site Generator (uv)",         "Idea", ["Python", "Web"]),
]

EXTRA_DOCX = ("NES_Emulator_Prompt.docx", "NES Emulator - Detailed Prompt (Word)", "Idea", ["Rust", "Systems"])
RUSTY_VAULT_FILES = [
    ("Rusty-Vault-Plan_Files/Rusty_Vault_Spec.md",         "Rusty Vault - Full Spec",            "Idea", ["Rust", "Security", "CLI", "Systems"]),
    ("Rusty-Vault-Plan_Files/Rusty_Vault_StarterPrompt.md","Rusty Vault - Starter Prompt",       "Idea", ["Rust", "Security", "CLI"]),
]
SCOUT_ZIP = "SCOUT-Plan.zip"

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


def read_md(rel_path: str) -> str:
    return (PLANS_DIR / rel_path).read_text(encoding="utf-8", errors="replace")


def read_docx(rel_path: str) -> str:
    doc = Document(str(PLANS_DIR / rel_path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_zip_md(zip_name: str):
    out = []
    with zipfile.ZipFile(PLANS_DIR / zip_name) as z:
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


def main():
    projects = []
    for fn, title, status, manual in PROJECTS:
        projects.append(build_entry(fn, title, status, manual, read_md(fn)))

    fn, title, status, manual = EXTRA_DOCX
    projects.append(build_entry(fn, title, status, manual, read_docx(fn)))

    for fn, title, status, manual in RUSTY_VAULT_FILES:
        projects.append(build_entry(fn, title, status, manual, read_md(fn)))

    for inner_name, content in read_zip_md(SCOUT_ZIP):
        if "PROJECT_PLAN" in inner_name.upper():
            title = "SCOUT - Unified OSINT Toolkit (Full Plan)"
            manual = ["Python", "Web", "Security", "AI/Agents", "Data"]
        else:
            title = "SCOUT - Claude Code Starter Prompt (MVP)"
            manual = ["Python", "Web", "Security"]
        projects.append(build_entry(f"{SCOUT_ZIP}/{inner_name}", title, "Idea", manual, content))

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
