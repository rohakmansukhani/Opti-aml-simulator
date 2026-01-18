'use client';

import { useBuilderStore } from '@/store/useBuilderStore';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Loader2, CheckCircle2, FileJson, AlertTriangle } from 'lucide-react';
import { MappingModal } from '@/components/ui/MappingModal';

export default function ReviewStep() {
    const { config, schema } = useBuilderStore();
    const router = useRouter();
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [showJson, setShowJson] = useState(false);
    const [testing, setTesting] = useState(false);
    const [testResults, setTestResults] = useState<any>(null);

    // Mapping State
    const [showMapping, setShowMapping] = useState(false);
    const [missingFields, setMissingFields] = useState<any[]>([]);
    const [confirmedMappings, setConfirmedMappings] = useState<Record<string, string> | null>(null);

    const handleTest = async (mappingsOverride: Record<string, string> | null = null) => {
        setTesting(true);
        // Clean previous errors/results
        setError('');
        setTestResults(null);

        // Use override if provided (recursion), otherwise use state if exists
        const activeMappings = mappingsOverride || confirmedMappings;

        try {
            // Run Test (Single call handles validation + preview)
            const payload = {
                ...config,
                limit: 10,
                field_mappings: activeMappings || {}
            };

            const res = await api.post('/api/simulation/preview', payload);

            if (res.data.status === 'validation_failed') {
                // Backend detected Schema Mismatch
                setMissingFields(res.data.missing_fields);
                setShowMapping(true);
                // Don't set results, just stop here
            } else {
                setTestResults(res.data);
            }
        } catch (e: any) {
            // Check if it's a backend error message response
            const msg = e.response?.data?.detail || e.response?.data?.message || 'Test failed. Check console.';
            // Set as test result error to show in that section
            setTestResults({ status: 'error', message: msg });
        } finally {
            setTesting(false);
        }
    };

    const handleMappingConfirm = (mappings: Record<string, string>) => {
        setConfirmedMappings(mappings);
        setShowMapping(false);
        // Immediately retry test with new mappings
        handleTest(mappings);
    };

    const handleSubmit = async () => {
        setSubmitting(true);
        setError('');
        try {
            // Check if we are updating an existing scenario or creating a new one
            if (config.scenario_id) {
                // Update existing
                await api.put(`/api/rules/scenarios/${config.scenario_id}`, {
                    scenario_name: config.scenario_name,
                    enabled: config.is_active,
                    config_json: config.config_json,
                    // Pass other fields if needed by backend model
                });
            } else {
                // Create new
                await api.post('/api/rules/scenarios', config);
            }

            router.push('/dashboard/rules'); // Redirect to Rules list instead of dashboard
        } catch (e: any) {
            setError(e.response?.data?.detail || 'Failed to save scenario');
            setSubmitting(false);
        }
    };

    // Helper to generate Natural Language
    const generateSummary = () => {
        const filters = config.config_json?.filters || [];
        const agg = config.config_json?.aggregation;
        const thresholds = config.config_json?.threshold || [];

        let parts = [];

        // 1. Scope
        if (filters.length > 0) {
            const filterText = filters.map(f => `${f.field} is ${f.operator} ${f.value}`).join(' AND ');
            parts.push(`Screening transactions where ${filterText}.`);
        } else {
            parts.push("Screening ALL transactions.");
        }

        // 2. Logic
        if (agg) {
            parts.push(`Calculating the ${agg.method || 'sum'} of ${agg.field || 'amounts'} per ${agg.group_by?.[0] || 'customer'} using a ${agg.time_window?.value}-day window.`);
        }

        // 3. Trigger
        if (thresholds && (thresholds as any).type) {
            const t = thresholds as any;
            if (t.type === 'fixed') {
                parts.push(`ALERTS when value exceeds ${t.fixed_value}.`);
            } else if (t.type === 'field_based') {
                parts.push(`ALERTS when value exceeds ${t.field_based?.field}.`);
            }
        }

        return parts.join(' ');
    };

    // Prepare available columns for dropdown
    const availableColumns = schema?.transactions?.map((c: any) => c.name) || [];

    return (
        <div className="space-y-8 max-w-3xl mx-auto">
            {/* Field Mapping Modal */}
            <MappingModal
                isOpen={showMapping}
                missingFields={missingFields}
                availableColumns={availableColumns}
                onConfirm={handleMappingConfirm}
                onCancel={() => { setShowMapping(false); setTesting(false); }}
            />

            <div className="text-center mb-6">
                <h2 className="text-3xl font-bold text-slate-900">Ready to Deploy?</h2>
                <p className="text-slate-500 mt-1">Review your logic in plain English.</p>
            </div>

            {/* Natural Language Card */}
            <div className="bg-gradient-to-br from-indigo-50 to-blue-50 border border-blue-100 rounded-3xl p-8 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                    <CheckCircle2 size={100} className="text-blue-600" />
                </div>

                <h3 className="font-bold text-blue-900 mb-4 flex items-center gap-2">
                    <span className="bg-blue-200 p-1 rounded text-xs px-2 uppercase tracking-wide">Summary</span>
                </h3>

                <p className="text-xl md:text-2xl text-blue-900 leading-relaxed font-medium">
                    "{generateSummary()}"
                </p>

                <div className="mt-8 flex gap-4 text-sm text-blue-700/70 border-t border-blue-200 pt-4">
                    <span className="flex items-center gap-1">
                        <AlertTriangle size={14} />
                        Priority: <span className="font-bold">{config.priority}</span>
                    </span>
                    <span>•</span>
                    <span>Active: <span className="font-bold">{config.is_active ? 'Yes' : 'No'}</span></span>
                </div>
            </div>

            {/* JSON Toggle */}
            <div className="text-center">
                <button
                    onClick={() => setShowJson(!showJson)}
                    className="text-slate-400 text-sm hover:text-slate-600 flex items-center justify-center gap-1 mx-auto"
                >
                    <FileJson size={14} />
                    {showJson ? 'Hide Technical Config' : 'View Technical JSON'}
                </button>
            </div>

            {showJson && (
                <div className="bg-slate-900 rounded-xl p-6 overflow-hidden shadow-inner animate-in fade-in slide-in-from-top-4 duration-300">
                    <pre className="text-blue-300 font-mono text-xs overflow-x-auto">
                        {JSON.stringify(config, null, 2)}
                    </pre>
                </div>
            )}

            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-lg flex items-center animate-in shake">
                    <span className="font-bold mr-2">Error:</span> {error}
                </div>
            )}

            {/* Test Logic Section */}
            <div className="border-t border-slate-100 pt-6">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h4 className="font-bold text-slate-800">Validation & Testing</h4>
                        <p className="text-xs text-slate-500">
                            Run this rule against a sample of recent transactions to preview results.
                        </p>
                    </div>
                    <button
                        onClick={() => handleTest(null)}
                        disabled={testing}
                        className="bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center gap-2 border border-amber-200"
                    >
                        {testing && <Loader2 size={14} className="animate-spin" />}
                        {testing ? 'Testing...' : '🔬 Test Logic'}
                    </button>
                </div>

                {/* Results Display */}
                {testResults?.status === 'success' ? (
                    <div className="bg-emerald-50 rounded-lg p-5 border border-emerald-200">
                        <div className="flex justify-between items-start mb-4">
                            <div>
                                <div className="text-4xl font-bold text-emerald-900">
                                    {testResults.alert_count}
                                </div>
                                <div className="text-sm text-emerald-600">alerts in sample</div>
                            </div>
                            <div className="text-right bg-white px-4 py-2 rounded-lg border border-emerald-200">
                                <div className="text-xs text-emerald-600 uppercase font-bold">
                                    Monthly Estimate
                                </div>
                                <div className="text-2xl font-bold text-emerald-900">
                                    ~{testResults.estimated_monthly_volume}
                                </div>
                            </div>
                        </div>

                        {testResults.sample_alerts?.length > 0 && (
                            <div className="space-y-2 mt-4">
                                <div className="text-xs font-bold text-emerald-700 uppercase">
                                    Sample Alerts Preview
                                </div>
                                {testResults.sample_alerts.map((alert: any, idx: number) => (
                                    <div key={idx} className="bg-white p-3 rounded text-sm border border-emerald-100 shadow-sm">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <span className="font-bold text-slate-800">
                                                    Customer: {alert.customer_id}
                                                </span>
                                                <div className="text-xs text-slate-500 mt-1">
                                                    Amount: {alert.trigger_details?.aggregated_value
                                                        ? Number(alert.trigger_details.aggregated_value).toFixed(2)
                                                        : 'N/A'}
                                                </div>
                                            </div>
                                            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded font-mono">
                                                {new Date(alert.alert_date).toLocaleDateString()}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="mt-3 pt-3 border-t border-emerald-200 text-xs text-emerald-600">
                            ✓ Tested on {testResults.sample_size} recent transactions
                            {/* Confirmed mappings notice */}
                            {confirmedMappings && (
                                <div className="mt-1 text-emerald-700 font-semibold">
                                    Applied {Object.keys(confirmedMappings).length} field mappings.
                                </div>
                            )}
                        </div>
                    </div>
                ) : testResults?.status === 'error' ? (
                    <div className="bg-red-50 p-4 rounded-lg border border-red-200">
                        <div className="flex items-start gap-2">
                            <AlertTriangle className="text-red-600" size={18} />
                            <div>
                                <div className="font-bold text-red-900 text-sm">Test Failed</div>
                                <p className="text-red-700 text-xs mt-1 font-mono break-all">{testResults.message}</p>
                            </div>
                        </div>
                    </div>
                ) : testResults?.status === 'no_data' ? (
                    <div className="bg-amber-50 p-4 rounded-lg border border-amber-200">
                        <div className="flex items-center gap-2">
                            <AlertTriangle className="text-amber-600" size={16} />
                            <span className="text-amber-700 text-sm">{testResults.message}</span>
                        </div>
                    </div>
                ) : (
                    <div className="bg-slate-50 rounded-lg p-4 border border-dashed border-slate-300 text-center">
                        <p className="text-slate-400 text-sm">
                            Click "Test Logic" to preview alert volume before deploying.
                        </p>
                    </div>
                )}
            </div>

            <div className="pt-4">
                <button
                    onClick={handleSubmit}
                    disabled={submitting}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-4 rounded-2xl font-bold text-lg shadow-xl shadow-blue-200 hover:shadow-2xl hover:-translate-y-1 transition-all flex justify-center items-center disabled:opacity-50 disabled:transform-none"
                >
                    {submitting ? <Loader2 className="animate-spin mr-2" /> : <CheckCircle2 className="mr-2" />}
                    Confirm & Deploy Rule
                </button>
            </div>
        </div>
    );
}
