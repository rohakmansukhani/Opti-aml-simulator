'use client';

import { useSessionStore } from '@/store/useSessionStore';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { motion } from 'framer-motion';
import {
    Play,
    AlertTriangle,
    ShieldAlert,
    TrendingUp,
    Activity,
    ArrowRight,
    Database
} from 'lucide-react';
import { formatDateIST } from '@/lib/date-utils';
import {
    Card,
    CardContent,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    CircularProgress
} from '@mui/material';

// Interface for Scenarios
interface Scenario {
    scenario_id: string;
    scenario_name: string;
    enabled: boolean;
}

export default function Dashboard() {
    const { isConnected, mode, dbUrl } = useSessionStore();
    const router = useRouter();
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Simulation Dialog State
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [runDialog, setRunDialog] = useState({ open: false, step: 'SELECT' }); // steps: SELECT, CONFIG, MAPPING
    const [selectedScenarios, setSelectedScenarios] = useState<string[]>([]);

    // Config State
    const [dateRange, setDateRange] = useState({ start: '2024-01-01', end: new Date().toISOString().split('T')[0] });
    const [schemaStatus, setSchemaStatus] = useState<'idle' | 'checking' | 'valid' | 'invalid'>('idle');
    const [missingFields, setMissingFields] = useState<string[]>([]);
    const [availColumns, setAvailColumns] = useState<string[]>([]); // For mapping dropdown
    const [fieldMappings, setFieldMappings] = useState<Record<string, string>>({});
    const [runError, setRunError] = useState<string>(''); // Inline error state

    useEffect(() => {
        if (!isConnected) {
            router.push('/');
            return;
        }

        const fetchData = async () => {
            try {
                // Fetch Scenarios and Stats in parallel
                const [statsRes, scenariosRes] = await Promise.all([
                    api.get('/api/dashboard/stats'),
                    api.get('/api/config/scenarios')
                ]);

                if (statsRes.status === 200) setStats(statsRes.data);
                if (scenariosRes.status === 200) setScenarios(scenariosRes.data);

            } catch (e: any) {
                console.error("Failed to fetch data", e);
                // Graceful fallback if stats fail
                setStats((prev: any) => prev || {
                    risk_score: "N/A",
                    active_high_risk_alerts: 0,
                    transactions_scanned: 0,
                    system_coverage: "0%",
                    total_simulations: 0,
                    recent_simulations: []
                });
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [isConnected, router, dbUrl]);

    const openRunDialog = () => {
        // Default select all enabled scenarios
        const enabledIds = scenarios.filter(s => s.enabled).map(s => s.scenario_id);
        setSelectedScenarios(enabledIds);
        setRunDialog({ open: true, step: 'SELECT' });
        setSchemaStatus('idle');
        setFieldMappings({});
    };

    const toggleRuleSelection = (id: string) => {
        setSelectedScenarios(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
        );
    };

    // Step 2: Validate Schema
    const handleValidateSchema = async () => {
        setSchemaStatus('checking');
        try {
            const res = await api.post('/api/simulation/check-schema', {
                scenarios: selectedScenarios
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
            console.error("Schema check failed", err);
            setRunError("Failed to validate schema. Proceeding with caution.");
            setSchemaStatus('valid'); // Bypass
        }
    };

    const handleRunConfirm = async () => {
        if (selectedScenarios.length === 0) return;

        // If not validated yet, validate first
        if (schemaStatus === 'idle') {
            await handleValidateSchema();
            // If invalid, it will switch step to MAPPING, return here
            return;
        }

        // Execute Run
        setRunError(''); // Clear previous errors
        try {
            await api.post('/api/simulation/run', {
                scenarios: selectedScenarios,
                date_range_start: new Date(dateRange.start).toISOString(),
                date_range_end: new Date(dateRange.end).toISOString(),
                field_mappings: fieldMappings
            });
            // Success - close dialog and navigate to reports
            setRunDialog({ open: false, step: 'SELECT' });
            router.push('/dashboard/reports');
        } catch (err: any) {
            setRunError(err.response?.data?.detail || 'Failed to run simulation');
        }
    };

    const isRunReady = schemaStatus === 'valid' || (runDialog.step === 'MAPPING' && Object.keys(fieldMappings).length === missingFields.length);

    if (!isConnected) return null;
    if (loading) return <div className="p-8">Loading...</div>;

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
                    <p className="text-slate-500 mt-1">Enterprise Simulation Environment</p>
                </div>
                <div onClick={openRunDialog} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg flex items-center font-medium shadow-sm cursor-pointer">
                    <Play size={18} className="mr-2" />
                    Run New Simulation
                </div>
            </div>

            {/* Existing Cards Section */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <Card className="rounded-2xl border-l-4 border-l-blue-500">
                    <CardContent className="p-6">
                        <div className="text-3xl font-bold text-slate-900 mb-1">{stats?.risk_score || 'N/A'}</div>
                        <div className="text-sm text-slate-500">Current Risk Level</div>
                    </CardContent>
                </Card>
                <Card className="rounded-2xl border-l-4 border-l-amber-500">
                    <CardContent className="p-6">
                        <div className="text-3xl font-bold text-slate-900 mb-1">{stats?.active_high_risk_alerts || 0}</div>
                        <div className="text-sm text-slate-500">Active High-Risk Alerts</div>
                    </CardContent>
                </Card>
                <Card className="rounded-2xl border-l-4 border-l-emerald-500">
                    <CardContent className="p-6">
                        <div className="text-3xl font-bold text-slate-900 mb-1">{stats?.transactions_scanned?.toLocaleString() || 0}</div>
                        <div className="text-sm text-slate-500">Transactions Scanned</div>
                    </CardContent>
                </Card>
                <Card className="rounded-2xl border-l-4 border-l-slate-500">
                    <CardContent className="p-6">
                        <div className="text-3xl font-bold text-slate-900 mb-1">{stats?.system_coverage || '0%'}</div>
                        <div className="text-sm text-slate-500">System Coverage</div>
                    </CardContent>
                </Card>
            </div>

            {/* Recent Activty */}
            <Card className="rounded-2xl border-none shadow-sm">
                <CardContent className="p-0">
                    <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
                        <h3 className="font-semibold text-slate-900">Recent Simulations</h3>
                        <button className="text-blue-600 text-sm font-medium hover:underline" onClick={() => router.push('/dashboard/reports')}>View All</button>
                    </div>
                    <div className="divide-y divide-slate-100">
                        {stats?.recent_simulations?.map((run: any, index: number) => {
                            // Calculate sequential ID: total - index (since sorted DESC, newest first)
                            const seqId = (stats?.total_simulations || 0) - index;

                            return (
                                <div key={run.run_id} onClick={() => router.push('/dashboard/reports')} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50 cursor-pointer">
                                    <div>
                                        <div className="font-medium text-slate-900">Simulation Run #{seqId}</div>
                                        <div className="text-sm text-slate-500">{formatDateIST(run.created_at)} • {run.total_alerts} Alerts</div>
                                    </div>
                                    <span className={`px-2 py-1 rounded-full text-xs font-bold ${run.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{run.status}</span>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>

            {/* Upgraded Multi-Step Dialog */}
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
                    {runDialog.step === 'SELECT' && 'Step 1: Select Scenarios'}
                    {runDialog.step === 'CONFIG' && 'Step 2: Configuration'}
                    {runDialog.step === 'MAPPING' && 'Step 3: Resolve Schema Mapping'}
                </DialogTitle>
                <DialogContent>
                    <div className="pt-6 min-h-[300px]">
                        {runDialog.step === 'SELECT' && (
                            <div className="space-y-6">
                                <div className="flex justify-between items-center">
                                    <p className="text-slate-600">Select the rules to include in this simulation run.</p>
                                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-medium">
                                        {selectedScenarios.length} Selected
                                    </span>
                                </div>

                                {scenarios.length === 0 ? (
                                    <div className="text-center py-12 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                                        <ShieldAlert className="mx-auto h-12 w-12 text-slate-300 mb-3" />
                                        <h3 className="text-lg font-medium text-slate-900">No Scenarios Found</h3>
                                        <p className="text-slate-500 max-w-sm mx-auto mt-1">
                                            You haven't defined any detection rules yet.
                                        </p>
                                        <Button
                                            variant="outlined"
                                            className="mt-4 normal-case"
                                            onClick={() => router.push('/dashboard/builder')}
                                        >
                                            Go to Builder
                                        </Button>
                                    </div>
                                ) : (
                                    <div className="max-h-[400px] overflow-y-auto border border-slate-200 rounded-xl divide-y divide-slate-100 shadow-sm">
                                        {scenarios.map(s => (
                                            <div
                                                key={s.scenario_id}
                                                onClick={() => toggleRuleSelection(s.scenario_id)}
                                                className={`p-4 flex items-center justify-between cursor-pointer transition-colors ${selectedScenarios.includes(s.scenario_id)
                                                    ? 'bg-blue-50/80 hover:bg-blue-50'
                                                    : 'hover:bg-slate-50'
                                                    }`}
                                            >
                                                <div className="flex items-center space-x-3">
                                                    <div className={`p-2 rounded-lg ${selectedScenarios.includes(s.scenario_id) ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-500'}`}>
                                                        <Activity size={18} />
                                                    </div>
                                                    <div>
                                                        <div className="font-medium text-slate-900">{s.scenario_name}</div>
                                                        <div className="text-xs text-slate-500">ID: {s.scenario_id}</div>
                                                    </div>
                                                </div>

                                                <div className={`h-6 w-6 rounded-full border-2 flex items-center justify-center transition-colors ${selectedScenarios.includes(s.scenario_id)
                                                    ? 'bg-blue-600 border-blue-600'
                                                    : 'border-slate-300'
                                                    }`}>
                                                    {selectedScenarios.includes(s.scenario_id) && (
                                                        <motion.svg
                                                            initial={{ scale: 0 }}
                                                            animate={{ scale: 1 }}
                                                            className="w-3.5 h-3.5 text-white"
                                                            viewBox="0 0 24 24"
                                                            fill="none"
                                                            stroke="currentColor"
                                                            strokeWidth="4"
                                                            strokeLinecap="round"
                                                            strokeLinejoin="round"
                                                        >
                                                            <polyline points="20 6 9 17 4 12" />
                                                        </motion.svg>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {runDialog.step === 'CONFIG' && (
                            <div className="space-y-6">
                                <div className="bg-blue-50 p-4 rounded-lg text-sm text-blue-800">
                                    Define the data scope. The engine will filter transactions within this range.
                                </div>
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

                                {schemaStatus === 'checking' && <div className="flex items-center text-slate-500"><CircularProgress size={16} className="mr-2" /> Validating Schema Compatibility...</div>}
                                {schemaStatus === 'valid' && <div className="flex items-center text-green-600"><TrendingUp size={16} className="mr-2" /> Schema Compatible - Ready to Run</div>}
                            </div>
                        )}

                        {runDialog.step === 'MAPPING' && (
                            <div className="space-y-4">
                                <div className="bg-amber-50 p-4 rounded-lg text-sm text-amber-800 flex items-start">
                                    <AlertTriangle className="mr-2 mt-0.5 shrink-0" size={16} />
                                    <div>
                                        <strong>Schema Mismatch Detected</strong>
                                        <p>The selected rules require fields that are missing from your database. Please map them to available columns.</p>
                                    </div>
                                </div>

                                <div className="border rounded-lg overflow-hidden">
                                    <table className="w-full text-sm text-left">
                                        <thead className="bg-slate-50 text-slate-700 font-medium">
                                            <tr>
                                                <th className="p-3 border-b">Required Field</th>
                                                <th className="p-3 border-b">Map to Database Column</th>
                                            </tr>
                                        </thead>
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

                    {/* Inline Error Display */}
                    {runError && (
                        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                            <div className="flex items-start space-x-2">
                                <AlertTriangle className="text-red-600 flex-shrink-0 mt-0.5" size={18} />
                                <p className="text-sm text-red-700">{runError}</p>
                            </div>
                        </div>
                    )}
                </DialogContent>
                <DialogActions>
                    {runDialog.step === 'SELECT' && (
                        <>
                            <Button onClick={() => setRunDialog({ ...runDialog, open: false })}>Cancel</Button>
                            <div className="flex flex-col items-end">
                                <Button
                                    variant="contained"
                                    onClick={() => setRunDialog(p => ({ ...p, step: 'CONFIG' }))}
                                    disabled={selectedScenarios.length === 0}
                                    className={`
                                        transition-colors
                                        ${selectedScenarios.length === 0
                                            ? '!bg-slate-200 !text-slate-400'
                                            : 'bg-blue-600 text-white hover:bg-blue-700'}
                                    `}
                                >
                                    Next
                                </Button>
                                {selectedScenarios.length === 0 && (
                                    <span className="text-[10px] text-red-500 mt-1 font-medium">Select a rule</span>
                                )}
                            </div>
                        </>
                    )}
                    {runDialog.step === 'CONFIG' && (
                        <>
                            <Button onClick={() => setRunDialog(p => ({ ...p, step: 'SELECT' }))}>Back</Button>
                            <Button
                                variant="contained"
                                onClick={handleRunConfirm}
                                className={schemaStatus === 'valid' ? 'bg-green-600 text-white hover:bg-green-700' : 'bg-blue-600 text-white hover:bg-blue-700'}
                            >
                                {schemaStatus === 'valid' ? 'Start Simulation' : 'Validate & Run'}
                            </Button>
                        </>
                    )}
                    {runDialog.step === 'MAPPING' && (
                        <>
                            <Button onClick={() => setRunDialog(p => ({ ...p, step: 'CONFIG' }))}>Back</Button>
                            <Button
                                variant="contained"
                                onClick={handleRunConfirm}
                                disabled={missingFields.some(f => !fieldMappings[f])}
                                className="bg-amber-600 text-white hover:bg-amber-700 disabled:bg-slate-300"
                            >
                                Confirm Mapping & Run
                            </Button>
                        </>
                    )}
                </DialogActions>
            </Dialog>
        </div >
    );
}
