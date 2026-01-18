'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { useSessionStore } from '@/store/useSessionStore';
import { Loader2 } from 'lucide-react';

export default function AuthCallback() {
    const router = useRouter();
    const setAuth = useSessionStore((s) => s.setAuth);

    useEffect(() => {
        const handleCallback = async () => {
            const { data, error } = await supabase.auth.getSession();

            if (error || !data.session) {
                router.push('/?error=auth_failed');
                return;
            }

            setAuth(data.session.user, data.session.access_token);
            router.push('/dashboard');
        };

        handleCallback();
    }, [router, setAuth]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
            <div className="text-center">
                <Loader2 className="animate-spin mx-auto mb-4" size={40} />
                <p className="text-slate-500">Completing sign in...</p>
            </div>
        </div>
    );
}
