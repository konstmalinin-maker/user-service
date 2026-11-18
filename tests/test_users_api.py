"""CRUD и контракт ошибок на изолированных SQLite БД."""

import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.common_models import StorageError
from app.main import create_app
from app.repositories import UserRepository


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "users.sqlite3")) as value:
        yield value


def create(client, email="ivan@example.com", name="Иван"):
    return client.post("/users", json={"email": email, "name": name})


def test_crud(client):
    assert client.get("/users").json() == []
    response = create(client, "IVAN@example.com", " Иван ")
    assert response.status_code == 201
    user = response.json()
    assert user["id"] == 1 and user["email"] == "ivan@example.com" and user["name"] == "Иван"
    assert datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")).utcoffset() is not None
    assert client.get("/users/1").json() == user
    assert client.get("/users").json() == [user]
    updated = client.put("/users/1", json={"email": "new@example.com", "name": "Пётр"})
    assert updated.status_code == 200 and updated.json()["created_at"] == user["created_at"]
    assert updated.json()["name"] == "Пётр"
    assert client.delete("/users/1").status_code == 204
    assert client.delete("/users/1").status_code == 404
    assert client.get("/users/1").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "bad", "name": "Иван"},
        {"email": "a@example.com", "name": ""},
        {"email": "a@example.com", "name": "   "},
        {"email": "a@example.com", "name": "x" * 101},
        {"email": "a@example.com", "name": "Иван", "id": 10},
        {"email": None, "name": "Иван"},
        {"email": "a@example.com", "name": 12},
    ],
)
def test_bad_input_does_not_write(client, payload):
    assert client.post("/users", json=payload).status_code == 400
    assert client.get("/users").json() == []


@pytest.mark.parametrize("name", ["x", "x" * 100])
def test_name_boundaries(client, name):
    assert create(client, name=name).status_code == 201


def test_duplicate_and_update_conflict(client):
    a = create(client).json()
    b = create(client, "b@example.com").json()
    assert create(client, "IVAN@EXAMPLE.COM").status_code == 400
    assert client.put("/users/" + str(b["id"]), json={"email": a["email"], "name": "Другое"}).status_code == 400
    assert client.get("/users/" + str(b["id"])).json() == b


def test_unknown_update(client):
    assert client.put("/users/999", json={"email": "a@example.com", "name": "A"}).status_code == 404


@pytest.mark.parametrize("path", ["/users/0", "/users/-1", "/users/abc"])
def test_invalid_id(client, path):
    assert client.get(path).status_code == 400


def test_malformed_json(client):
    response = client.post("/users", content="{bad", headers={"Content-Type": "application/json"})
    assert response.status_code == 400 and "error" in response.json()


def test_health_docs_openapi_metrics(client):
    assert client.get("/health").json()["status"] == "ok"
    assert "swagger-ui" in client.get("/docs").text
    assert client.get("/static/swagger-ui.css").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/users/{user_id}"]["get"]["operationId"] == "get_user"
    assert "422" not in schema["paths"]["/users"]["post"]["responses"]
    metrics = client.get("/metrics/")
    assert metrics.status_code == 200
    assert "api_requests_total" in metrics.text and "user-service" in metrics.text


def test_persistence_and_ids(tmp_path):
    path = tmp_path / "db.sqlite3"
    with TestClient(create_app(path)) as first:
        a = create(first).json()
        first.delete("/users/" + str(a["id"]))
        second_user = create(first, "b@example.com").json()
    with TestClient(create_app(path)) as second:
        assert second.get("/users").json() == [second_user]
        assert create(second, "c@example.com").json()["id"] > second_user["id"]


def test_storage_error_translated(client):
    with patch.object(client.app.state.repo, "create", side_effect=StorageError("disk")):
        assert create(client).status_code == 503
    with patch.object(client.app.state.repo, "list_all", side_effect=sqlite3.OperationalError("disk")):
        assert client.get("/users").status_code == 503


def test_repository_write_failure(tmp_path):
    repo = UserRepository(tmp_path / "db.sqlite3")
    with patch.object(repo, "connect", side_effect=sqlite3.OperationalError("disk")):
        with pytest.raises(StorageError):
            repo.create("a@example.com", "A")
