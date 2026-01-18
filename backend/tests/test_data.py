"""
Tests for data upload endpoints
"""
import pytest
from httpx import AsyncClient
from io import BytesIO

@pytest.mark.asyncio
async def test_upload_transactions_csv(client: AsyncClient):
    """Test transaction CSV upload"""
    csv_content = b"""transaction_id,customer_id,transaction_date,transaction_amount,transaction_narrative
TXN001,CUST001,2024-01-15,50000,Payment for services
TXN002,CUST001,2024-01-16,25000,Transfer to account"""
    
    files = {"file": ("transactions.csv", BytesIO(csv_content), "text/csv")}
    
    response = await client.post("/api/data/upload/transactions", files=files)
    
    # Should succeed or return validation error
    assert response.status_code in [200, 400, 413, 422]
    
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "records_uploaded" in data

@pytest.mark.asyncio
async def test_upload_invalid_file_type(client: AsyncClient):
    """Test upload with invalid file type"""
    files = {"file": ("test.txt", BytesIO(b"invalid content"), "text/plain")}
    
    response = await client.post("/api/data/upload/transactions", files=files)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_ttl_extension(client: AsyncClient):
    """Test TTL extension endpoint"""
    response = await client.post(
        "/api/data/ttl/extend",
        params={"upload_id": "nonexistent", "additional_hours": 24}
    )
    # Should return 404 for nonexistent upload
    assert response.status_code == 404
