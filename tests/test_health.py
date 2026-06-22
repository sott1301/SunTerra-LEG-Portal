from fastapi.testclient import TestClient

from sunterra_leg_portal.main import app


def test_health_endpoint_describes_running_portal() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "sunterra-leg-portal",
        "version": "0.1.0",
    }
