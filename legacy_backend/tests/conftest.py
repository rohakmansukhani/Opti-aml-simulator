"""
Pytest configuration and fixtures for SAS Simulator tests
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import app and models
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from database import Base, get_db
from models import Transaction, Customer, ScenarioConfig, SimulationRun

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def override_get_db(test_db):
    """Override the get_db dependency"""
    def _override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def client(override_get_db):
    """Create an async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_transactions(test_db):
    """Create sample transactions for testing"""
    transactions = [
        Transaction(
            transaction_id="TXN001",
            customer_id="CUST001",
            transaction_date="2024-01-15",
            transaction_amount=50000,
            transaction_narrative="University tuition payment",
            beneficiary_name="MIT",
            upload_id="test_upload"
        ),
        Transaction(
            transaction_id="TXN002",
            customer_id="CUST001",
            transaction_date="2024-01-16",
            transaction_amount=25000,
            transaction_narrative="Bitcoin purchase",
            beneficiary_name="Binance",
            upload_id="test_upload"
        )
    ]
    
    for txn in transactions:
        test_db.add(txn)
    test_db.commit()
    
    return transactions

@pytest.fixture
def sample_customers(test_db):
    """Create sample customers for testing"""
    customers = [
        Customer(
            customer_id="CUST001",
            customer_name="John Doe",
            customer_type="Individual",
            upload_id="test_upload"
        )
    ]
    
    for cust in customers:
        test_db.add(cust)
    test_db.commit()
    
    return customers
