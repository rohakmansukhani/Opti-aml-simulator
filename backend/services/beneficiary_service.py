from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
from datetime import datetime
from decimal import Decimal
import pandas as pd

from models import Transaction, BeneficiaryHistory

class BeneficiaryService:
    def __init__(self, db: Session):
        self.db = db
        
    def build_history_for_upload(self, upload_id: str):
        """
        Scans transactions for a specific upload and builds/updates beneficiary profiles.
        This is an expensive operation and should be run asynchronously.
        """
        # 1. Fetch all transactions with beneficiaries
        # We need raw_data -> beneficiary_name
        # OR use aggregation queries if possible. 
        # Since raw_data is JSONB, we can query it.
        
        # Aggregate by Beneficiary Name (Normalized)
        # Using Pandas mostly because JSONB aggregation in SQL can be complex to standardize names
        # But for performance on 10L rows, SQL is better.
        # Let's try hybrid: Fetch essential cols
        
        try:
            # Delete existing history for this upload to allow re-runs
            self.db.query(BeneficiaryHistory).filter(BeneficiaryHistory.upload_id == upload_id).delete()
            
            # Fetch Data
            # Note: We rely on 'raw_data' having 'beneficiary_name' or similar
            # Ideally we extract this during ingestion into a column, but if not, we do it here.
            # Assuming schema-agnostic means we trust the mapping in search/indexing
            
            # Let's pull relevant columns from Transaction
            query = self.db.query(Transaction.raw_data, Transaction.created_at).filter(Transaction.upload_id == upload_id)
            
            # Use pandas for heavy lifting of normalization
            df = pd.read_sql(query.statement, self.db.bind)
            
            if df.empty:
                return {"status": "no_data"}
            
            # Extract beneficiary
            def get_ben(row):
                raw = row['raw_data']
                return raw.get('beneficiary_name') or raw.get('beneficiary') or raw.get('counterparty')
                
            def get_amount(row):
                raw = row['raw_data']
                val = raw.get('transaction_amount') or raw.get('amount') or 0
                try: return float(val)
                except: return 0.0
                
            df['beneficiary_name'] = df.apply(get_ben, axis=1)
            df['amount'] = df.apply(get_amount, axis=1)
            df['date'] = pd.to_datetime(df['created_at']) # or transaction_date from raw_data
            
            # Filter nulls
            df = df.dropna(subset=['beneficiary_name'])
            
            # Group by Beneficiary
            # Stats: total_txns, total_amt, first_seen, last_seen, std_dev, avg_days
            stats = df.groupby('beneficiary_name').agg({
                'amount': ['count', 'sum', 'std'],
                'date': ['min', 'max']
            })
            
            # Flatten columns
            stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
            stats = stats.reset_index()
            
            # Prepare Objects
            history_records = []
            for _, row in stats.iterrows():
                name = row['beneficiary_name']
                count = row['amount_count']
                total_amt = row['amount_sum']
                std_dev = row['amount_std'] if not pd.isna(row['amount_std']) else 0
                first = row['date_min']
                last = row['date_max']
                
                # Avg Days between txns (simple heuristic: duration / count-1)
                duration = (last - first).days
                avg_days = 0
                if count > 1:
                    avg_days = duration / (count - 1)
                
                record = {
                    "history_id": str(uuid.uuid4()),
                    "beneficiary_name": str(name)[:255],
                    "upload_id": upload_id,
                    "total_transactions": int(count),
                    "total_amount": Decimal(str(total_amt)),
                    "first_seen": first,
                    "last_seen": last,
                    "std_dev_amount": float(std_dev),
                    "avg_days_between_txns": float(avg_days)
                }
                history_records.append(record)
                
            # Bulk Insert
            if history_records:
                self.db.bulk_insert_mappings(BeneficiaryHistory, history_records)
                self.db.commit()
                
            return {"status": "success", "count": len(history_records)}
            
        except Exception as e:
            self.db.rollback()
            print(f"Beneficiary analysis failed: {e}")
            raise e
