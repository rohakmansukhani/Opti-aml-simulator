import { createClient } from '@supabase/supabase-js';

// Fallback to empty strings or placeholders during build if env vars are missing
// to prevent the build process from crashing during prerendering.
// Platforms like Vercel/Netlify will inject these at build time if configured.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder-build-url.supabase.co';
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-build-key';

if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
    if (typeof window !== 'undefined') {
        console.warn("Supabase URL or Key is missing. Auth features will not work.");
    }
}

export const supabase = createClient(supabaseUrl, supabaseKey);
