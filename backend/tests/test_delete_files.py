from app.db import File, Session, Task
from app.main import app, identity
from app.storage import storage


def test_delete_generated_file_enforces_ownership_and_state(client):
    key = storage.put(b"generated content")
    with Session.begin() as db:
        task = Task(owner="local-demo", goal="Generate report", mode="demo", status="running")
        db.add(task)
        db.flush()
        file = File(task_id=task.id, name="report.pdf", mime="application/pdf", size=17, storage_key=key, kind="artifact")
        db.add(file)
        db.flush()
        file_id, task_id = file.id, task.id
        task.checkpoint = {"current_file_ids": [file_id], "turns": [{"file_ids": [file_id]}]}
    url = f"/api/files/{file_id}"
    app.dependency_overrides[identity] = lambda: "another-user"
    try:
        assert client.delete(url).status_code == 404
    finally:
        app.dependency_overrides.clear()
    assert client.delete(url).status_code == 409
    assert storage.path(key).exists()
    with Session.begin() as db:
        db.get(Task, task_id).status = "completed"
    assert client.delete(url).status_code == 200
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    assert not storage.path(key).exists()
    result = client.get(f"/api/tasks/{task_id}").json()
    assert result["files"] == []
    assert result["current_file_ids"] == []
    assert result["turns"][0]["file_ids"] == []


def test_original_uploads_cannot_be_deleted(client):
    file = client.post("/api/uploads", files={"file": ("notes.txt", b"Original document")}).json()
    assert client.delete(f"/api/files/{file['id']}").status_code == 409
    assert client.get(f"/api/files/{file['id']}").status_code == 200
