-- Migration: Simplify customers and transactions tables to be schema-agnostic
-- Date: 2026-01-19
-- Purpose: Remove fixed columns, rely solely on raw_data JSONB for user data
-- Author: Antigravity AI

-- This migration removes redundant fixed columns from customers and transactions tables.
-- All user CSV data is stored in the raw_data JSONB column, making the system
-- truly schema-agnostic and able to handle any CSV structure.

BEGIN;

-- ============================================================
-- CUSTOMERS TABLE SIMPLIFICATION
-- ============================================================
-- Remove all user-data columns, keep only system metadata
ALTER TABLE public.customers
  DROP COLUMN IF EXISTS customer_name,
  DROP COLUMN IF EXISTS customer_type,
  DROP COLUMN IF EXISTS occupation,
  DROP COLUMN IF EXISTS annual_income,
  DROP COLUMN IF EXISTS account_type,
  DROP COLUMN IF EXISTS risk_score;

-- ============================================================
-- TRANSACTIONS TABLE SIMPLIFICATION
-- ============================================================
-- Remove all user-data columns, keep only system metadata and FK
ALTER TABLE public.transactions
  DROP COLUMN IF EXISTS account_number,
  DROP COLUMN IF EXISTS transaction_date,
  DROP COLUMN IF EXISTS transaction_amount,
  DROP COLUMN IF EXISTS debit_credit_indicator,
  DROP COLUMN IF EXISTS transaction_type,
  DROP COLUMN IF EXISTS channel,
  DROP COLUMN IF EXISTS transaction_narrative,
  DROP COLUMN IF EXISTS beneficiary_name,
  DROP COLUMN IF EXISTS beneficiary_bank;

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
-- Run these after migration to verify the schema

-- Check customers table structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'customers' 
ORDER BY ordinal_position;

-- Check transactions table structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'transactions' 
ORDER BY ordinal_position;

-- Expected customers columns:
-- customer_id, upload_id, created_at, expires_at, raw_data

-- Expected transactions columns:
-- transaction_id, customer_id, upload_id, created_at, expires_at, raw_data
