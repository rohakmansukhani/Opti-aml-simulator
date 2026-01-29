"""
Upload Validator - Enforces size limits for CSV/Excel uploads (Django Native)
"""

from typing import Dict, Any

class UploadValidator:
    """Validates upload size and provides recommendations for large datasets"""
    
    MAX_RECORDS_TRANSACTIONS = 10000
    MAX_RECORDS_CUSTOMERS = 10000
    
    @classmethod
    def validate_size(cls, record_count: int, data_type: str = "transactions") -> Dict[str, Any]:
        """
        Validates if a dataset is within acceptable size limits.
        
        Args:
            record_count: Number of records in the dataset
            data_type: Type of data ("transactions" or "customers")
            
        Returns:
            dict with keys:
                - allowed (bool): Whether upload is permitted
                - count (int): Number of records
                - message (str): User-facing message
                - recommendation (str): Action to take if rejected
        """
        max_records = (cls.MAX_RECORDS_TRANSACTIONS if data_type == "transactions" 
                      else cls.MAX_RECORDS_CUSTOMERS)
        
        if record_count >= max_records:
            return {
                "allowed": False,
                "count": record_count,
                "max_allowed": max_records,
                "message": (
                    f"Dataset too large: {record_count:,} records exceeds limit of {max_records:,}. "
                    f"Please connect your own database for large datasets."
                ),
                "recommendation": "connect_external_db"
            }
        
        return {
            "allowed": True,
            "count": record_count,
            "max_allowed": max_records,
            "message": f"Upload validated: {record_count:,} records"
        }
    
    @classmethod
    def estimate_from_file_size(cls, file_size_bytes: int, data_type: str = "transactions") -> Dict[str, Any]:
        """
        Estimates record count from file size for early validation.
        
        Args:
            file_size_bytes: Size of uploaded file in bytes
            data_type: Type of data
            
        Returns:
            dict with estimated count and pre-validation result
        """
        # Rough estimate: ~200 bytes per transaction record, ~150 bytes per customer record
        bytes_per_record = 200 if data_type == "transactions" else 150
        estimated_count = file_size_bytes // bytes_per_record
        
        max_records = (cls.MAX_RECORDS_TRANSACTIONS if data_type == "transactions" 
                      else cls.MAX_RECORDS_CUSTOMERS)
        
        return {
            "estimated_count": estimated_count,
            "likely_too_large": estimated_count >= max_records,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 2)
        }
