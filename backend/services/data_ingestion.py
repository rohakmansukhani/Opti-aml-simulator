import pandas as pd
import numpy as np
from pydantic import BaseModel, ValidationError, validator
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import io

class TransactionSchema(BaseModel):
    transaction_id: str
    customer_id: str
    account_number: Optional[str] = None
    transaction_date: datetime
    transaction_amount: Decimal
    debit_credit_indicator: str
    transaction_type: str
    channel: str
    transaction_narrative: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_bank: Optional[str] = None

    @validator('debit_credit_indicator')
    def validate_dc_indicator(cls, v):
        if v not in ['D', 'C']:
            raise ValueError('Must be D or C')
        return v

class CustomerSchema(BaseModel):
    customer_id: str
    customer_name: str
    customer_type: str  # Required
    occupation: str     # Required
    annual_income: Decimal # Required for ICICI_44
    account_type: Optional[str] = "Savings"
    risk_score: Optional[int] = 0

class DataIngestionService:
    def _read_file(self, file_content: bytes, filename: str) -> pd.DataFrame:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content))
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            raise ValueError("Unsupported file format")
            
        # Robust Cleaning: Replace Inf/-Inf with NaN, then all NaN with None
        df = df.replace([np.inf, -np.inf], np.nan)
        # Cast to object to allow None replacement for numeric columns
        df = df.astype(object)
        df = df.where(pd.notnull(df), None)
        return df

    def process_transactions_csv(self, file_content: bytes, filename: str = "data.csv") -> List[dict]:
        df = self._read_file(file_content, filename)
        
        # Basic cleaning
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        
        # Pydantic validation
        valid_records = []
        errors = []
        
        for idx, record in enumerate(df.to_dict(orient='records')):
            try:
                # Basic timestamp parsing if needed
                if 'transaction_date' in record and isinstance(record['transaction_date'], str):
                     record['transaction_date'] = pd.to_datetime(record['transaction_date'])
                
                valid_record = TransactionSchema(**record).model_dump()
                valid_records.append(valid_record)
            except ValidationError as e:
                errors.append({
                    "row": idx + 2, # +1 for 0-index, +1 for header
                    "error": str(e),
                    "record": record
                })
        
        return valid_records, errors
        
    def process_customers_csv(self, file_content: bytes, filename: str = "data.csv") -> List[dict]:
        df = self._read_file(file_content, filename)
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        
        valid_records = []
        errors = []
        
        for idx, record in enumerate(df.to_dict(orient='records')):
            try:
                valid_record = CustomerSchema(**record).model_dump()
                valid_records.append(valid_record)
            except ValidationError as e:
                errors.append({
                    "row": idx + 2,
                    "error": str(e),
                    "record": record
                })
                
        return valid_records, errors
