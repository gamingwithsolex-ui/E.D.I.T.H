import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from edith.server.auth_middleware import AuthMiddleware

@pytest.fixture
def auth_app():
    app = FastAPI()
    app.add_middleware(AuthMiddleware, api_key="secret_key")
    
    @app.get("/v1/test")
    def read_test():
        return {"status": "ok"}
        
    @app.get("/public")
    def read_public():
        return {"status": "ok"}
        
    return app

def test_auth_middleware_valid_key(auth_app):
    client = TestClient(auth_app)
    response = client.get("/v1/test", headers={"Authorization": "Bearer secret_key"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_auth_middleware_invalid_key(auth_app):
    client = TestClient(auth_app)
    response = client.get("/v1/test", headers={"Authorization": "Bearer wrong_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}

def test_auth_middleware_missing_header(auth_app):
    client = TestClient(auth_app)
    response = client.get("/v1/test")
    assert response.status_code == 401
    assert response.json() == {"detail": "Missing Authorization header"}

def test_auth_middleware_public_route(auth_app):
    client = TestClient(auth_app)
    response = client.get("/public")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
