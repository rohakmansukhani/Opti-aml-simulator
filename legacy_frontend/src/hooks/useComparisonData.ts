/**
 * Custom hook for managing comparison data fetching and state
 * 
 * Handles:
 * - Fetching comparison data between baseline and refined runs
 * - Loading states
 * - Error handling
 * - Data transformation
 */

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

interface ComparisonData {
    summary: {
        baseline_alerts: number;
        refined_alerts: number;
        net_change: number;
        percent_reduction: number;
    };
    customer_level_diff: Array<{
        customer_id: string;
        customer_name: string;
        baseline_alerts: number;
        refined_alerts: number;
        net_change: number;
    }>;
    risk_analysis: {
        high_risk_reduction: number;
        medium_risk_reduction: number;
        low_risk_increase: number;
    };
    sample_exploits: Array<{
        customer_id: string;
        customer_name: string;
        alert_type: string;
        details: any;
    }>;
}

interface UseComparisonDataReturn {
    data: ComparisonData | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useComparisonData(
    baselineId: string | null,
    refinedId: string | null
): UseComparisonDataReturn {
    const [data, setData] = useState<ComparisonData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchComparison = async () => {
        if (!baselineId || !refinedId) {
            setData(null);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await api.post('/comparison/compare', {
                baseline_run_id: baselineId,
                refined_run_id: refinedId
            });

            setData(response.data);
        } catch (err: any) {
            console.error('Comparison fetch error:', err);
            setError(err.response?.data?.detail || 'Failed to load comparison data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchComparison();
    }, [baselineId, refinedId]);

    return {
        data,
        loading,
        error,
        refetch: fetchComparison
    };
}
