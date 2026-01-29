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

    def process_transactions_csv(self, file_content: bytes, filename: str = "data.csv", upload_id: str = None) -> tuple[List[dict], List[dict], dict]:
        df = self._read_file(file_content, filename)
        
        # ✅ Generate upload_id and prefix EARLY
        import uuid
        if upload_id is None:
            upload_id = str(uuid.uuid4())
        upload_prefix = upload_id[:8]  # First 8 chars for prefix
        
        # Best-effort header mapping
        mapping = {
            'id': 'transaction_id',
            'txn_id': 'transaction_id',
            'transaction_id': 'transaction_id',
            'ref': 'transaction_id',
            'date': 'transaction_date',
            'txn_date': 'transaction_date',
            'transaction_date': 'transaction_date',
            'amount': 'transaction_amount',
            'txn_amt': 'transaction_amount',
            'transaction_amount': 'transaction_amount',
            'cust_id': 'customer_id',
            'customer_id': 'customer_id',
            'client_id': 'customer_id',
            'indicator': 'debit_credit_indicator',
            'dc': 'debit_credit_indicator',
            'd/c': 'debit_credit_indicator',
        }
        
        valid_records = []
        errors = []
        
        for idx, row in enumerate(df.to_dict(orient='records')):
            try:
                # ✅ STEP 1: Build raw_data, excluding ID fields to avoid duplicates
                raw_data = {}
                original_customer_id = None
                original_transaction_id = None
                
                for k, v in row.items():
                    clean_k = str(k).lower().strip().replace(' ', '_')
                    target_k = mapping.get(clean_k, clean_k)
                    
                    # ✅ Extract and skip ID fields (they're table columns, not raw_data)
                    if target_k == 'customer_id':
                        original_customer_id = str(v)
                        continue  # Don't add to raw_data
                    elif target_k == 'transaction_id':
                        original_transaction_id = str(v)
                        continue  # Don't add to raw_data
                    
                    # Add all other fields to raw_data
                    if v is not None:  # Skip None/NaN
                        # Convert types for JSON serialization
                        if isinstance(v, (np.integer, np.floating)):
                            raw_data[clean_k] = float(v) if isinstance(v, np.floating) else int(v)
                        elif isinstance(v, pd.Timestamp):
                            raw_data[clean_k] = v.isoformat()
                        elif isinstance(v, Decimal):
                            raw_data[clean_k] = float(v)
                        else:
                            raw_data[clean_k] = str(v)
                
                # ✅ Store original IDs separately in raw_data
                if original_customer_id:
                    raw_data['original_customer_id'] = original_customer_id
                if original_transaction_id:
                    raw_data['original_transaction_id'] = original_transaction_id
                
                # Validate required fields exist
                if not original_transaction_id or not original_customer_id:
                    raise ValueError(f"Missing required fields: transaction_id or customer_id")
                
                # ✅ STEP 2: Build processed_row with prefixed customer_id
                processed_row = {
                    'transaction_id': original_transaction_id,
                    'customer_id': f"{upload_prefix}_{original_customer_id}",
                    'upload_id': upload_id,
                    'raw_data': raw_data
                }
                
                valid_records.append(processed_row)
                
            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})
        
        # Build field index from raw_data
        computed_index = self._build_field_index(valid_records, 'transactions')
        
        return valid_records, errors, computed_index
        
    def process_customers_csv(self, file_content: bytes, filename: str = "data.csv", upload_id: str = None) -> tuple[List[dict], List[dict], dict, List[dict]]:
        df = self._read_file(file_content, filename)
        
        # ✅ Generate upload_id and prefix EARLY
        import uuid
        if upload_id is None:
            upload_id = str(uuid.uuid4())
        upload_prefix = upload_id[:8]  # First 8 chars for prefix
        
        mapping = {
            'cust_id': 'customer_id',
            'customer_id': 'customer_id',
            'client_id': 'customer_id',
            'id': 'customer_id',
        }
        
        valid_records = []
        errors = []
        
        for idx, row in enumerate(df.to_dict(orient='records')):
            try:
                # ✅ Build raw_data, excluding customer_id to avoid duplicates
                raw_data = {}
                original_customer_id = None
                
                for k, v in row.items():
                    clean_k = str(k).lower().strip().replace(' ', '_')
                    target_k = mapping.get(clean_k, clean_k)
                    
                    # ✅ Extract and skip customer_id (it's a table column)
                    if target_k == 'customer_id':
                        original_customer_id = str(v)
                        continue  # Don't add to raw_data
                    
                    # Add all other fields to raw_data
                    if v is not None:
                        if isinstance(v, (np.integer, np.floating)):
                            raw_data[clean_k] = float(v) if isinstance(v, np.floating) else int(v)
                        elif isinstance(v, pd.Timestamp):
                            raw_data[clean_k] = v.isoformat()
                        elif isinstance(v, Decimal):
                            raw_data[clean_k] = float(v)
                        else:
                            raw_data[clean_k] = str(v)
                
                # ✅ Store original customer_id in raw_data
                if original_customer_id:
                    raw_data['original_customer_id'] = original_customer_id
                else:
                    raise ValueError("Missing customer_id")
                
                # Build processed_row with prefixed customer_id
                processed_row = {
                    'customer_id': f"{upload_prefix}_{original_customer_id}",
                    'upload_id': upload_id,
                    'raw_data': raw_data
                }
                
                valid_records.append(processed_row)
                
            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})
        
        computed_index = self._build_field_index(valid_records, 'customers')
        extracted_accounts = self._extract_accounts_from_customers(valid_records, upload_id, upload_prefix)
        
        return valid_records, errors, computed_index, extracted_accounts

    def _extract_accounts_from_customers(self, customer_records: List[dict], upload_id: str, upload_prefix: str) -> List[dict]:
        """
        Generates master Account records from Customer data.
        """
        accounts = []
        import uuid
        from datetime import datetime
        
        for cust in customer_records:
            # We assume 1 customer row = 1 primary account for now
            # In real world, one customer can have multiple accounts (master-detail),
            # but usually the CSV is flattened.
            
            # Generate or derive Account ID
            # If account_number exists in raw_data, use it to seed ID? 
            # ideally we want consistent IDs if re-uploaded.
            # But for now, new UUIDs are safer to avoid collisions unless we have a strict key.
            
            raw = cust.get('raw_data', {})
            acc_num = raw.get('account_number')
            
            # Generate account_id from raw data or create new
            original_account_id = raw.get('account_id') or raw.get('account_number') or str(uuid.uuid4())
            
            # Basic Account Dict
            account_data = {
                "account_id": f"{upload_prefix}_{original_account_id}",  # ✅ PREFIX account_id
                "customer_id": cust['customer_id'],  # Already prefixed from customer processing
                "upload_id": upload_id,  # ✅ Add upload_id
                "account_number": acc_num,
                "account_type": cust.get('account_type', 'Savings'),
                "account_status": 'Active',
                "currency_code": raw.get('currency', 'GBP'),
                "account_open_date": datetime.utcnow(),
                "risk_rating": 'LOW',
                "is_pep": False,
                "current_balance": 0,
                "raw_data": {
                    'original_account_id': original_account_id,  # ✅ Store original
                    'original_customer_id': raw.get('original_customer_id')  # Pass through
                }
            }
            
            # Try to populate more fields from raw_data if available
            if 'open_date' in raw:
                try: account_data['account_open_date'] = pd.to_datetime(raw['open_date'])
                except: pass
            
            if 'balance' in raw:
                try: account_data['current_balance'] = Decimal(str(raw['balance']))
                except: pass
                
            if 'risk_rating' in raw:
                account_data['risk_rating'] = raw['risk_rating']
                
            if 'status' in raw:
                account_data['account_status'] = raw['status']
                
            accounts.append(account_data)
            
        return accounts

    def _build_field_index(self, records: List[dict], table_name: str) -> dict:
        """
        Extract all unique field values and build searchable index stats.
        Returns a dict structure to be used for creating FieldMetadata and FieldValueIndex.
        """
        from collections import Counter
        
        # Group records by field
        field_values = {}  # {field_name: {value: count}}
        field_samples = {} # {field_name: [sample_values]}
        
        for record in records:
            # We index data from 'raw_data' (dynamic fields) AND specific core columns users filter on.
            # Core columns to index:
            core_cols = []
            if table_name == 'transactions':
                core_cols = ['transaction_type', 'channel', 'debit_credit_indicator', 'beneficiary_bank']
            elif table_name == 'customers':
                core_cols = ['customer_type', 'occupation', 'account_type']
            
            # Combine raw_data and core columns
            data_to_index = record.get('raw_data', {}).copy()
            for col in core_cols:
                if record.get(col):
                    data_to_index[col] = record.get(col)
            
            for field_name, field_value in data_to_index.items():
                if field_name not in field_values:
                    field_values[field_name] = Counter()
                
                # Convert to string for indexing, but keep None as None
                str_value = str(field_value) if field_value is not None else None
                if str_value:
                    field_values[field_name][str_value] += 1
        
        # Build Index Result
        index_result = {}
        total_records = len(records)
        
        for field_name, value_counts in field_values.items():
            field_type = self._infer_field_type(list(value_counts.keys()))
            distinct_count = len(value_counts)
            
            metadata = {
                "field_name": field_name,
                "field_type": field_type,
                "total_records": total_records,
                "non_null_count": sum(value_counts.values()),
                "null_count": total_records - sum(value_counts.values()),
                "distinct_count": distinct_count,
                "recommended_operators": self._get_recommended_operators(field_type),
                "sample_values": list(value_counts.keys())[:10]
            }
            
            values = []
            # Build value index (only if distinct values < 1000)
            if distinct_count < 1000:  # Don't index high-cardinality fields
                for value, count in value_counts.items():
                    percentage = (count / total_records) * 100
                    values.append({
                        "field_value": value,
                        "value_count": count,
                        "value_percentage": round(percentage, 2)
                    })
            
            index_result[field_name] = {
                "metadata": metadata,
                "values": values
            }
            
        return index_result
    
    def _infer_field_type(self, sample_values: List[str]) -> str:
        """Infer field type from values"""
        samples = sample_values[:100]
        if not samples: return 'text'
        
        # Check if all values are numeric
        try:
            [float(v) for v in samples]
            return 'numeric'
        except:
            pass
        
        # Check if all values are dates (simple check)
        # Using pandas to datetime is robust but slow for many checks. 
        # For ingestion, reliability > speed here.
        try:
            # Only checking if *valid* samples parse. If it fails, it's text.
             # We assume if 90% parse, it's date? No, be strict for now.
            [pd.to_datetime(v) for v in samples]
            return 'date'
        except:
            pass
        
        # Check if boolean
        unique_values = set(str(v).lower() for v in samples)
        if unique_values.issubset({'true', 'false', '1', '0', 'yes', 'no'}):
            return 'boolean'
        
        return 'text'
    
    def _get_recommended_operators(self, field_type: str) -> list:
        """Get operators that make sense for this field type"""
        if field_type == 'numeric':
            return ['equals', 'not_equals', 'greater_than', 'less_than', 'greater_or_equal', 'less_or_equal', 'between']
        elif field_type == 'date':
            return ['equals', 'greater_than', 'less_than', 'between']
        elif field_type == 'boolean':
            return ['equals']
        else:  # text
            return ['equals', 'not_equals', 'in', 'contains', 'starts_with', 'ends_with']
