/**
 * RuleSelector Component
 * 
 * Allows users to select baseline and refined scenarios for comparison
 */

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Search, GitCompare } from 'lucide-react';

interface Scenario {
    scenario_id: string;
    scenario_name: string;
    description: string;
    updated_at: string;
}

interface RuleSelectorProps {
    onSelect: (baselineId: string, refinedId: string) => void;
}

export function RuleSelector({ onSelect }: RuleSelectorProps) {
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [baselineId, setBaselineId] = useState<string>('');
    const [refinedId, setRefinedId] = useState<string>('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchScenarios();
    }, []);

    const fetchScenarios = async () => {
        try {
            const response = await api.get('/scenario-config/list');
            setScenarios(response.data);
        } catch (error) {
            console.error('Failed to load scenarios:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCompare = () => {
        if (baselineId && refinedId) {
            onSelect(baselineId, refinedId);
        }
    };

    if (loading) {
        return (
            <div className="bg-white rounded-lg shadow p-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-4 bg-slate-200 rounded w-1/4"></div>
                    <div className="h-10 bg-slate-200 rounded"></div>
                    <div className="h-10 bg-slate-200 rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center gap-2 mb-4">
                <GitCompare className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-semibold">Select Rules to Compare</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                {/* Baseline Selection */}
                <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                        Baseline Rule
                    </label>
                    <select
                        value={baselineId}
                        onChange={(e) => setBaselineId(e.target.value)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                        <option value="">Select baseline...</option>
                        {scenarios.map((scenario) => (
                            <option key={scenario.scenario_id} value={scenario.scenario_id}>
                                {scenario.scenario_name}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Refined Selection */}
                <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                        Refined Rule
                    </label>
                    <select
                        value={refinedId}
                        onChange={(e) => setRefinedId(e.target.value)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                        <option value="">Select refined...</option>
                        {scenarios.map((scenario) => (
                            <option key={scenario.scenario_id} value={scenario.scenario_id}>
                                {scenario.scenario_name}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <button
                onClick={handleCompare}
                disabled={!baselineId || !refinedId || baselineId === refinedId}
                className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
            >
                <div className="flex items-center justify-center gap-2">
                    <Search className="w-4 h-4" />
                    <span>Compare Rules</span>
                </div>
            </button>

            {baselineId === refinedId && baselineId && (
                <p className="text-sm text-amber-600 mt-2">
                    Please select two different rules to compare
                </p>
            )}
        </div>
    );
}
