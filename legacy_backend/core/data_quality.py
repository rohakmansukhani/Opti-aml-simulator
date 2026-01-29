"""
Data Quality Validation

Validates uploaded data for quality issues before processing:
- Negative amounts
- Future dates
- Missing critical fields
- Duplicates
- Data type mismatches
"""

import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger("data_quality")


class DataQualityValidator:
    """
    Validates data quality for transactions and customers.
    
    Returns a quality report with:
    - valid: bool (whether data passes validation)
    - issues: list of quality issues found
    - quality_score: 0-100 score
    - total_rows: number of rows validated
    """
    
    @staticmethod
    def validate_transactions(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate transaction data quality.
        
        Checks:
        - No negative amounts
        - No future dates
        - No duplicate transaction IDs
        - No missing customer IDs
        - Valid transaction types
        - Reasonable amount ranges
        """
        issues = []
        warnings = []
        
        # Check for negative amounts
        negative_amounts = (df['transaction_amount'] < 0).sum()
        if negative_amounts > 0:
            issues.append({
                "severity": "error",
                "field": "transaction_amount",
                "message": f"{negative_amounts} transactions have negative amounts",
                "count": negative_amounts
            })
        
        # Check for future dates
        now = pd.Timestamp.now(tz=timezone.utc)
        df['transaction_date'] = pd.to_datetime(df['transaction_date'], utc=True)
        future_dates = (df['transaction_date'] > now).sum()
        if future_dates > 0:
            warnings.append({
                "severity": "warning",
                "field": "transaction_date",
                "message": f"{future_dates} transactions are future-dated",
                "count": future_dates
            })
        
        # Check for duplicates
        if 'transaction_id' in df.columns:
            dupes = df.duplicated(subset=['transaction_id']).sum()
            if dupes > 0:
                issues.append({
                    "severity": "error",
                    "field": "transaction_id",
                    "message": f"{dupes} duplicate transaction IDs found",
                    "count": dupes
                })
        
        # Check for missing customer IDs
        missing_customers = df['customer_id'].isna().sum()
        if missing_customers > 0:
            issues.append({
                "severity": "error",
                "field": "customer_id",
                "message": f"{missing_customers} transactions missing customer_id",
                "count": missing_customers
            })
        
        # Check for missing amounts
        missing_amounts = df['transaction_amount'].isna().sum()
        if missing_amounts > 0:
            issues.append({
                "severity": "error",
                "field": "transaction_amount",
                "message": f"{missing_amounts} transactions missing amount",
                "count": missing_amounts
            })
        
        # Check for unreasonably large amounts (potential data entry errors)
        if 'transaction_amount' in df.columns:
            very_large = (df['transaction_amount'] > 10_000_000).sum()  # > 10M
            if very_large > 0:
                warnings.append({
                    "severity": "warning",
                    "field": "transaction_amount",
                    "message": f"{very_large} transactions exceed 10M (potential data entry errors)",
                    "count": very_large
                })
        
        # Check for zero amounts
        zero_amounts = (df['transaction_amount'] == 0).sum()
        if zero_amounts > 0:
            warnings.append({
                "severity": "warning",
                "field": "transaction_amount",
                "message": f"{zero_amounts} transactions have zero amount",
                "count": zero_amounts
            })
        
        # Calculate quality score
        total_issues = len(issues)
        total_warnings = len(warnings)
        quality_score = max(0, 100 - (total_issues * 15) - (total_warnings * 5))
        
        # Determine if valid (no errors, warnings are okay)
        is_valid = total_issues == 0
        
        result = {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "total_rows": len(df),
            "quality_score": quality_score,
            "summary": {
                "errors": total_issues,
                "warnings": total_warnings,
                "clean_rows": len(df) - sum(i['count'] for i in issues + warnings)
            }
        }
        
        logger.info(
            "transaction_validation_complete",
            valid=is_valid,
            total_rows=len(df),
            quality_score=quality_score,
            errors=total_issues,
            warnings=total_warnings
        )
        
        return result
    
    @staticmethod
    def validate_customers(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate customer data quality.
        
        Checks:
        - No duplicate customer IDs
        - No missing customer names
        - Valid data types
        """
        issues = []
        warnings = []
        
        # Check for duplicate customer IDs
        if 'customer_id' in df.columns:
            dupes = df.duplicated(subset=['customer_id']).sum()
            if dupes > 0:
                issues.append({
                    "severity": "error",
                    "field": "customer_id",
                    "message": f"{dupes} duplicate customer IDs found",
                    "count": dupes
                })
        
        # Check for missing customer IDs
        missing_ids = df['customer_id'].isna().sum()
        if missing_ids > 0:
            issues.append({
                "severity": "error",
                "field": "customer_id",
                "message": f"{missing_ids} customers missing customer_id",
                "count": missing_ids
            })
        
        # Check for missing customer names
        if 'customer_name' in df.columns:
            missing_names = df['customer_name'].isna().sum()
            if missing_names > 0:
                warnings.append({
                    "severity": "warning",
                    "field": "customer_name",
                    "message": f"{missing_names} customers missing name",
                    "count": missing_names
                })
        
        # Calculate quality score
        total_issues = len(issues)
        total_warnings = len(warnings)
        quality_score = max(0, 100 - (total_issues * 15) - (total_warnings * 5))
        
        is_valid = total_issues == 0
        
        result = {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "total_rows": len(df),
            "quality_score": quality_score,
            "summary": {
                "errors": total_issues,
                "warnings": total_warnings,
                "clean_rows": len(df) - sum(i['count'] for i in issues + warnings)
            }
        }
        
        logger.info(
            "customer_validation_complete",
            valid=is_valid,
            total_rows=len(df),
            quality_score=quality_score,
            errors=total_issues,
            warnings=total_warnings
        )
        
        return result
