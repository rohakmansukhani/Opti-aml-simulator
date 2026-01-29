import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SessionState {
    dbUrl: string | null;
    mode: 'local' | 'enterprise' | null;
    isConnected: boolean;
    user: any | null; // Supabase User
    token: string | null;
    setConnection: (url: string, mode: 'local' | 'enterprise') => void;
    setAuth: (user: any, token: string) => void;
    disconnect: () => void;
    logout: () => void;
}

export const useSessionStore = create<SessionState>()(
    persist(
        (set) => ({
            dbUrl: null,
            mode: null,
            isConnected: false,
            user: null,
            token: null,
            setConnection: (url, mode) => set({ dbUrl: url, mode, isConnected: true }),
            setAuth: (user, token) => set({ user, token }),
            disconnect: () => set({ dbUrl: null, mode: null, isConnected: false }),
            logout: () => set({ user: null, token: null, dbUrl: null, mode: null, isConnected: false }),
        }),
        {
            name: 'sas-session-storage',
        }
    )
);
