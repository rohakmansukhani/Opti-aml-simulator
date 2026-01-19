/**
 * Custom hook for managing simulation execution
 * 
 * Handles:
 * - Running simulations
 * - Polling for completion
 * - Progress tracking
 * - Error handling
 */

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface SimulationProgress {
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress_percentage: number;
    total_alerts?: number;
    error?: string;
}

interface UseSimulationRunnerReturn {
    runSimulation: (scenarioId: string, dateRange?: { start: string; end: string }) => Promise<string | null>;
    progress: SimulationProgress | null;
    isRunning: boolean;
    error: string | null;
}

export function useSimulationRunner(): UseSimulationRunnerReturn {
    const [progress, setProgress] = useState<SimulationProgress | null>(null);
    const [isRunning, setIsRunning] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const pollStatus = async (runId: string): Promise<void> => {
        const maxAttempts = 120; // 2 minutes max (1 second intervals)
        let attempts = 0;

        const poll = async (): Promise<void> => {
            try {
                const response = await api.get(`/simulation/status/${runId}`);
                const status = response.data;

                setProgress(status);

                if (status.status === 'completed' || status.status === 'failed') {
                    setIsRunning(false);
                    if (status.status === 'failed') {
                        setError(status.error || 'Simulation failed');
                    }
                    return;
                }

                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(poll, 1000);
                } else {
                    setError('Simulation timed out');
                    setIsRunning(false);
                }
            } catch (err: any) {
                console.error('Status poll error:', err);
                setError('Failed to check simulation status');
                setIsRunning(false);
            }
        };

        await poll();
    };

    const runSimulation = useCallback(async (
        scenarioId: string,
        dateRange?: { start: string; end: string }
    ): Promise<string | null> => {
        setIsRunning(true);
        setError(null);
        setProgress({ status: 'pending', progress_percentage: 0 });

        try {
            const response = await api.post('/simulation/run', {
                run_type: 'ad_hoc',
                scenarios: [scenarioId],
                metadata: dateRange ? { date_range: dateRange } : undefined
            });

            const runId = response.data.run_id;

            // Start polling
            await pollStatus(runId);

            return runId;
        } catch (err: any) {
            console.error('Simulation start error:', err);
            setError(err.response?.data?.detail || 'Failed to start simulation');
            setIsRunning(false);
            return null;
        }
    }, []);

    return {
        runSimulation,
        progress,
        isRunning,
        error
    };
}
