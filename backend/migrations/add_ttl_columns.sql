-- Add TTL columns to existing tables in Supabase
-- Run this SQL in your Supabase SQL Editor

-- Add columns to customers table (UUID type to match data_uploads)
ALTER TABLE public.customers 
ADD COLUMN IF NOT EXISTS upload_id UUID REFERENCES public.data_uploads(upload_id),
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Add columns to transactions table (UUID type to match data_uploads)
ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS upload_id UUID REFERENCES public.data_uploads(upload_id),
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Create indexes for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_customers_expires_at ON public.customers(expires_at);
CREATE INDEX IF NOT EXISTS idx_transactions_expires_at ON public.transactions(expires_at);
CREATE INDEX IF NOT EXISTS idx_customers_upload_id ON public.customers(upload_id);
CREATE INDEX IF NOT EXISTS idx_transactions_upload_id ON public.transactions(upload_id);

-- Verify the changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('customers', 'transactions') 
  AND column_name IN ('upload_id', 'expires_at')
ORDER BY table_name, column_name;
