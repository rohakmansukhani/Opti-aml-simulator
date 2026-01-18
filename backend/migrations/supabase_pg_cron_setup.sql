-- Supabase pg_cron Configuration for TTL Cleanup
-- Run this SQL in your Supabase SQL Editor

-- 1. Enable pg_cron extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 2. Schedule hourly cleanup job
SELECT cron.schedule(
  'cleanup-expired-data',
  '0 * * * *',  -- Every hour at minute 0
  $$
  DELETE FROM public.transactions WHERE expires_at < now();
  DELETE FROM public.customers WHERE expires_at < now();
  UPDATE public.data_uploads 
  SET status = 'expired' 
  WHERE expires_at < now() AND status = 'active';
  $$
);

-- 3. Verify the job was created
SELECT * FROM cron.job WHERE jobname = 'cleanup-expired-data';

-- 4. (Optional) Manually trigger cleanup for testing
-- DELETE FROM public.transactions WHERE expires_at < now();
-- DELETE FROM public.customers WHERE expires_at < now();
-- UPDATE public.data_uploads SET status = 'expired' WHERE expires_at < now() AND status = 'active';
