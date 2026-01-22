'use client';

/**
 * Comparison Page - Compare Baseline vs Refined Simulation Runs
 * 
 * Features:
 * - High-level reduction metrics
 * - Customer-level granular diff
 * - Risk analysis visualization
 * - Sample exploits display
 */

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import {
    Play,
    Activity,
    ShieldAlert,
    TrendingDown,
    AlertTriangle,
    CheckCircle,
    XCircle,
    ArrowLeft,
    Users,
    DollarSign,
    GitCompare,
    ChevronDown,
    ArrowRight,
    Search,
    AlertCircle,
    Download
} from 'lucide-react';
import { formatDateIST } from '@/lib/date-utils';
import {
    CircularProgress,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions
} from '@mui/material';
import { motion } from 'framer-motion';

interface ComparisonSummary {
    baseline_alerts: number;
    refined_alerts: number;
    net_change: number;
    percent_reduction: number;
}

interface GranularDiffItem {
    customer_id: string;
    status: string;
    alert_count: number;
    total_amount: number;
    max_risk_score: number;
    scenarios: string[];
}

interface RiskAnalysis {
    risk_score: number;
    risk_level: string;
    sample_exploits: string[];
    high_risk_suppressions: number;
    total_suppressions: number;
}

interface ComparisonData {
    summary: ComparisonSummary;
    granular_diff: GranularDiffItem[];
    risk_analysis: RiskAnalysis;
    metadata: {
        baseline_run_id: string;
        refined_run_id: string;
        comparison_type: string;
    };
}

export default function ComparisonPage() {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center h-screen bg-slate-50">
                <CircularProgress size={40} className="text-blue-600" />
            </div>
        }>
            <ComparisonPageContent />
        </Suspense>
    );
}

