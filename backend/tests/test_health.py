from fastapi.testclient import TestClient

from app.main import create_app


def test_app_can_be_created() -> None:
    app = create_app()

    assert app is not None


def test_health_returns_200() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
