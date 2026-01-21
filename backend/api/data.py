from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from datetime import datetime, timezone
import pandas as pd
import io

from database import get_db
from services.data_ingestion import DataIngestionService
from models import Transaction, DataUpload, Alert, SimulationRun, Customer, FieldValueIndex, FieldMetadata, Account, AlertTransaction
from core.upload_validator import UploadValidator
from core.ttl_manager import TTLManager
from auth import get_current_user

router = APIRouter(prefix="/api/data", tags=["Data"])

@router.post("/upload/transactions")
async def upload_transactions(
    file: UploadFile = File(...),
    force_replace: bool = False,
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = user_payload.get("sub")
    if not file.filename.endswith(('.csv', '.xls', '.xlsx')):
        raise HTTPException(400, "Only CSV and Excel files are supported")
    
    content = await file.read()
    service = DataIngestionService()
    
    try:
        # Changed to unpack 3 values
        valid_records, errors, computed_index = service.process_transactions_csv(content, file.filename)
    except Exception as e:
         raise HTTPException(400, str(e))
    
    if not valid_records:
        raise HTTPException(400, "No valid records found. Please ensure headers match: transaction_id, customer_id, etc.")

    # Convert to DataFrame for validation
    if valid_records:
        df = pd.DataFrame(valid_records)
        
        # SIZE VALIDATION
        validation = UploadValidator.validate_size(df, "transactions")
        if not validation["allowed"]:
            raise HTTPException(413, detail={
                "error": "dataset_too_large",
                "count": validation["count"],
                "max_allowed": validation["max_allowed"],
                "message": validation["message"],
                "recommendation": "connect_external_db"
            })
        
    # ===== UPLOAD ID DECISION LOGIC =====
    upload_id = None
    expires_at = None
    should_merge = False
    
    # CHECK FOR EXISTING DATA
    existing_upload_record = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active',
        DataUpload.expires_at > datetime.now(timezone.utc)
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if existing_upload_record and not force_replace:
        upload_age = (datetime.now(timezone.utc) - existing_upload_record.upload_timestamp).total_seconds()
        
        # Same file check
        if existing_upload_record.filename == file.filename and \
           abs(existing_upload_record.record_count_transactions - len(valid_records)) < 10:
            TTLManager.extend_ttl(db, existing_upload_record.upload_id, additional_hours=24)
            return {
                "status": "extended",
                "message": "Existing data found. TTL extended by 24 hours.",
                "upload_id": str(existing_upload_record.upload_id),
                "expires_at": (existing_upload_record.expires_at + pd.Timedelta(hours=24)).isoformat(),
                "records_count": existing_upload_record.record_count_transactions,
                "action": "ttl_extended"
            }
        
        # Merge check: customers exist, transactions don't, recent upload
        if existing_upload_record.record_count_customers > 0 and \
           existing_upload_record.record_count_transactions == 0 and \
           upload_age < 300:
            # MERGE MODE
            upload_id = existing_upload_record.upload_id
            expires_at = existing_upload_record.expires_at
            should_merge = True
            
            # Update record
            existing_upload_record.record_count_transactions = len(valid_records)
            existing_upload_record.filename = f"{existing_upload_record.filename}+{file.filename}"
            db.commit()
        else:
            # Conflict
            raise HTTPException(409, detail={
                "error": "existing_data_conflict",
                "message": f"Active data exists ({existing_upload_record.filename}). Use force_replace=true to replace.",
                "existing_upload_id": str(existing_upload_record.upload_id),
                "expires_at": existing_upload_record.expires_at.isoformat(),
                "suggestion": "Add ?force_replace=true to URL"
            })
    
    # CREATE NEW UPLOAD (only if not merging)
    if not should_merge:
        upload_id = TTLManager.create_upload_record(
            db=db,
            user_id=user_id,
            filename=file.filename,
            txn_count=len(valid_records),
            cust_count=0,
            schema_snapshot={"columns": list(df.columns)},
            ttl_hours=48
        )
        expires_at = TTLManager.set_expiry(48)
    
    # ===== DATA INSERTION =====
    for record in valid_records:
        record['upload_id'] = upload_id
        record['expires_at'] = expires_at
    
    try:
        # Clear old data (only if NOT merging)
        if not should_merge:
            prev_upload_ids = [u.upload_id for u in db.query(DataUpload.upload_id).filter(
                DataUpload.user_id == user_id,
                DataUpload.upload_id != upload_id
            ).all()]
            prev_run_ids = [r.run_id for r in db.query(SimulationRun.run_id).filter(SimulationRun.user_id == user_id).all()]
            

            prev_alert_ids = [a.alert_id for a in db.query(Alert.alert_id).filter(Alert.run_id.in_(prev_run_ids)).all()]
            
            if prev_alert_ids:
                db.query(AlertTransaction).filter(AlertTransaction.alert_id.in_(prev_alert_ids)).delete(synchronize_session=False)
                db.query(Alert).filter(Alert.run_id.in_(prev_run_ids)).delete(synchronize_session=False)
            
            if prev_upload_ids:
                db.query(Transaction).filter(Transaction.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                db.query(FieldValueIndex).filter(FieldValueIndex.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                db.query(FieldMetadata).filter(FieldMetadata.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
            
            # EXTRA SAFETY: Delete specific records in the current batch that would cause unique conflicts
            incoming_txn_ids = [r['transaction_id'] for r in valid_records if 'transaction_id' in r]
            if incoming_txn_ids:
                db.query(Transaction).filter(Transaction.transaction_id.in_(incoming_txn_ids)).delete(synchronize_session=False)
                
        db.flush()
        
        db.bulk_insert_mappings(Transaction, valid_records)
        
        # Save Field Metadata & Index
        print(f"Saving {len(computed_index)} field indices...")
        for field_name, data in computed_index.items():
            metadata = data['metadata']
            values = data['values']
            
            # 1. Save Metadata
            db_metadata = FieldMetadata(
                upload_id=upload_id,
                table_name='transactions',
                **metadata
            )
            db.add(db_metadata)
            
            # 2. Save Values
            for val in values:
                db_val = FieldValueIndex(
                    upload_id=upload_id,
                    table_name='transactions',
                    field_name=field_name,
                    **val
                )
                db.add(db_val)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Database error: {str(e)}")
    
    return {
        "status": "success",
        "records_uploaded": len(valid_records),
        "errors": len(errors),
        "error_sample": errors[:5] if errors else [],
        "upload_id": str(upload_id) if valid_records else None,
        "expires_at": expires_at.isoformat() if valid_records else None,
        "action": "merged" if should_merge else "new_upload"
    }

@router.get("/schema")
async def get_data_schema(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the schema (columns) for Transactions and Customers by extracting field names
    from raw_data JSONB of the user's most recent upload.
    
    This enables schema-agnostic uploads - the system discovers fields dynamically
    from the uploaded CSV data rather than relying on fixed database columns.
    """
    from models import Transaction, Customer, DataUpload
    
    user_id = current_user.get('sub')  # Extract user_id from JWT payload
    
    schema_response = {"transactions": [], "customers": []}
    
    # Helper function to infer type from value
    def infer_type(value):
        if value is None:
            return 'string'
        if isinstance(value, (int, float)):
            return 'number' if isinstance(value, float) else 'integer'
        if isinstance(value, bool):
            return 'boolean'
        # Try to parse as number
        try:
            float(str(value))
            return 'number'
        except:
            pass
        return 'string'
    
    # Get user's most recent upload
    latest_upload = db.query(DataUpload).filter(
        DataUpload.user_id == user_id
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if not latest_upload:
        # Return empty schema if no uploads yet
        return schema_response
    
    # Extract transaction fields from raw_data
    sample_txn = db.query(Transaction).filter(
        Transaction.upload_id == latest_upload.upload_id
    ).first()
    
    if sample_txn and sample_txn.raw_data:
        for field_name, field_value in sample_txn.raw_data.items():
            schema_response["transactions"].append({
                "name": field_name,
                "type": infer_type(field_value),
                "label": field_name.replace('_', ' ').title(),
                "sql_type": infer_type(field_value)
            })
    
    # Extract customer fields from raw_data
    sample_cust = db.query(Customer).filter(
        Customer.upload_id == latest_upload.upload_id
    ).first()
    
    if sample_cust and sample_cust.raw_data:
        for field_name, field_value in sample_cust.raw_data.items():
            schema_response["customers"].append({
                "name": field_name,
                "type": infer_type(field_value),
                "label": field_name.replace('_', ' ').title(),
                "sql_type": infer_type(field_value)
            })
    
    # Fallback to basic schema if no data found
    if not schema_response["transactions"] and not schema_response["customers"]:
        return {
            "transactions": [
                {"name": "transaction_amount", "type": "number", "label": "Transaction Amount"},
                {"name": "transaction_type", "type": "string", "label": "Transaction Type"},
                {"name": "channel", "type": "string", "label": "Channel"},
                {"name": "debit_credit_indicator", "type": "string", "label": "D/C Indicator"},
                {"name": "transaction_narrative", "type": "string", "label": "Narrative"},
                {"name": "beneficiary_name", "type": "string", "label": "Beneficiary Name"},
                {"name": "beneficiary_bank", "type": "string", "label": "Beneficiary Bank"},
                {"name": "transaction_date", "type": "date", "label": "Date"}
            ],
            "customers": [
                {"name": "customer_type", "type": "string", "label": "Customer Type"},
                {"name": "occupation", "type": "string", "label": "Occupation"},
                {"name": "annual_income", "type": "number", "label": "Annual Income"},
                {"name": "risk_score", "type": "number", "label": "Risk Score"},
                {"name": "account_type", "type": "string", "label": "Account Type"}
            ]
        }

    return schema_response

@router.post("/upload/customers")
async def upload_customers(
    file: UploadFile = File(...),
    force_replace: bool = False,  # Query param to force replacement
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = user_payload.get("sub")
    
    if not file.filename.endswith(('.csv', '.xls', '.xlsx')):
        raise HTTPException(400, "Only CSV and Excel files are supported")
    
    content = await file.read()
    service = DataIngestionService()
    try:
        # Changed to unpack 4 values (added extracted_accounts)
        valid_records, errors, computed_index, extracted_accounts = service.process_customers_csv(content, file.filename)
    except Exception as e:
        raise HTTPException(400, str(e))
    
    if not valid_records:
        raise HTTPException(400, "No valid records found. Please ensure headers match: customer_id, customer_name, etc.")

    if valid_records:
        df = pd.DataFrame(valid_records)
        
        # SIZE VALIDATION
        validation = UploadValidator.validate_size(df, "customers")
        if not validation["allowed"]:
            raise HTTPException(413, detail={
                "error": "dataset_too_large",
                "count": validation["count"],
                "max_allowed": validation["max_allowed"],
                "message": validation["message"],
                "recommendation": "connect_external_db"
            })
        
    # ===== UPLOAD ID DECISION LOGIC =====
    upload_id = None
    expires_at = None
    should_merge = False
    
    # CHECK FOR EXISTING DATA
    existing_upload_record = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active',
        DataUpload.expires_at > datetime.now(timezone.utc)
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    if existing_upload_record and not force_replace:
        upload_age = (datetime.now(timezone.utc) - existing_upload_record.upload_timestamp).total_seconds()
        
        # Same file check
        if existing_upload_record.filename == file.filename and \
           abs(existing_upload_record.record_count_customers - len(valid_records)) < 5:
            # Extend TTL
            TTLManager.extend_ttl(db, existing_upload_record.upload_id, additional_hours=24)
            return {
                "status": "extended",
                "message": "Existing data found. TTL extended by 24 hours.",
                "upload_id": str(existing_upload_record.upload_id),
                "expires_at": (existing_upload_record.expires_at + pd.Timedelta(hours=24)).isoformat(),
                "records_count": existing_upload_record.record_count_customers,
                "action": "ttl_extended"
            }
        
        # Merge check: transactions exist, customers don't, recent upload
        if existing_upload_record.record_count_transactions > 0 and \
           existing_upload_record.record_count_customers == 0 and \
           upload_age < 300:
            # MERGE MODE
            upload_id = existing_upload_record.upload_id
            expires_at = existing_upload_record.expires_at
            should_merge = True
            
            # Update record
            existing_upload_record.record_count_customers = len(valid_records)
            existing_upload_record.filename = f"{existing_upload_record.filename}+{file.filename}"
            db.commit()
        else:
             raise HTTPException(409, detail={
                "error": "existing_data_conflict",
                "message": f"Active data exists ({existing_upload_record.filename}). Use force_replace=true to replace.",
                "existing_upload_id": str(existing_upload_record.upload_id),
                "expires_at": existing_upload_record.expires_at.isoformat(),
                "suggestion": "Add ?force_replace=true to URL to replace existing data"
            })
    
    # CREATE NEW UPLOAD (only if not merging)
    if not should_merge:
        upload_id = TTLManager.create_upload_record(
            db=db,
            user_id=user_id,
            filename=file.filename,
            txn_count=0,
            cust_count=len(valid_records),
            schema_snapshot={"columns": list(df.columns)},
            ttl_hours=48
        )
        expires_at = TTLManager.set_expiry(48)
    
    # ===== DATA INSERTION =====
    # Add TTL fields to records
    for record in valid_records:
        record['upload_id'] = upload_id
        record['expires_at'] = expires_at
        
    for account in extracted_accounts:
        account['upload_id'] = upload_id
        account['expires_at'] = expires_at
    
    try:
        # Clear existing data ONLY for the current user
        # (Only if NOT merging - merging appends to the same upload_id entity but we are inserting new rows for a different table)
        if not should_merge:

            
            # Find all previous upload IDs for this user
            prev_upload_ids = [u.upload_id for u in db.query(DataUpload.upload_id).filter(
                DataUpload.user_id == user_id,
                DataUpload.upload_id != upload_id
            ).all()]
            # Find all previous run IDs for this user
            prev_run_ids = [r.run_id for r in db.query(SimulationRun.run_id).filter(SimulationRun.user_id == user_id).all()]
            
            # 1. Delete Alerts linked to this user's runs
            if prev_run_ids:
                db.query(Alert).filter(Alert.run_id.in_(prev_run_ids)).delete(synchronize_session=False)
            
            # 2. Delete Transactions/Customers/Accounts linked to this user's uploads
            if prev_upload_ids:
                db.query(Transaction).filter(Transaction.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                # Cleanup Accounts
                db.query(Account).filter(Account.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                # Cleanup Customers
                db.query(Customer).filter(Customer.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                # Cleanup Indices
                db.query(FieldValueIndex).filter(FieldValueIndex.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                db.query(FieldMetadata).filter(FieldMetadata.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
        
        # 3. EXTRA SAFETY: Delete specific records in the current batch
        incoming_cust_ids = [r['customer_id'] for r in valid_records if 'customer_id' in r]
        if incoming_cust_ids:
            # Referenced tables first
            db.query(Alert).filter(Alert.customer_id.in_(incoming_cust_ids)).delete(synchronize_session=False)
            db.query(Transaction).filter(Transaction.customer_id.in_(incoming_cust_ids)).delete(synchronize_session=False)
            db.query(Account).filter(Account.customer_id.in_(incoming_cust_ids)).delete(synchronize_session=False)
            db.query(Customer).filter(Customer.customer_id.in_(incoming_cust_ids)).delete(synchronize_session=False)
        
        db.flush()
        
        # Bulk Insert Customers & Accounts
        db.bulk_insert_mappings(Customer, valid_records)
        
        if extracted_accounts:
            db.bulk_insert_mappings(Account, extracted_accounts)

        # Save Field Metadata & Index
        print(f"Saving {len(computed_index)} field indices for customers...")
        for field_name, data in computed_index.items():
            metadata = data['metadata']
            values = data['values']
            
            # 1. Save Metadata
            db_metadata = FieldMetadata(
                upload_id=upload_id,
                table_name='customers',
                **metadata
            )
            db.add(db_metadata)
            
            # 2. Save Values
            for val in values:
                db_val = FieldValueIndex(
                    upload_id=upload_id,
                    table_name='customers',
                    field_name=field_name,
                    **val
                )
                db.add(db_val)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Database error: {str(e)}")
            
    return {
        "status": "success",
        "records_uploaded": len(valid_records),
        "errors": len(errors),
        "upload_id": str(upload_id) if valid_records else None,
        "expires_at": expires_at.isoformat() if valid_records else None,
        "action": "merged" if should_merge else "new_upload"
    }

@router.get("/values")
async def get_field_values(
    field: str,
    search: str = "",
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns distinct values for a specific field to power UI autocomplete.
    Queries raw_data JSONB from both Transactions and Customers tables.
    """
    user_id = user_payload.get("sub")
    print(f"[VALUES] Searching field='{field}', search='{search}', user_id='{user_id}'")
    potential_tables = ['transactions', 'customers']

    for table in potential_tables:
        try:
            # Query JSONB raw_data directly (schema-agnostic)
            # SQL Injection Fix: Validate table & use params
            if table not in ['transactions', 'customers']:
                continue

            query = text(f"""
                SELECT DISTINCT t.raw_data ->> :field_name
                FROM {table} t
                JOIN data_uploads du ON t.upload_id = du.upload_id
                WHERE du.user_id = :user_id 
                AND t.raw_data ? :field_name
                AND lower(t.raw_data ->> :field_name) LIKE lower(:search)
                LIMIT 20
            """)
            json_result = db.execute(query, {"field_name": field, "search": f"%{search}%", "user_id": user_id})
            json_values = [row[0] for row in json_result.fetchall() if row[0] is not None]

            print(f"[VALUES] Found {len(json_values)} values in {table}: {json_values}")
            
            if json_values:
                return {"values": json_values}
                
        except Exception as e:
            print(f"[VALUES] Error querying {table}: {e}")
            db.rollback()
            continue
            
    print(f"[VALUES] No values found, returning empty array")
    return {"values": []}

@router.post("/ttl/extend")
async def extend_ttl(
    upload_id: str,
    additional_hours: int = 24,
    db: Session = Depends(get_db)
):
    """
    Extend the TTL for uploaded data.
    """
    success = TTLManager.extend_ttl(db, upload_id, additional_hours)
    
    if not success:
        raise HTTPException(404, "Upload not found")
    
    # Get updated expiry
    result = db.execute(
        text("SELECT expires_at FROM data_uploads WHERE upload_id = :id"),
        {"id": upload_id}
    ).fetchone()
    
    return {
        "status": "success",
        "upload_id": str(upload_id),
        "new_expires_at": result[0].isoformat() if result else None,
        "hours_added": additional_hours
    }