function ComparisonPageContent() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [data, setData] = useState<ComparisonData | null>(null);

    // Selection State
    const [scenarios, setScenarios] = useState<any[]>([]);
    const [runs, setRuns] = useState<any[]>([]);
    const [selectedBaseline, setSelectedBaseline] = useState('');
    const [selectedRefined, setSelectedRefined] = useState('');
    const [fetchingData, setFetchingData] = useState(false);

    // Simulation Dialog State (Ported from Dashboard)
    const [runDialog, setRunDialog] = useState({ open: false, step: 'SELECT', side: '' });
    const [selectedModalScenarios, setSelectedModalScenarios] = useState<string[]>([]);
    const [dateRange, setDateRange] = useState({ start: '2024-01-01', end: new Date().toISOString().split('T')[0] });
    const [schemaStatus, setSchemaStatus] = useState<'idle' | 'checking' | 'valid' | 'invalid'>('idle');
    const [missingFields, setMissingFields] = useState<string[]>([]);
    const [availColumns, setAvailColumns] = useState<string[]>([]);
    const [fieldMappings, setFieldMappings] = useState<Record<string, string>>({});
    const [runError, setRunError] = useState<string>('');

    const baselineId = searchParams.get('baseline');
    const refinedId = searchParams.get('refined');
    const isComparisonMode = !!(baselineId && refinedId);

    useEffect(() => {
        if (isComparisonMode) {
            fetchComparison();
        } else {
            fetchRuns();
        }
    }, [baselineId, refinedId]);

    const fetchRuns = async () => {
        try {
            setFetchingData(true);
            const [scenariosRes, runsRes] = await Promise.all([
                api.get('/api/rules/scenarios'),
                api.get('/api/simulation/runs')
            ]);
            setScenarios(scenariosRes.data);
            setRuns(runsRes.data);
            setLoading(false);
        } catch (err) {
            console.error('Failed to fetch data', err);
            setError('Failed to load scenarios or runs');
            setLoading(false);
        } finally {
            setFetchingData(false);
        }
    };

    // Helper to check if a scenario has any runs
    const hasRuns = (scenarioId: string) => {
        return runs.some(run => run.scenarios_run?.includes(scenarioId));
    };

    // --- Simulation Dialog Logic (Ported from Dashboard) ---
    const openRunDialog = (scenarioId: string, side: string) => {
        setSelectedModalScenarios([scenarioId]);
        setRunDialog({ open: true, step: 'SELECT', side });
        setSchemaStatus('idle');
        setFieldMappings({});
        setRunError('');
    };

    const handleValidateSchema = async () => {
        setSchemaStatus('checking');
        try {
            const res = await api.post('/api/simulation/check-schema', {
                scenarios: selectedModalScenarios
            });
            if (res.data.status === 'missing_fields') {
                setMissingFields(res.data.missing_fields);
                setAvailColumns(res.data.available_columns || []);
                setSchemaStatus('invalid');
                setRunDialog(prev => ({ ...prev, step: 'MAPPING' }));
            } else {
                setSchemaStatus('valid');
            }
        } catch (err) {
            setRunError("Schema validation failed.");
            setSchemaStatus('valid');
        }
    };

    const handleRunConfirm = async () => {
        if (selectedModalScenarios.length === 0) return;
        if (schemaStatus === 'idle') {
            await handleValidateSchema();
            return;
        }
        try {
            setRunError('');
            await api.post('/api/simulation/run', {
                scenarios: selectedModalScenarios,
                date_range_start: new Date(dateRange.start).toISOString(),
                date_range_end: new Date(dateRange.end).toISOString(),
                field_mappings: fieldMappings
            });

            // On success, refresh and select
            const scenarioId = selectedModalScenarios[0];
            await fetchRuns(); // Refresh runs

            if (runDialog.side === 'A') setSelectedBaseline(scenarioId);
            else setSelectedRefined(scenarioId);

            setRunDialog({ open: false, step: 'SELECT', side: '' });
        } catch (err: any) {
            setRunError(err.response?.data?.detail || 'Failed to run simulation');
        }
    };

    const fetchComparison = async () => {
        try {
            setLoading(true);
            setError('');

            const response = await api.post('/api/comparison/compare', {
                baseline_run_id: baselineId,
                refined_run_id: refinedId
            });

            setData(response.data);
        } catch (err: any) {
            console.error('Comparison failed:', err);
            setError(err.response?.data?.detail || 'Failed to load comparison');
        } finally {
            setLoading(false);
        }
    };

    const handleCompare = () => {
        if (!selectedBaseline || !selectedRefined) return;
        router.push(`/dashboard/compare?baseline=${selectedBaseline}&refined=${selectedRefined}`);
    };

    const getRiskColor = (level: string) => {
        switch (level) {
            case 'SAFE': return 'text-green-600 bg-green-50';
            case 'CAUTION': return 'text-amber-600 bg-amber-50';
            case 'DANGEROUS': return 'text-orange-600 bg-orange-50';
            case 'CRITICAL': return 'text-red-600 bg-red-50';
            default: return 'text-slate-600 bg-slate-50';
        }
    };

    const getRiskIcon = (level: string) => {
        switch (level) {
            case 'SAFE': return <CheckCircle className="text-green-600" size={24} />;
            case 'CAUTION': return <AlertTriangle className="text-amber-600" size={24} />;
            case 'DANGEROUS': return <AlertTriangle className="text-orange-600" size={24} />;
            case 'CRITICAL': return <XCircle className="text-red-600" size={24} />;
            default: return <AlertTriangle className="text-slate-600" size={24} />;
        }
    };

    if (loading && isComparisonMode) {
        return (
            <div className="flex items-center justify-center h-screen">
                <CircularProgress />
            </div>
        );
    }

    // --- SELECTION VIEW ---
    if (!isComparisonMode) {
        if (loading || fetchingData) {
            return (
                <div className="flex items-center justify-center h-screen bg-slate-50">
                    <CircularProgress size={40} className="text-blue-600" />
                </div>
            );
        }

        return (
            <div className="min-h-screen bg-slate-50 p-8 flex flex-col items-center justify-center relative overflow-hidden">
                {/* Background Decoration */}
                <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                    <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-100/50 rounded-full blur-3xl" />
                    <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-100/50 rounded-full blur-3xl" />
                </div>

                <div className="w-full max-w-5xl z-10">
                    <div className="text-center mb-12">
                        <div className="inline-flex items-center justify-center p-3 bg-blue-50 rounded-2xl mb-4 shadow-sm">
                            <GitCompare className="text-blue-600" size={32} />
                        </div>
                        <h1 className="text-4xl font-extrabold text-slate-900 mb-3 tracking-tight">
                            Rule Logic Comparison
                        </h1>
                        <p className="text-lg text-slate-500 max-w-2xl mx-auto leading-relaxed">
                            Analyze the trade-off between <span className="font-semibold text-blue-600">Efficiency</span> and <span className="font-semibold text-red-600">Effectiveness</span> by comparing two rule configurations side-by-side.
                        </p>
                    </div>

                    <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8 md:p-12">
                        {scenarios.length < 2 ? (
                            <div className="bg-slate-50 rounded-2xl p-12 text-center border border-dashed border-slate-200 flex flex-col items-center max-w-lg mx-auto">
                                <Activity className="text-blue-500 mb-4" size={48} />
                                <h3 className="text-xl font-bold text-slate-900 mb-2">
                                    {scenarios.length === 0 ? 'No Rules Found' : 'More Rules Needed'}
                                </h3>
                                <p className="text-slate-500 mb-8">
                                    {scenarios.length === 0
                                        ? 'You haven\'t created any rule configurations yet. Head to the Rule Builder to get started.'
                                        : 'Comparison requires at least two different rule configurations. Create another one to see the impact of your changes.'}
                                </p>
                                <Button
                                    onClick={() => router.push('/dashboard/builder')}
                                    variant="contained"
                                    className="bg-blue-600 text-white hover:bg-blue-700 py-3 px-8 rounded-xl font-bold normal-case shadow-lg shadow-blue-200 transition-all hover:scale-105 active:scale-95 flex items-center"
                                >
                                    Go to Rule Builder
                                    <ArrowRight className="ml-2" size={18} />
                                </Button>
                            </div>
                        ) : (
                            <>
                                <div className="grid md:grid-cols-[1fr_auto_1fr] gap-8 items-center">

                                    {/* Rule Configuration A */}
                                    <div className="relative group">
                                        <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-300 to-indigo-300 rounded-2xl opacity-20 group-hover:opacity-40 transition duration-500 blur"></div>
                                        <div className="relative bg-white border border-slate-200 p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow">
                                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center">
                                                <span className="w-2 h-2 rounded-full bg-slate-400 mr-2"></span>
                                                Rule Configuration A
                                            </h3>

                                            <div className="space-y-4">
                                                <div className="space-y-4">
                                                    <div className="space-y-4">
                                                        <div className="relative">
                                                            <select
                                                                value={selectedBaseline}
                                                                onChange={(e) => setSelectedBaseline(e.target.value)}
                                                                className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none appearance-none cursor-pointer hover:bg-slate-100 transition-colors"
                                                            >
                                                                <option value="">Select a rule...</option>
                                                                {scenarios.map(s => (
                                                                    <option key={s.scenario_id} value={s.scenario_id}>
                                                                        {s.scenario_name} {hasRuns(s.scenario_id) ? '' : '(Needs Simulation)'}
                                                                    </option>
                                                                ))}
                                                            </select>
                                                            <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-slate-500">
                                                                <ChevronDown size={16} />
                                                            </div>
                                                        </div>

                                                        {!hasRuns(selectedBaseline) && selectedBaseline && (
                                                            <div className="p-4 bg-amber-50 rounded-xl border border-amber-100 flex flex-col items-center">
                                                                <p className="text-xs text-amber-600 font-medium mb-3 text-center">This rule needs simulation data</p>
                                                                <Button
                                                                    onClick={() => openRunDialog(selectedBaseline, 'A')}
                                                                    startIcon={<Play size={14} />}
                                                                    variant="contained"
                                                                    className="bg-amber-600 hover:bg-amber-700 shadow-none normal-case text-xs px-4"
                                                                >
                                                                    Simulate Now
                                                                </Button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Arrow Divider */}
                                    <div className="flex justify-center md:rotate-0 rotate-90 my-4 md:my-0">
                                        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 font-bold border border-slate-200">
                                            VS
                                        </div>
                                    </div>

                                    {/* Rule Configuration B */}
                                    <div className="relative group">
                                        <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-400 to-indigo-400 rounded-2xl opacity-20 group-hover:opacity-40 transition duration-500 blur"></div>
                                        <div className="relative bg-white border border-slate-200 p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow">
                                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center">
                                                <span className="w-2 h-2 rounded-full bg-blue-500 mr-2"></span>
                                                Rule Configuration B
                                            </h3>

                                            <div className="space-y-4">
                                                <div className="space-y-4">
                                                    <div className="space-y-4">
                                                        <div className="relative">
                                                            <select
                                                                value={selectedRefined}
                                                                onChange={(e) => setSelectedRefined(e.target.value)}
                                                                className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none appearance-none cursor-pointer hover:bg-slate-100 transition-colors"
                                                            >
                                                                <option value="">Select a rule...</option>
                                                                {scenarios.map(s => (
                                                                    <option key={s.scenario_id} value={s.scenario_id}>
                                                                        {s.scenario_name} {hasRuns(s.scenario_id) ? '' : '(Needs Simulation)'}
                                                                    </option>
                                                                ))}
                                                            </select>
                                                            <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-slate-500">
                                                                <ChevronDown size={16} />
                                                            </div>
                                                        </div>

                                                        {!hasRuns(selectedRefined) && selectedRefined && (
                                                            <div className="p-4 bg-amber-50 rounded-xl border border-amber-100 flex flex-col items-center">
                                                                <p className="text-xs text-amber-600 font-medium mb-3 text-center">This rule needs simulation data</p>
                                                                <Button
                                                                    onClick={() => openRunDialog(selectedRefined, 'B')}
                                                                    startIcon={<Play size={14} />}
                                                                    variant="contained"
                                                                    className="bg-amber-600 hover:bg-amber-700 shadow-none normal-case text-xs px-4"
                                                                >
                                                                    Simulate Now
                                                                </Button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="mt-10 flex flex-col items-center">
                                    <Button
                                        onClick={handleCompare}
                                        disabled={!selectedBaseline || !selectedRefined || selectedBaseline === selectedRefined || !hasRuns(selectedBaseline) || !hasRuns(selectedRefined)}
                                        variant="contained"
                                        className={`
                                            py-4 px-10 rounded-xl text-lg font-bold shadow-xl transition-all duration-300 transform hover:-translate-y-1 normal-case
                                            ${(!selectedBaseline || !selectedRefined || selectedBaseline === selectedRefined || !hasRuns(selectedBaseline) || !hasRuns(selectedRefined))
                                                ? 'bg-slate-200 text-slate-400 shadow-none'
                                                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 hover:shadow-blue-500/30 text-white'
                                            }
                                        `}
                                    >
                                        Compare Logic
                                        <ArrowRight className="ml-2 inline-block" size={20} />
                                    </Button>

                                    {selectedBaseline === selectedRefined && selectedBaseline && (
                                        <p className="text-center text-amber-600 bg-amber-50 px-4 py-2 rounded-lg text-sm mt-4 border border-amber-100 flex items-center animate-pulse">
                                            <AlertTriangle size={16} className="mr-2" />
                                            Please select two different configurations to compare.
                                        </p>
                                    )}
                                </div>
                            </>
                        )}
                    </div>

                    {/* Simulation Dialog (Ported from Dashboard) */}
                    <Dialog
                        open={runDialog.open}
                        onClose={() => setRunDialog({ ...runDialog, open: false })}
                        maxWidth="md"
                        fullWidth
                        PaperProps={{
                            style: { borderRadius: '16px', padding: '8px' }
                        }}
                    >
                        <DialogTitle className="font-bold text-xl border-b border-slate-100 pb-4">
                            {runDialog.step === 'SELECT' && 'Confirm Rule Selection'}
                            {runDialog.step === 'CONFIG' && 'Step 2: Simulation Parameters'}
                            {runDialog.step === 'MAPPING' && 'Step 3: Resolve Schema Mapping'}
                        </DialogTitle>
                        <DialogContent>
                            <div className="pt-6 min-h-[250px]">
                                {runDialog.step === 'SELECT' && (
                                    <div className="space-y-4">
                                        <div className="p-4 bg-blue-50 rounded-xl border border-blue-100 flex items-center">
                                            <Activity className="text-blue-600 mr-3" size={24} />
                                            <div>
                                                <p className="text-sm font-bold text-slate-900">Selected Rule:</p>
                                                <p className="text-sm text-slate-600">
                                                    {scenarios.find(s => s.scenario_id === selectedModalScenarios[0])?.scenario_name}
                                                </p>
                                            </div>
                                        </div>
                                        <p className="text-sm text-slate-500">
                                            This rule does not have any simulation data yet. We need to run a simulation on your data set to generate comparison metrics.
                                        </p>
                                    </div>
                                )}

                                {runDialog.step === 'CONFIG' && (
                                    <div className="space-y-6">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <label className="block text-sm font-medium text-slate-700 mb-1">Start Date</label>
                                                <input
                                                    type="date"
                                                    value={dateRange.start}
                                                    onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                                                    className="w-full border rounded-md p-2"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-slate-700 mb-1">End Date</label>
                                                <input
                                                    type="date"
                                                    value={dateRange.end}
                                                    onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                                                    className="w-full border rounded-md p-2"
                                                />
                                            </div>
                                        </div>
                                        {schemaStatus === 'checking' && <div className="flex items-center text-slate-500"><CircularProgress size={16} className="mr-2" /> Validating...</div>}
                                    </div>
                                )}

                                {runDialog.step === 'MAPPING' && (
                                    <div className="space-y-4">
                                        <div className="bg-amber-50 p-4 rounded-lg text-sm text-amber-800 flex items-start">
                                            <AlertTriangle className="mr-2 mt-0.5 shrink-0" size={16} />
                                            <div>
                                                <strong>Schema Mapping Required</strong>
                                                <p>Map the following required fields to columns in your data set.</p>
                                            </div>
                                        </div>
                                        <div className="border rounded-lg overflow-hidden">
                                            <table className="w-full text-sm text-left">
                                                <tbody className="divide-y">
                                                    {missingFields.map(field => (
                                                        <tr key={field}>
                                                            <td className="p-3 font-mono text-slate-600">{field}</td>
                                                            <td className="p-3">
                                                                <select
                                                                    className="w-full border rounded p-1.5"
                                                                    value={fieldMappings[field] || ''}
                                                                    onChange={(e) => setFieldMappings(prev => ({ ...prev, [field]: e.target.value }))}
                                                                >
                                                                    <option value="">Select Column...</option>
                                                                    {availColumns.map(col => (
                                                                        <option key={col} value={col}>{col}</option>
                                                                    ))}
                                                                </select>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {runError && (
                                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                                    {runError}
                                </div>
                            )}
                        </DialogContent>
                        <DialogActions className="p-4 border-t border-slate-100">
                            <Button onClick={() => setRunDialog({ ...runDialog, open: false })} className="text-slate-500">Cancel</Button>
                            <Button
                                variant="contained"
                                onClick={handleRunConfirm}
                                className="bg-blue-600 text-white hover:bg-blue-700 shadow-none normal-case"
                            >
                                {runDialog.step === 'SELECT' ? 'Next' : 'Run Simulation'}
                            </Button>
                        </DialogActions>
                    </Dialog>
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="p-8">
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center space-x-2">
                        <XCircle className="text-red-600" size={20} />
                        <p className="text-red-700">{error || 'No data available'}</p>
                    </div>
                </div>
                <Button
                    onClick={() => router.push('/dashboard/compare')}
                    className="mt-4"
                >
                    Back to Selection
                </Button>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 p-8">
            {/* Header */}
            <div className="mb-8">
                <Button
                    onClick={() => router.push('/dashboard/compare')} // Clean URL to go back to selection
                    startIcon={<ArrowLeft size={18} />}
                    className="mb-4 text-slate-500 hover:bg-slate-100 normal-case"
                >
                    Back to Selection
                </Button>

                <h1 className="text-3xl font-bold text-slate-900">
                    Rule Logic Comparison
                </h1>
                <p className="text-slate-600 mt-2">
                    Analyzing the trade-off between <span className="font-semibold text-blue-600">Efficiency</span> (Alert Volume) and <span className="font-semibold text-red-600">Effectiveness</span> (Security Coverage).
                </p>
            </div>

            {/* Critical Security Warning - The User's Main Concern */}
            {data.risk_analysis.total_suppressions > 0 && (
                <div className={`mb-8 p-6 rounded-xl border-l-4 shadow-sm ${data.risk_analysis.risk_level === 'SAFE'
                    ? 'bg-green-50 border-green-500'
                    : 'bg-amber-50 border-amber-500'
                    }`}>
                    <div className="flex items-start">
                        {data.risk_analysis.high_risk_suppressions > 0 ? (
                            <AlertTriangle className="text-amber-600 mt-1 mr-4 flex-shrink-0" size={28} />
                        ) : (
                            <CheckCircle className="text-green-600 mt-1 mr-4 flex-shrink-0" size={28} />
                        )}
                        <div>
                            <h3 className={`text-lg font-bold ${data.risk_analysis.risk_level === 'SAFE' ? 'text-green-900' : 'text-amber-900'
                                }`}>
                                {data.risk_analysis.high_risk_suppressions > 0
                                    ? "Potential Security Gaps Detected"
                                    : "Efficiency Improved Without Compromising Security"}
                            </h3>
                            <p className="text-slate-700 mt-1 leading-relaxed">
                                {data.risk_analysis.high_risk_suppressions > 0
                                    ? `While Rule B is more efficient (${data.summary.percent_reduction.toFixed(1)}% reduction), it missed ${data.risk_analysis.high_risk_suppressions} high-risk alerts that were caught by Rule A. This indicates a potential "opening for money laundering".`
                                    : `Rule B successfully reduced alert volume by ${data.summary.percent_reduction.toFixed(1)}% without missing any critical high-risk alerts caught by Rule A.`
                                }
                            </p>
                        </div>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                {/* 1. Efficiency Metrics (Volume) */}
                <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
                    <h2 className="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <TrendingDown className="mr-2 text-blue-600" size={20} />
                        Efficiency Gains (Volume Reduction)
                    </h2>

                    <div className="grid grid-cols-2 gap-6">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-sm text-slate-500 mb-1">Rule A Volume</div>
                            <div className="text-2xl font-bold text-slate-900">{data.summary.baseline_alerts}</div>
                            <div className="text-xs text-slate-400 mt-1">Initial Alerts</div>
                        </div>
                        <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                            <div className="text-sm text-blue-600 mb-1">Rule B Volume</div>
                            <div className="text-2xl font-bold text-blue-700">{data.summary.refined_alerts}</div>
                            <div className="text-xs text-blue-400 mt-1">Comparison Alerts</div>
                        </div>
                    </div>

                    <div className="mt-6 pt-6 border-t border-slate-100">
                        <div className="flex items-center justify-between">
                            <span className="text-slate-600 font-medium">Efficiency Improvement</span>
                            <span className="text-2xl font-bold text-blue-600">{data.summary.percent_reduction.toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2 mt-3">
                            <div
                                className="bg-blue-600 h-2 rounded-full transition-all duration-1000"
                                style={{ width: `${Math.min(data.summary.percent_reduction, 100)}%` }}
                            />
                        </div>
                    </div>
                </div>

                {/* 2. Security Impact (Missed Risks) */}
                <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200">
                    <h2 className="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <AlertTriangle className="mr-2 text-red-600" size={20} />
                        Security Impact (Missed Risks)
                    </h2>

                    <div className="grid grid-cols-2 gap-6">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-sm text-slate-500 mb-1">Total Suppressed</div>
                            <div className="text-2xl font-bold text-slate-900">{data.risk_analysis.total_suppressions}</div>
                            <div className="text-xs text-slate-400 mt-1">Caught by A, missed by B</div>
                        </div>
                        <div className={`p-4 rounded-xl border ${data.risk_analysis.high_risk_suppressions > 0 ? 'bg-red-50 border-red-100' : 'bg-green-50 border-green-100'}`}>
                            <div className={`text-sm mb-1 ${data.risk_analysis.high_risk_suppressions > 0 ? 'text-red-600' : 'text-green-600'}`}>High Risk Missed</div>
                            <div className={`text-2xl font-bold ${data.risk_analysis.high_risk_suppressions > 0 ? 'text-red-700' : 'text-green-700'}`}>
                                {data.risk_analysis.high_risk_suppressions}
                            </div>
                            <div className={`text-xs mt-1 ${data.risk_analysis.high_risk_suppressions > 0 ? 'text-red-400' : 'text-green-400'}`}>Critical Vulnerabilities</div>
                        </div>
                    </div>

                    {/* Sample Exploits List */}
                    <div className="mt-6 pt-6 border-t border-slate-100">
                        <h4 className="text-sm font-semibold text-slate-700 mb-3">Detected Vulnerabilities (Sample)</h4>
                        {data.risk_analysis.sample_exploits.length > 0 ? (
                            <div className="space-y-2">
                                {data.risk_analysis.sample_exploits.slice(0, 2).map((exploit, idx) => (
                                    <div key={idx} className="bg-red-50 text-red-700 px-3 py-2 rounded text-xs border border-red-100 flex items-start">
                                        <XCircle size={14} className="mr-2 mt-0.5 flex-shrink-0" />
                                        {exploit}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-sm text-slate-400 italic flex items-center">
                                <CheckCircle size={16} className="mr-2 text-green-500" />
                                No prominent security gaps detected in sample.
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Granular Diff Table */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200">
                <div className="p-6 border-b border-slate-200 flex justify-between items-center">
                    <div>
                        <h2 className="text-xl font-bold text-slate-900">
                            Impact Analysis Details
                        </h2>
                        <p className="text-sm text-slate-600 mt-1">
                            Specific customers/cases where Rule B produced different results than Rule A
                        </p>
                    </div>
                    <Button
                        variant="outlined"
                        startIcon={<Download size={16} />}
                        onClick={() => {
                            const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/comparison/export?baseline_run_id=${baselineId}&refined_run_id=${refinedId}`;
                            window.open(url, '_blank');
                        }}
                        className="normal-case border-slate-300 text-slate-700 hover:bg-slate-50"
                    >
                        Export CSV
                    </Button>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase">Customer ID</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase">Alert Count Impact</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase">Total Amount</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase">Risk Score</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase">Affected Scenarios</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                            {data.granular_diff.map((item, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                    <td className="px-6 py-4 text-sm font-medium text-slate-900">
                                        {item.customer_id}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-slate-600">
                                        <div className="flex items-center">
                                            <span className="font-mono bg-slate-100 px-2 rounded mr-2">{item.alert_count}</span>
                                            <span className="text-xs text-slate-400">suppressed</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-slate-900 font-medium">
                                        ${item.total_amount.toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${item.max_risk_score > 70 ? 'bg-red-100 text-red-700' :
                                            item.max_risk_score > 50 ? 'bg-amber-100 text-amber-700' :
                                                'bg-green-100 text-green-700'
                                            }`}>
                                            {item.max_risk_score.toFixed(1)}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-slate-600">
                                        {item.scenarios.join(', ')}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
