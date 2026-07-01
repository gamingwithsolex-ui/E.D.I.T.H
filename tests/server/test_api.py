import pytest
from fastapi.testclient import TestClient
from edith.server.api_routes import budget_router
from fastapi import FastAPI

@pytest.fixture
def api_app():
    app = FastAPI()
    app.include_router(budget_router)
    return app

def test_budget_limits_endpoint(api_app):
    client = TestClient(api_app)
    
    # Test setting budget limits
    response = client.put(
        "/v1/budget/limits",
        json={"max_tokens_per_day": 10000}
    )
    assert response.status_code == 200
    assert response.json()["limits"]["max_tokens_per_day"] == 10000
    
    # Test getting budget
    response = client.get("/v1/budget")
    assert response.status_code == 200
    assert response.json()["limits"]["max_tokens_per_day"] == 10000
