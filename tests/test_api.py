"""
Integration Tests for the ShelfSense REST API.

Uses FastAPI's TestClient with an in-memory SQLite database so tests
don't pollute the real database.

Run with:
    pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_db
from app import app
from models.database import Base


# ── Test database setup ─────────────────────────────────────────────────

# In-memory SQLite for isolated tests.
# StaticPool ensures all connections share the SAME in-memory database;
# without it, create_all and session queries would use different databases.
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_TEST_ENGINE, autoflush=False, autocommit=False)


def _override_get_db():
    """Yield a test DB session instead of the real one."""
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


# Override the dependency
app.dependency_overrides[get_db] = _override_get_db

client = TestClient(app)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop them after."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


# ── Health check ────────────────────────────────────────────────────────

def test_health_check():
    """GET / should return service info."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ShelfSense"


# ── Zone CRUD lifecycle ────────────────────────────────────────────────

def test_create_zone():
    """POST /api/zones should create a zone and return 201."""
    payload = {
        "zone_name": "Zone A",
        "product_name": "Olpers Milk",
        "x": 100,
        "y": 50,
        "width": 200,
        "height": 150,
    }
    response = client.post("/api/zones", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["zone_name"] == "Zone A"
    assert data["product_name"] == "Olpers Milk"
    assert data["x"] == 100
    assert data["id"] is not None


def test_list_zones_empty():
    """GET /api/zones should return an empty list when no zones exist."""
    response = client.get("/api/zones")
    assert response.status_code == 200
    assert response.json() == []


def test_full_crud_lifecycle():
    """Test create → read → update → read → delete → verify 404."""
    # CREATE
    create_resp = client.post("/api/zones", json={
        "zone_name": "Zone B",
        "product_name": "Water Bottles",
        "x": 0, "y": 0, "width": 100, "height": 100,
    })
    assert create_resp.status_code == 201
    zone_id = create_resp.json()["id"]

    # READ
    get_resp = client.get(f"/api/zones/{zone_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["zone_name"] == "Zone B"

    # UPDATE
    update_resp = client.put(f"/api/zones/{zone_id}", json={
        "zone_name": "Zone B (Updated)",
        "product_name": "Sparkling Water",
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["zone_name"] == "Zone B (Updated)"
    assert update_resp.json()["product_name"] == "Sparkling Water"
    # Unchanged fields should remain
    assert update_resp.json()["width"] == 100

    # READ again
    get_resp2 = client.get(f"/api/zones/{zone_id}")
    assert get_resp2.json()["zone_name"] == "Zone B (Updated)"

    # DELETE
    del_resp = client.delete(f"/api/zones/{zone_id}")
    assert del_resp.status_code == 200
    assert "deleted" in del_resp.json()["detail"]

    # VERIFY 404
    get_resp3 = client.get(f"/api/zones/{zone_id}")
    assert get_resp3.status_code == 404


# ── Error cases ─────────────────────────────────────────────────────────

def test_get_nonexistent_zone():
    """GET /api/zones/9999 should return 404."""
    response = client.get("/api/zones/9999")
    assert response.status_code == 404


def test_delete_nonexistent_zone():
    """DELETE /api/zones/9999 should return 404."""
    response = client.delete("/api/zones/9999")
    assert response.status_code == 404


def test_update_nonexistent_zone():
    """PUT /api/zones/9999 should return 404."""
    response = client.put("/api/zones/9999", json={"zone_name": "Nope"})
    assert response.status_code == 404


def test_create_zone_invalid_data():
    """POST /api/zones with missing required fields should return 422."""
    response = client.post("/api/zones", json={"zone_name": "Incomplete"})
    assert response.status_code == 422


# ── Status endpoint ────────────────────────────────────────────────────

def test_status_empty():
    """GET /api/status should return empty zones when no analysis has run."""
    response = client.get("/api/status")
    assert response.status_code == 200

    data = response.json()
    assert data["zones"] == []
    assert data["summary"] == {"FULL": 0, "LOW": 0, "EMPTY": 0}
    assert data["analyzed_at"] is None


# ── References endpoint ────────────────────────────────────────────────

def test_list_references():
    """GET /api/references should return a list of filenames."""
    response = client.get("/api/references")
    assert response.status_code == 200
    assert "references" in response.json()


def test_delete_nonexistent_reference():
    """DELETE /api/references/nope.png should return 404."""
    response = client.delete("/api/references/nope.png")
    assert response.status_code == 404


def test_delete_reference_path_traversal():
    """DELETE with path traversal should return 400."""
    response = client.delete("/api/references/..config.py")
    assert response.status_code == 400


# ── Analysis endpoint (error case — no zones) ──────────────────────────

def test_analyze_without_zones():
    """POST /api/analyze with no zones defined should return 422."""
    # Create a tiny valid PNG image (1x1 pixel)
    import cv2
    import numpy as np
    import io

    img = np.zeros((10, 10, 3), dtype=np.uint8)
    _, buffer = cv2.imencode(".png", img)
    image_bytes = buffer.tobytes()

    response = client.post(
        "/api/analyze",
        files={"image": ("test.png", image_bytes, "image/png")},
    )
    # Should fail because no zones exist
    assert response.status_code == 422
    assert "No zones defined" in response.json()["detail"]
