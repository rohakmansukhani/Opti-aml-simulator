"""
Tests for authentication and authorization
"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_protected_endpoint_without_auth(client: AsyncClient):
    """Test that protected endpoints require authentication"""
    response = await client.get("/api/rules/scenarios")
    # Should return 401 or 403 without auth
    assert response.status_code in [401, 403]

@pytest.mark.asyncio
async def test_database_connection_validation(client: AsyncClient):
    """Test database connection validation"""
    # Test with invalid URL
    response = await client.post(
        "/api/connect",
        json={"db_url": "mysql://invalid"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    
    # Test with non-PostgreSQL URL
    response = await client.post(
        "/api/connect",
        json={"db_url": "mongodb://localhost"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "PostgreSQL" in data["message"]
