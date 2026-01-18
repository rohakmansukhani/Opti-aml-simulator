import { create } from 'zustand';
import { ScenarioConfig, ScenarioDefinition, FilterConfig, AggregationConfig, ThresholdConfig } from '@/types/schema';

interface BuilderState {
    currentStep: number;
    config: Partial<ScenarioConfig>;
    // Actions
    nextStep: () => void;
    prevStep: () => void;
    setStep: (step: number) => void;
    updateConfig: (updates: Partial<ScenarioConfig>) => void;
    updateNestedConfig: <K extends keyof ScenarioDefinition>(
        key: K,
        value: ScenarioDefinition[K]
    ) => void;
    reset: () => void;
    schema: any; // Using any for prototype, ideally typed
    fetchSchema: () => Promise<void>;
}

const INITIAL_CONFIG: Partial<ScenarioConfig> = {
    scenario_name: '',
    priority: 'Medium',
    is_active: true,
    config_json: {
        filters: [],
        threshold: { // Default to Fixed
            type: 'fixed',
            fixed_value: 0
        },
        trigger_condition: '',
        aggregation: {
            group_by: ['customer_id'],
            time_window: { value: 30, unit: 'days', type: 'rolling' },
            method: 'sum',
            field: 'transaction_amount'
        }
    }
};

export const useBuilderStore = create<BuilderState>((set) => ({
    currentStep: 0,
    config: JSON.parse(JSON.stringify(INITIAL_CONFIG)), // Deep copy init

    nextStep: () => set((state) => ({ currentStep: state.currentStep + 1 })),
    prevStep: () => set((state) => ({ currentStep: Math.max(0, state.currentStep - 1) })),
    setStep: (step) => set({ currentStep: step }),

    updateConfig: (updates) => set((state) => ({
        config: { ...state.config, ...updates }
    })),

    updateNestedConfig: (key, value) => set((state) => ({
        config: {
            ...state.config,
            config_json: {
                ...state.config.config_json!,
                [key]: value
            }
        }
    })),

    reset: () => set({ currentStep: 0, config: JSON.parse(JSON.stringify(INITIAL_CONFIG)) }),

    // Schema Data
    schema: null,
    fetchSchema: async () => {
        try {
            // Use the strict API client (injects x-db-url header)
            const { api } = await import('@/lib/api');
            const res = await api.get('/api/data/schema');
            if (res.status === 200) {
                set({ schema: res.data });
            }
        } catch (e) {
            console.error("Failed to fetch schema", e);
        }
    }
}));
