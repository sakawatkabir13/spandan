from unittest.mock import patch


async def test_database_failure_is_json_503_and_liveness_remains_available(client):
    with patch("app.main.engine") as engine:
        engine.connect.side_effect = RuntimeError("Synthetic database outage")
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "NOT_READY"
    assert (await client.get("/health/live")).status_code == 200
