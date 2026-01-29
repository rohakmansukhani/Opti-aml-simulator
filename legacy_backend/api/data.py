from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from datetime import datetime, timezone
import pandas as pd
import io
import json

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
    
    # ===== CHECK FOR EXISTING UPLOAD FIRST (for merge) =====
    existing_upload_record = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active',
        DataUpload.expires_at > datetime.now(timezone.utc)
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    upload_id = None
    should_merge = False
    
    # ✅ HANDLE force_replace EARLY (delete only transactions, keep customers!)
    if existing_upload_record and force_replace:
        print(f"[FORCE_REPLACE] Deleting ONLY transactions from upload: {existing_upload_record.upload_id}")
        
        try:
            # Get all upload IDs for this user
            prev_upload_ids = [u.upload_id for u in db.query(DataUpload.upload_id).filter(
                DataUpload.user_id == user_id
            ).all()]
            
            # Delete simulation data (alerts depend on transactions)
            prev_run_ids = [r.run_id for r in db.query(SimulationRun.run_id).filter(
                SimulationRun.user_id == user_id
            ).all()]
            
            if prev_run_ids:
                prev_alert_ids = [a.alert_id for a in db.query(Alert.alert_id).filter(
                    Alert.run_id.in_(prev_run_ids)
                ).all()]
                
                if prev_alert_ids:
                    db.query(AlertTransaction).filter(
                        AlertTransaction.alert_id.in_(prev_alert_ids)
                    ).delete(synchronize_session=False)
                    print(f"[FORCE_REPLACE] Deleted alert_transactions")
                    
                db.query(Alert).filter(Alert.run_id.in_(prev_run_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted alerts")
                
                db.query(SimulationRun).filter(SimulationRun.run_id.in_(prev_run_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted simulation runs")
            
            # ✅ DELETE ONLY TRANSACTIONS (keep customers and accounts!)
            if prev_upload_ids:
                txn_count = db.query(Transaction).filter(
                    Transaction.upload_id.in_(prev_upload_ids)
                ).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {txn_count} transactions")
                
                # Delete transaction field indices
                db.query(FieldValueIndex).filter(
                    FieldValueIndex.upload_id.in_(prev_upload_ids),
                    FieldValueIndex.table_name == 'transactions'
                ).delete(synchronize_session=False)
                
                db.query(FieldMetadata).filter(
                    FieldMetadata.upload_id.in_(prev_upload_ids),
                    FieldMetadata.table_name == 'transactions'
                ).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted transaction field indices")
                
                # Update DataUpload record (set txn count to 0, keep customer count)
                db.query(DataUpload).filter(
                    DataUpload.upload_id.in_(prev_upload_ids)
                ).update({
                    'record_count_transactions': 0
                }, synchronize_session=False)
                print(f"[FORCE_REPLACE] Reset transaction counts in upload records")
            
            db.commit()
            print(f"[FORCE_REPLACE] Deletion committed successfully")
            
            # ✅ REUSE EXISTING UPLOAD_ID (don't create new one!)
            upload_id = str(existing_upload_record.upload_id)
            should_merge = True
            print(f"[FORCE_REPLACE] Reusing upload_id: {upload_id}")
            
        except Exception as e:
            print(f"[ERROR] Force replace deletion failed: {str(e)}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise HTTPException(500, f"Failed to delete old data: {str(e)}")
    
    # MERGE CHECK: Recent customers upload without transactions (if not force_replace)
    if existing_upload_record and not force_replace and upload_id is None:
        upload_age = (datetime.now(timezone.utc) - existing_upload_record.upload_timestamp).total_seconds()
        
        # ✅ MERGE MODE: Customers exist, transactions don't, recent upload (< 5 min)
        if (existing_upload_record.record_count_customers > 0 and 
            existing_upload_record.record_count_transactions == 0 and 
            upload_age < 300):
            
            # ✅ REUSE EXISTING UPLOAD_ID for matching prefixes
            upload_id = str(existing_upload_record.upload_id)
            should_merge = True
            print(f"[MERGE MODE] Reusing upload_id: {upload_id}")
            print(f"[MERGE MODE] Upload age: {upload_age:.1f} seconds")
    
    # ✅ Generate NEW upload_id only if NOT merging
    if upload_id is None:
        import uuid
        upload_id = str(uuid.uuid4())
        print(f"[NEW UPLOAD] Generated upload_id: {upload_id}")
    
    
    # ✅ NOW process with the correct upload_id
    try:
        # ✅ Pass upload_id to service for prefixing
        valid_records, errors, computed_index = service.process_transactions_csv(content, file.filename, upload_id)
        
        # [DEBUG]
        print(f"[DEBUG] Upload Transactions File: {file.filename}")
        print(f"[DEBUG] Valid Transaction Records: {len(valid_records)}")
        if valid_records:
            print(f"[DEBUG] First 3 Txn IDs: {[r.get('transaction_id') for r in valid_records[:3]]}")
            print(f"[DEBUG] First 3 Customer IDs: {[r.get('customer_id') for r in valid_records[:3]]}")
            print(f"[DEBUG] Upload ID being used: {upload_id}")
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
        
        # ✅ VERIFY CUSTOMERS EXIST before proceeding
        sample_cust_id = valid_records[0]['customer_id']
        customer_check = db.query(Customer).filter(
            Customer.customer_id == sample_cust_id,
            Customer.upload_id == upload_id
        ).first()
        
        if customer_check:
            print(f"[DEBUG] ✅ Customer {sample_cust_id} EXISTS in database")
        else:
            print(f"[DEBUG] ❌ Customer {sample_cust_id} NOT FOUND!")
            print(f"[DEBUG] Checking all customers with upload_id {upload_id}...")
            all_custs = db.query(Customer.customer_id).filter(
                Customer.upload_id == upload_id
            ).limit(5).all()
            print(f"[DEBUG] Found {len(all_custs)} customers: {[c.customer_id for c in all_custs]}")
            
            if len(all_custs) == 0:
                raise HTTPException(400, 
                    "No customers found for this upload. Please upload customers first before uploading transactions."
                )
    
    # ===== HANDLE EXISTING DATA CONFLICTS =====
    expires_at = None
    
    if existing_upload_record and not force_replace and not should_merge:
        upload_age = (datetime.now(timezone.utc) - existing_upload_record.upload_timestamp).total_seconds()
        
        # Same file check (extend TTL)
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
        
        # Conflict: Transactions already exist
        if existing_upload_record.record_count_transactions > 0:
            raise HTTPException(409, detail={
                "error": "existing_data_conflict",
                "message": f"Active data exists ({existing_upload_record.filename}). Use force_replace=true to replace.",
                "existing_upload_id": str(existing_upload_record.upload_id),
                "expires_at": existing_upload_record.expires_at.isoformat(),
                "suggestion": "Add ?force_replace=true to URL"
            })
    
    # ===== UPDATE OR CREATE UPLOAD RECORD =====
    if should_merge:
        # Update existing upload record
        existing_upload_record.record_count_transactions = len(valid_records)
        existing_upload_record.filename = f"{existing_upload_record.filename}+{file.filename}"
        expires_at = existing_upload_record.expires_at
        db.commit()
        print(f"[MERGE MODE] Updated existing upload record")
    
    # CREATE NEW UPLOAD (only if not merging)
    if not should_merge:
        # Use the upload_id we already generated and used for prefixing
        upload_record_id = TTLManager.create_upload_record(
            db=db,
            user_id=user_id,
            filename=file.filename,
            txn_count=len(valid_records),
            cust_count=0,
            schema_snapshot={"columns": list(df.columns)},
            ttl_hours=48,
            upload_id=upload_id  # Pass our pre-generated ID
        )
        # upload_id stays the same
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
            
            db.commit()  # Commit deletion before insert
        
        # USE UPSERT FOR TRANSACTIONS
        print(f"[UPLOAD] Upserting {len(valid_records)} transactions...")
        
        from sqlalchemy import insert
        
        # USE BATCH UPSERT FOR TRANSACTIONS (much faster!)
        print(f"[UPLOAD] Upserting {len(valid_records)} transactions...")
        
        # Use RAW psycopg2 cursor to bypass SQLAlchemy parameter issues
        connection = db.connection().connection
        cursor = connection.cursor()
        
        # Deduplicate
        unique_txns = {r['transaction_id']: r for r in valid_records}
        valid_records = list(unique_txns.values())
        
        batch_size = 500
        for i in range(0, len(valid_records), batch_size):
            batch = valid_records[i:i+batch_size]
            placeholders = []
            values = []
            
            for record in batch:
                placeholders.append("(%s, %s, %s::uuid, %s::jsonb, %s, %s)")
                values.extend([
                    record['transaction_id'],
                    record.get('customer_id'),
                    str(record['upload_id']),
                    json.dumps(record['raw_data']),
                    record['expires_at'],
                    record.get('created_at', datetime.now(timezone.utc))
                ])
            
            sql = f"""
                INSERT INTO transactions (transaction_id, customer_id, upload_id, raw_data, expires_at, created_at)
                VALUES {','.join(placeholders)}
                ON CONFLICT (transaction_id, upload_id)
                DO UPDATE SET
                    customer_id = EXCLUDED.customer_id,
                    raw_data = EXCLUDED.raw_data,
                    expires_at = EXCLUDED.expires_at,
                    created_at = EXCLUDED.created_at
            """
            cursor.execute(sql, values)
            print(f"[UPLOAD] Processed {min(i+batch_size, len(valid_records))}/{len(valid_records)} transactions")
        
        cursor.close()
        print(f"[UPLOAD] Upserted {len(valid_records)} transactions")
        
        # Save Field Metadata & Index
        print(f"[UPLOAD] Saving {len(computed_index)} field indices...")
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
        print(f"[UPLOAD] Successfully committed all data")
        
    except Exception as e:
        print(f"[ERROR] Database insertion failed: {str(e)}")
        import traceback
        traceback.print_exc()
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
            
    # Fallback: If no customers in current upload, try to find ANY customer to infer schema
    if not schema_response["customers"]:
        any_sample_cust = db.query(Customer).order_by(Customer.created_at.desc()).first()
        if any_sample_cust and any_sample_cust.raw_data:
             for field_name, field_value in any_sample_cust.raw_data.items():
                schema_response["customers"].append({
                    "name": field_name,
                    "type": infer_type(field_value),
                    "label": field_name.replace('_', ' ').title(),
                    "sql_type": infer_type(field_value)
                })

    # Hard Fallback: If still no customer schema, use defaults
    if not schema_response["customers"]:
        schema_response["customers"] = [
            {"name": "customer_type", "type": "string", "label": "Customer Type"},
            {"name": "occupation", "type": "string", "label": "Occupation"},
            {"name": "annual_income", "type": "number", "label": "Annual Income"},
            {"name": "risk_score", "type": "number", "label": "Risk Score"},
            {"name": "customer_id", "type": "string", "label": "Customer ID"}
        ]

    # Fallback to basic schema if no data found (Transactions only)
    if not schema_response["transactions"]:
         schema_response["transactions"] = [
                {"name": "transaction_amount", "type": "number", "label": "Transaction Amount"},
                {"name": "transaction_type", "type": "string", "label": "Transaction Type"},
                {"name": "channel", "type": "string", "label": "Channel"},
                {"name": "debit_credit_indicator", "type": "string", "label": "D/C Indicator"},
                {"name": "transaction_narrative", "type": "string", "label": "Narrative"},
                {"name": "beneficiary_name", "type": "string", "label": "Beneficiary Name"},
                {"name": "beneficiary_bank", "type": "string", "label": "Beneficiary Bank"},
                {"name": "transaction_date", "type": "date", "label": "Date"}
            ]

    return schema_response

@router.post("/upload/customers")
async def upload_customers(
    file: UploadFile = File(...),
    force_replace: bool = False,
    user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = user_payload.get("sub")
    
    # 1. Validate file type
    if not file.filename.endswith(('.csv', '.xls', '.xlsx')):
        raise HTTPException(400, "Only CSV and Excel files are supported")
    
    # 2. Process file
    content = await file.read()
    service = DataIngestionService()
    
    # ✅ Generate upload_id EARLY (before processing)
    import uuid
    upload_id = str(uuid.uuid4())
    
    try:
        # ✅ Pass upload_id to service for prefixing
        valid_records, errors, computed_index, extracted_accounts = service.process_customers_csv(content, file.filename, upload_id)
        
        # [DEBUG]
        print(f"[DEBUG] Upload Customers File: {file.filename}")
        print(f"[DEBUG] Valid Customer Records: {len(valid_records)}")
        if valid_records:
            print(f"[DEBUG] First 3 Cust IDs: {[r.get('customer_id') for r in valid_records[:3]]}")
    except Exception as e:
        raise HTTPException(400, str(e))
    
    if not valid_records:
        raise HTTPException(400, "No valid records found. Please ensure headers match customer_id, customer_name, etc.")
    
    # 3. Size validation
    df = pd.DataFrame(valid_records)
    validation = UploadValidator.validate_size(df, "customers")
    
    if not validation['allowed']:
        raise HTTPException(413, detail={
            "error": "dataset_too_large",
            "count": validation['count'],
            "max_allowed": validation['max_allowed'],
            "message": validation['message'],
            "recommendation": "connect_external_db"
        })
    
    # 4. Check for existing data
    existing_upload_record = db.query(DataUpload).filter(
        DataUpload.user_id == user_id,
        DataUpload.status == 'active',
        DataUpload.expires_at > datetime.now(timezone.utc)
    ).order_by(DataUpload.upload_timestamp.desc()).first()
    
    # Note: upload_id already generated above for prefixing
    expires_at = None
    should_merge = False
    
    # FORCE REPLACE FIRST
    if existing_upload_record and force_replace:
        try:
            print(f"[FORCE_REPLACE] Deleting existing upload: {existing_upload_record.upload_id}")
            
            # Find all previous upload IDs for this user
            prev_upload_ids = [u.upload_id for u in db.query(DataUpload.upload_id).filter(
                DataUpload.user_id == user_id
            ).all()]
            
            print(f"[FORCE_REPLACE] Found {len(prev_upload_ids)} previous uploads: {prev_upload_ids}")
            
            # Find all previous run IDs
            prev_run_ids = [r.run_id for r in db.query(SimulationRun.run_id).filter(
                SimulationRun.user_id == user_id
            ).all()]
            
            print(f"[FORCE_REPLACE] Found {len(prev_run_ids)} previous runs")
            
            # Delete cascade (in correct order to respect foreign keys)
            if prev_run_ids:
                # 1. Delete AlertTransaction (if exists)
                try:
                    alert_txn_count = db.query(AlertTransaction).filter(
                        AlertTransaction.alert_id.in_(
                            db.query(Alert.alert_id).filter(Alert.run_id.in_(prev_run_ids))
                        )
                    ).delete(synchronize_session=False)
                    print(f"[FORCE_REPLACE] Deleted {alert_txn_count} alert_transactions")
                except:
                    pass  # Table might not exist
                
                # 2. Delete Alerts
                alert_count = db.query(Alert).filter(Alert.run_id.in_(prev_run_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {alert_count} alerts")
                
                # 3. Delete Simulation Runs
                run_count = db.query(SimulationRun).filter(SimulationRun.run_id.in_(prev_run_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {run_count} runs")
            
            if prev_upload_ids:
                # 4. Delete Transactions
                txn_count = db.query(Transaction).filter(Transaction.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {txn_count} transactions")
                
                # 5. Delete Accounts
                acc_count = db.query(Account).filter(Account.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {acc_count} accounts")
                
                # 6. Delete Field Indices
                idx_count = db.query(FieldValueIndex).filter(FieldValueIndex.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {idx_count} field value indices")
                
                meta_count = db.query(FieldMetadata).filter(FieldMetadata.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {meta_count} field metadata")
                
                # 7. Delete Customers (MUST be after Alerts are deleted due to FK)
                cust_count = db.query(Customer).filter(Customer.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {cust_count} customers")
                
                # 8. Delete DataUpload records
                upload_count = db.query(DataUpload).filter(DataUpload.upload_id.in_(prev_upload_ids)).delete(synchronize_session=False)
                print(f"[FORCE_REPLACE] Deleted {upload_count} data uploads")
            
            # CRITICAL: Commit the deletion BEFORE creating new records
            db.commit()
            print(f"[FORCE_REPLACE] Deletion committed successfully")
            
            existing_upload_record = None
            
        except Exception as e:
            print(f"[ERROR] Force replace deletion failed: {str(e)}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise HTTPException(500, f"Failed to delete old data: {str(e)}")
    
    # 5. Handle existing data (if not force_replace)
    if existing_upload_record and not force_replace:
        upload_age = (datetime.now(timezone.utc) - existing_upload_record.upload_timestamp).total_seconds()
        
        # Same file check (extend TTL)
        if (existing_upload_record.filename == file.filename and 
            abs(existing_upload_record.record_count_customers - len(valid_records)) <= 5):
            
            TTLManager.extend_ttl(db, existing_upload_record.upload_id, additional_hours=24)
            return {
                "status": "extended",
                "message": "Existing data found. TTL extended by 24 hours.",
                "upload_id": str(existing_upload_record.upload_id),
                "expires_at": (existing_upload_record.expires_at + pd.Timedelta(hours=24)).isoformat(),
                "records_count": existing_upload_record.record_count_customers,
                "action": "ttl_extended"
            }
        
        # Merge check (transactions exist, customers don't, recent upload)
        if (existing_upload_record.record_count_transactions > 0 and 
            existing_upload_record.record_count_customers == 0 and 
            upload_age < 300):
            # MERGE MODE - reuse existing upload_id
            # Re-process with existing upload_id for proper prefixing
            existing_upload_id = existing_upload_record.upload_id
            
            valid_records, errors, computed_index, extracted_accounts = service.process_customers_csv(content, file.filename, str(existing_upload_id))
            
            upload_id = existing_upload_id
            expires_at = existing_upload_record.expires_at
            should_merge = True
            
            # Update record
            existing_upload_record.record_count_customers = len(valid_records)
            existing_upload_record.filename = f"{existing_upload_record.filename}+{file.filename}"
            db.commit()
        else:
            # Conflict - ask user to force replace
            raise HTTPException(409, detail={
                "error": "existing_data_conflict",
                "message": f"Active data exists ({existing_upload_record.filename}). Use force_replace=true to replace.",
                "existing_upload_id": str(existing_upload_record.upload_id),
                "expires_at": existing_upload_record.expires_at.isoformat(),
                "suggestion": "Add ?force_replace=true to URL"
            })
    
    # 6. Create new upload if not merging
    if not should_merge:
        # Use the upload_id we already generated and used for prefixing
        upload_record_id = TTLManager.create_upload_record(
            db=db,
            user_id=user_id,
            filename=file.filename,
            txn_count=0,
            cust_count=len(valid_records),
            schema_snapshot={"columns": list(df.columns)},
            ttl_hours=48,
            upload_id=upload_id  # Pass our pre-generated ID
        )
        # upload_id stays the same
        expires_at = TTLManager.set_expiry(48)
    
    # VALIDATION: Ensure upload_id is set
    if not upload_id:
        raise HTTPException(500, "Failed to create upload record")
    
    # 7. Add TTL fields to records
    for record in valid_records:
        record['upload_id'] = upload_id
        record['expires_at'] = expires_at
    
    for account in extracted_accounts:
        account['upload_id'] = upload_id
        account['expires_at'] = expires_at
    
    # 8. Insert data
    try:
        print(f"[UPLOAD] Upserting {len(valid_records)} customers...")
        
        # Use RAW psycopg2 cursor (bypasses SQLAlchemy parameter conversion)
        connection = db.connection().connection  # Get raw psycopg2 connection
        cursor = connection.cursor()
        
        batch_size = 500
        for i in range(0, len(valid_records), batch_size):
            batch = valid_records[i:i+batch_size]
            placeholders = []
            values = []
            
            for record in batch:
                placeholders.append("(%s, %s::uuid, %s::jsonb, %s, %s)")
                values.extend([
                    record['customer_id'],
                    str(record['upload_id']),
                    json.dumps(record['raw_data']),
                    record['expires_at'],
                    record.get('created_at', datetime.now(timezone.utc))
                ])
            
            sql = f"""
                INSERT INTO customers (customer_id, upload_id, raw_data, expires_at, created_at)
                VALUES {','.join(placeholders)}
                ON CONFLICT (customer_id, upload_id) 
                DO UPDATE SET
                    raw_data = EXCLUDED.raw_data,
                    expires_at = EXCLUDED.expires_at,
                    created_at = EXCLUDED.created_at
            """
            cursor.execute(sql, values)
            print(f"[UPLOAD] Processed {min(i+batch_size, len(valid_records))}/{len(valid_records)} customers")
        
        cursor.close()
        print(f"[UPLOAD] Upserted {len(valid_records)} customers")
        
        # Insert accounts
        if extracted_accounts:
            print(f"[UPLOAD] Upserting {len(extracted_accounts)} accounts...")
            cursor = db.connection().connection.cursor()
            
            batch_size = 500
            for i in range(0, len(extracted_accounts), batch_size):
                batch = extracted_accounts[i:i+batch_size]
                placeholders = []
                values = []
                
                for account in batch:
                    placeholders.append("(%s, %s, %s::uuid, %s::jsonb, %s, %s)")
                    values.extend([
                        account['account_id'],
                        account['customer_id'],
                        str(account['upload_id']),
                        json.dumps(account.get('raw_data', {})),
                        account['expires_at'],
                        account.get('created_at', datetime.now(timezone.utc))
                    ])
                
                sql = f"""
                    INSERT INTO accounts (account_id, customer_id, upload_id, raw_data, expires_at, created_at)
                    VALUES {','.join(placeholders)}
                    ON CONFLICT (account_id, upload_id) DO UPDATE SET
                        customer_id = EXCLUDED.customer_id,
                        raw_data = EXCLUDED.raw_data,
                        expires_at = EXCLUDED.expires_at,
                        created_at = EXCLUDED.created_at
                """
                cursor.execute(sql, values)
            
            cursor.close()
            print(f"[UPLOAD] Upserted {len(extracted_accounts)} accounts")
        
        # Save field indices
        print(f"[UPLOAD] Saving {len(computed_index)} field indices...")
        for field_name, data in computed_index.items():
            metadata = data['metadata']
            values = data['values']
            
            # Save metadata
            db_metadata = FieldMetadata(
                upload_id=upload_id,
                table_name='customers',
                **metadata
            )
            db.add(db_metadata)
            
            # Save values
            for val in values:
                db_val = FieldValueIndex(
                    upload_id=upload_id,
                    table_name='customers',
                    field_name=field_name,
                    **val
                )
                db.add(db_val)
        
        db.commit()
        print(f"[UPLOAD] Successfully committed all data")
        
    except Exception as e:
        print(f"[ERROR] Database insertion failed: {str(e)}")
        import traceback
        traceback.print_exc()
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
