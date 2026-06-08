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
