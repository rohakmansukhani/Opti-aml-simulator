from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd
import uuid
from datetime import datetime
from models import DataQualityMetric, Transaction, Customer, DataUpload

class DataQualityService:
    def __init__(self, db: Session):
        self.db = db

    def check_upload_quality(self, upload_id: str) -> dict:
        """
        Runs comprehensive data quality checks on a specific upload.
        """
        # 1. Load Data
        upload = self.db.query(DataUpload).filter(DataUpload.upload_id == upload_id).first()
        if not upload:
            raise ValueError("Upload not found")
        
        # Load raw data into DF for analysis
        # Using raw_data column from transactions
        txns = self.db.query(Transaction.raw_data).filter(Transaction.upload_id == upload_id).all()
        if not txns:
             return {"error": "No transaction data found for analysis"}
             
        df = pd.DataFrame([t[0] for t in txns])
        total_rows = len(df)
        
        if total_rows == 0:
             return {"error": "Empty dataset"}

        # 2. Metric: Completeness (% of non-nulls in critical fields)
        critical_fields = ['transaction_id', 'transaction_amount', 'transaction_date', 'customer_id']
        field_issues = {}
        
        null_counts = df[critical_fields].isnull().sum() if set(critical_fields).issubset(df.columns) else df.isnull().sum()
        total_fields_checked = len(null_counts)
        total_possible_values = total_rows * total_fields_checked
        total_nulls = null_counts.sum()
        
        completeness_score = ((total_possible_values - total_nulls) / total_possible_values) * 100
        
        # 3. Metric: Validity (Negative amounts, future dates)
        invalid_count = 0
        if 'transaction_amount' in df.columns:
            # Check for negative amounts (assuming standard AML data shouldn't have them unless reversals, but let's flag)
            # Convert to numeric first
            nums = pd.to_numeric(df['transaction_amount'], errors='coerce')
            invalid_count += (nums < 0).sum()
            
            # Record field issue
            field_issues['transaction_amount'] = {
                "nulls": int(null_counts.get('transaction_amount', 0)),
                "negatives": int((nums < 0).sum())
            }

        validity_score = ((total_rows - invalid_count) / total_rows) * 100
        if validity_score < 0: validity_score = 0
        
        # 4. Metric: Uniqueness (Duplicate Transaction IDs)
        uniqueness_score = 100.0
        if 'transaction_id' in df.columns:
            dupes = df['transaction_id'].duplicated().sum()
            uniqueness_score = ((total_rows - dupes) / total_rows) * 100
        
        # 5. Persist
        metric_id = str(uuid.uuid4())
        metric = DataQualityMetric(
            metric_id=metric_id,
            upload_id=upload_id,
            completeness_score=completeness_score,
            validity_score=validity_score,
            uniqueness_score=uniqueness_score,
            field_level_issues=field_issues,
            row_level_issues={}, # Placeholder for sample bad rows
            created_at=datetime.utcnow()
        )
        
        # Clear old metrics for this upload if any
        self.db.query(DataQualityMetric).filter(DataQualityMetric.upload_id == upload_id).delete()
        
        self.db.add(metric)
        self.db.commit()
        
        return {
            "metric_id": metric_id,
            "scores": {
                "completeness": completeness_score,
                "validity": validity_score,
                "uniqueness": uniqueness_score
            }
        }
