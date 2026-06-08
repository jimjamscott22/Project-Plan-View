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
    assert extract_title("no headings here", Path("my_notes.md"), {}) == "My Notes"


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
