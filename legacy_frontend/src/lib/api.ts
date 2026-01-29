import axios from 'axios';
import { useSessionStore } from '@/store/useSessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
});

// Request interceptor - inject auth + db URL
apiClient.interceptors.request.use((config) => {
    const { token, dbUrl, mode } = useSessionStore.getState();

    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }

    // Inject DB URL or Local Mode flag
    if (dbUrl) {
        config.headers['x-db-url'] = dbUrl;
    } else if (mode === 'local') {
        config.headers['x-db-url'] = 'local';
    }

    return config;
});

// Response interceptor - global error handling
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Token expired or invalid
            console.warn('Session expired, logging out...');
            useSessionStore.getState().logout();
            if (typeof window !== 'undefined') {
                window.location.href = '/?error=session_expired';
            }
        }

        if (error.response?.status === 403) {
            // Permission denied
            console.error('Access denied:', error.response.data);
            // Optional: Show toast/alert
        }

        return Promise.reject(error);
    }
);

export const api = apiClient;
