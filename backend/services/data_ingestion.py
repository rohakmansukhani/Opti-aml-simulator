import pandas as pd
import numpy as np
from pydantic import BaseModel, ValidationError, validator
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import io

# IDs are now mandatory again as they are PKs
class TransactionSchema(BaseModel):
    transaction_id: str
    customer_id: str
    account_number: Optional[str] = None
    transaction_date: Optional[datetime] = None
    transaction_amount: Optional[Decimal] = None
    debit_credit_indicator: Optional[str] = None
    transaction_type: Optional[str] = None
    channel: Optional[str] = None
    transaction_narrative: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_bank: Optional[str] = None
    raw_data: Optional[dict] = None

class CustomerSchema(BaseModel):
    customer_id: str
    customer_name: Optional[str] = None
    customer_type: Optional[str] = None
    occupation: Optional[str] = None
    annual_income: Optional[Decimal] = None
    account_type: Optional[str] = None
    risk_score: Optional[int] = 0
    raw_data: Optional[dict] = None

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
        
        # Best-effort header mapping
        mapping = {
            'id': 'transaction_id',
            'txn_id': 'transaction_id',
            'transaction_id': 'transaction_id',
            'ref': 'transaction_id',
            'reference': 'transaction_id',
            'txn_ref': 'transaction_id',
            'date': 'transaction_date',
            'txn_date': 'transaction_date',
            'transaction_date': 'transaction_date',
            'amount': 'transaction_amount',
            'txn_amt': 'transaction_amount',
            'transaction_amount': 'transaction_amount',
            'value': 'transaction_amount',
            'cust_id': 'customer_id',
            'customer_id': 'customer_id',
            'client_id': 'customer_id',
            'party_id': 'customer_id',
            'indicator': 'debit_credit_indicator',
            'dc': 'debit_credit_indicator',
            'd/c': 'debit_credit_indicator',
            'type': 'transaction_type',
            'txn_type': 'transaction_type',
        }
        
        known_fields = set(TransactionSchema.model_fields.keys())
        valid_records = []
        errors = []
        
        for idx, row in enumerate(df.to_dict(orient='records')):
            try:
                processed_row = {}
                raw_data = {}
                
                for k, v in row.items():
                    clean_k = str(k).lower().strip().replace(' ', '_')
                    target_k = mapping.get(clean_k, clean_k)
                    
                    if target_k in known_fields:
                        # Attempt type conversion for known fields
                        if target_k == 'transaction_date' and v:
                            try: processed_row[target_k] = pd.to_datetime(v)
                            except: processed_row[target_k] = None
                        elif target_k == 'transaction_amount' and v is not None:
                            try: processed_row[target_k] = Decimal(str(v))
                            except: processed_row[target_k] = None
                        else:
                            processed_row[target_k] = v
                    else:
                        raw_data[k] = v
                
                processed_row['raw_data'] = raw_data
                
                # Validation will now fail if transaction_id or customer_id is missing
                valid_record = TransactionSchema(**processed_row).model_dump()
                valid_records.append(valid_record)
            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})
        
        return valid_records, errors
        
    def process_customers_csv(self, file_content: bytes, filename: str = "data.csv") -> List[dict]:
        df = self._read_file(file_content, filename)
        
        mapping = {
            'cust_id': 'customer_id',
            'customer_id': 'customer_id',
            'client_id': 'customer_id',
            'party_id': 'customer_id',
            'id': 'customer_id',
            'name': 'customer_name',
            'customer_name': 'customer_name',
            'income': 'annual_income',
            'salary': 'annual_income',
            'annual_income': 'annual_income'
        }
        
        known_fields = set(CustomerSchema.model_fields.keys())
        valid_records = []
        errors = []
        
        for idx, row in enumerate(df.to_dict(orient='records')):
            try:
                processed_row = {}
                raw_data = {}
                
                for k, v in row.items():
                    clean_k = str(k).lower().strip().replace(' ', '_')
                    target_k = mapping.get(clean_k, clean_k)
                    
                    if target_k in known_fields:
                        if target_k == 'annual_income' and v is not None:
                             try: processed_row[target_k] = Decimal(str(v))
                             except: processed_row[target_k] = None
                        else:
                            processed_row[target_k] = v
                    else:
                        raw_data[k] = v
                
                processed_row['raw_data'] = raw_data
                
                # Validation will fail if customer_id is missing
                valid_record = CustomerSchema(**processed_row).model_dump()
                valid_records.append(valid_record)
            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})
                
        return valid_records, errors
