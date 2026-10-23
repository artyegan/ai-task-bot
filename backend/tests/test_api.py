from app.core.models import TaskStatus


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True, "redis": True}


async def test_task_crud_flow(client, user):
    r = await client.post("/api/tasks", json={"title": "Write tests", "user_id": user.id})
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["number"] == 1
    assert task["status"] == "pending" and task["source"] == "text"
    assert task["user"] == {
        "id": user.id, "telegram_id": 123456789, "username": "alice", "first_name": "Alice"
    }
    assert task["created_at"].endswith("Z")

    r = await client.get("/api/tasks")
    assert r.status_code == 200
    assert r.json()["total"] == 1 and r.json()["items"][0]["id"] == task["id"]

    r = await client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 200 and r.json()["title"] == "Write tests"

    r = await client.patch(f"/api/tasks/{task['id']}", json={"status": "completed"})
    assert r.status_code == 200 and r.json()["status"] == "completed"

    r = await client.get("/api/tasks", params={"status": ["pending", "in_progress"]})
    assert r.json()["total"] == 0
    r = await client.get("/api/tasks", params={"status": "completed"})
    assert r.json()["total"] == 1

    r = await client.delete(f"/api/tasks/{task['id']}")
    assert r.status_code == 204
    r = await client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 404
    assert r.json() == {
        "error": {"code": "task_not_found", "message": f"Task {task['id']} does not exist"}
    }


async def test_validation_error_envelope(client, user):
    r = await client.post("/api/tasks", json={"title": "", "user_id": user.id})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error" and body["details"]

    r = await client.patch("/api/tasks/1", json={})
    assert r.status_code == 422

    r = await client.patch("/api/tasks/1", json={"status": "done"})
    assert r.status_code == 422


async def test_create_for_unknown_user(client):
    r = await client.post("/api/tasks", json={"title": "x", "user_id": 42})
    assert r.status_code == 404 and r.json()["error"]["code"] == "user_not_found"


async def test_users_endpoint(client, user):
    r = await client.get("/api/users")
    assert r.status_code == 200
    assert [u["telegram_id"] for u in r.json()["items"]] == [123456789]


async def test_status_values_are_contract_strings():
    assert [s.value for s in TaskStatus] == ["pending", "in_progress", "completed"]
