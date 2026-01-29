import csv
import io
import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Tuple, Generator, Any
from datetime import datetime
import json

from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError

from simulation.models import (
    DataUpload, 
    Transaction, 
    Customer, 
    Account
)

# Use a named logger for better filtering and configuration
logger = logging.getLogger(__name__)

class DataIngestionService:
    """
    Service responsible for ingesting, validating, and persisting AML Transaction and Customer data.
    
    Design Principles:
    - Memory Efficiency: Uses generators and chunked processing for large files.
    - Atomicity: Transactions are all-or-nothing per file upload to maintain data integrity.
    - Robustness: Handles malformed date/numeric formats gracefully with logging.
    - Air-Gap Safe: No external API calls; purely local verification and parsing.
    """

    BATCH_SIZE = 1000  # Number of records to insert in a single SQL statement

    def process_upload(self, file_obj: io.BytesIO, filename: str, dataset_name: str = None, existing_upload: DataUpload = None) -> DataUpload:
        """
        Main entry point for processing an uploaded CSV file.
        Detects file type (Transaction vs Customer) based on headers and delegates processing.
        
        Args:
            file_obj: File content as BytesIO
            filename: Original filename
            dataset_name: Optional name for this dataset (e.g., "January 2024")
            existing_upload: Optional existing DataUpload record to add data to
        """
        timestamp = timezone.now()
        
        # Decode file stream safely
        decoded_file = file_obj.read().decode('utf-8-sig').splitlines()
        reader = csv.DictReader(decoded_file)
        
        headers = [h.lower().strip() for h in reader.fieldnames or []]
        logger.debug(f"Detected headers: {headers}")

        if existing_upload:
            upload_record = existing_upload
            # Append filename if not already present or if it's a new file in the batch
            if upload_record.filename:
                if filename not in upload_record.filename:
                    upload_record.filename = f"{upload_record.filename}, {filename}"
            else:
                upload_record.filename = filename
            upload_record.save()
        else:
            upload_id = uuid.uuid4()
            # Create the Master Record
            upload_record = DataUpload.objects.create(
                upload_id=upload_id,
                filename=filename,
                dataset_name=dataset_name,
                upload_timestamp=timestamp,
                status="processing"
            )
        
        logger.info(f"Processing file: {filename} for Upload ID: {upload_record.upload_id}")

        try:
            # Check File Type Strategy
            if 'transaction_id' in headers or 'txn_id' in headers:
                self._process_transactions(reader, upload_record)
            elif 'customer_id' in headers or 'cust_id' in headers:
                self._process_customers(reader, upload_record)
            else:
                raise Exception(f"Unknown CSV format. Headers found: {headers}")

            upload_record.status = "completed"
            upload_record.save()
            logger.info(f"File {filename} processing completed for Upload ID: {upload_record.upload_id}")
            return upload_record

        except Exception as e:
            logger.error(f"Upload failed for {filename}: {str(e)}", exc_info=True)
            # If we created/used a record, mark it as failed
            if 'upload_record' in locals():
                upload_record.status = "failed"
                upload_record.save()
            raise e

    @transaction.atomic
    def _process_transactions(self, reader: csv.DictReader, upload: DataUpload) -> None:
        """
        Process transaction records with bulk creation for performance.
        """
        tx_objects = []
        row_count = 0
        
        for row in reader:
            normalized_row = {k.lower().strip(): v for k, v in row.items()}
            
            try:
                # Basic Mapping
                tx_id = normalized_row.get('transaction_id') or normalized_row.get('txn_id') or str(uuid.uuid4())
                cust_id = normalized_row.get('customer_id') or normalized_row.get('cust_id') or normalized_row.get('client_id')
                
                if not cust_id:
                    logger.warning(f"Skipping row {row_count}: Missing Customer ID")
                    continue

                # Ensure customer link exists (or create partial/dummy customer if allowed)
                # For strict integrity, we might require customer to exist. 
                # Here, we get_or_create to ensure FK satisfaction.
                customer, _ = Customer.objects.get_or_create(
                    customer_id=cust_id,
                    defaults={'upload': upload, 'raw_data': {'auto_created': True}}
                )

                # Parse Date
                date_str = normalized_row.get('date') or normalized_row.get('transaction_date')
                parsed_date = self._parse_date(date_str) or timezone.now()

                # Ensure timezone awareness
                if timezone.is_naive(parsed_date):
                    parsed_date = timezone.make_aware(parsed_date)

                # Convert numeric strings for JSON querying
                row_data = {k: self._cast_value(v) for k, v in row.items()}

                # Build Object
                tx = Transaction(
                    transaction_id=tx_id,
                    customer=customer,
                    upload=upload,
                    created_at=parsed_date,
                    raw_data=row_data # Store dict
                )
                tx_objects.append(tx)
                row_count += 1

                # Bulk Insert Window
                if len(tx_objects) >= self.BATCH_SIZE:
                    try:
                        Transaction.objects.bulk_create(tx_objects)
                    except IntegrityError:
                        # Handle duplicates individually for Oracle
                        for tx in tx_objects:
                            try:
                                tx.save()
                            except IntegrityError:
                                pass  # Skip duplicates
                    tx_objects = []

            except Exception as e:
                logger.warning(f"Failed to process row {row_count}: {e}")
                continue

        # Flush remaining
        if tx_objects:
            try:
                Transaction.objects.bulk_create(tx_objects)
            except IntegrityError:
                # Handle duplicates individually for Oracle
                for tx in tx_objects:
                    try:
                        tx.save()
                    except IntegrityError:
                        pass  # Skip duplicates
        
        # Update Stats
        upload.record_count_transactions = row_count
        upload.save()

    @transaction.atomic
    def _process_customers(self, reader: csv.DictReader, upload: DataUpload) -> None:
        """
        Process customer records. accounts for existing customers by updating them 
        if necessary or ignoring conflicts.
        """
        cust_objects = []
        row_count = 0

        for row in reader:
            normalized_row = {k.lower().strip(): v for k, v in row.items()}
            
            try:
                cust_id = normalized_row.get('customer_id') or normalized_row.get('cust_id')
                if not cust_id:
                    continue

                # Convert numeric strings for JSON querying
                row_data = {k: self._cast_value(v) for k, v in row.items()}

                cust = Customer(
                    customer_id=cust_id,
                    upload=upload,
                    raw_data=row_data, # Store dict directly in JSONField
                    created_at=timezone.now()
                )
                cust_objects.append(cust)
                row_count += 1

                if len(cust_objects) >= self.BATCH_SIZE:
                    try:
                        Customer.objects.bulk_create(cust_objects)
                    except IntegrityError:
                        # Handle duplicates for Oracle - Update existing ones with new raw_data
                        for cust in cust_objects:
                            try:
                                cust.save()
                            except IntegrityError:
                                # Update existing record instead of skipping
                                Customer.objects.filter(customer_id=cust.customer_id).update(
                                    raw_data=cust.raw_data,
                                    upload=upload
                                )
                    cust_objects = []

            except Exception as e:
                logger.warning(f"Failed to process customer row {row_count}: {e}")

        if cust_objects:
            try:
                Customer.objects.bulk_create(cust_objects)
            except IntegrityError:
                for cust in cust_objects:
                    try:
                        cust.save()
                    except IntegrityError:
                        Customer.objects.filter(customer_id=cust.customer_id).update(
                            raw_data=cust.raw_data,
                            upload=upload
                        )
            
        upload.record_count_customers = row_count
        upload.save()

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Robust date parsing trying multiple formats.
        """
        if not date_str:
            return None
            
        formats = [
            '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', 
            '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None

    def _cast_value(self, val: Any) -> Any:
        """Helper to cast CSV string values to appropriate Python types for JSON storage."""
        if not isinstance(val, str):
            return val
        
        val_strip = val.strip()
        if not val_strip:
            return None
            
        # Try int
        try:
            return int(val_strip)
        except ValueError:
            pass
            
        # Try float
        try:
            return float(val_strip)
        except ValueError:
            pass
            
        # Return as-is
        return val_strip
