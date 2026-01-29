"""
Tests for simulation endpoints
"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    """Test Prometheus metrics endpoint"""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

@pytest.mark.asyncio
async def test_simulation_run_validation(client: AsyncClient):
    """Test simulation run with invalid data"""
    response = await client.post(
        "/api/simulation/run",
        json={
            "scenarios": [],  # Empty scenarios should fail
            "run_type": "baseline"
        }
    )
    # Should return validation error or 422
    assert response.status_code in [400, 422]

@pytest.mark.asyncio
async def test_check_schema_endpoint(client: AsyncClient):
    """Test schema validation endpoint"""
    response = await client.post(
        "/api/simulation/check-schema",
        json={
            "scenarios": ["ICICI_01"],
            "run_type": "baseline"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "missing_fields" in data
