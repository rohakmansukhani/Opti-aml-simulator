'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
    Card,
    CardContent,
    CircularProgress,
    Alert as MuiAlert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper
} from '@mui/material';
import { FileText, Download, Calendar, TrendingUp } from 'lucide-react';
import { formatDateIST, formatIST } from '@/lib/date-utils';

interface ReportSummary {
    total_scenarios: number;
    total_alerts: number;
    active_scenarios: number;
    last_run: string;
}

interface Report {
    report_id: string;
    title: string;
    created_at: string;
    type: string;
    alert_count: number;
    status: string;
}

// Interface for Alert Details
interface AlertDetail {
    alert_id: string;
    customer_id: string;
    customer_name?: string;
    scenario_name: string;
    risk_score: number;
    alert_date: string;
}

export default function ReportsPage() {
    const [summary, setSummary] = useState<ReportSummary | null>(null);
    const [reports, setReports] = useState<Report[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Details Dialog State
    const [detailsDialog, setDetailsDialog] = useState<{ open: boolean; runId: string; alerts: AlertDetail[]; loading: boolean }>({
        open: false,
        runId: '',
        alerts: [],
        loading: false
    });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            setLoading(true);

            // Fetch summary statistics & runs in parallel
            const [scenariosRes, runsRes] = await Promise.all([
                api.get('/api/rules/scenarios'),
                api.get('/api/simulation/runs')
            ]);

            const scenarios = scenariosRes.data;
            const runs = runsRes.data;

            // Calculate total alerts from all completed runs
            const allAlerts = runs.reduce((acc: number, r: any) => acc + (r.total_alerts || 0), 0);

            setSummary({
                total_scenarios: scenarios.length,
                active_scenarios: scenarios.filter((s: any) => s.enabled).length,
                total_alerts: allAlerts,
                last_run: runs.length > 0 ? runs[0].created_at : 'Never'
            });

            // Map runs to reports UI with Sequential IDs
            const totalRuns = runs.length;
            const mappedReports: Report[] = runs.map((r: any, index: number) => {
                // Since runs are usually DESC (newest first), ID = Total - Index
                // If runs are ASC, ID = Index + 1. 
                // Assuming API returns DESC (Newest first) based on previous code.
                const seqId = totalRuns - index;

                return {
                    report_id: r.run_id,
                    title: `Simulation Run #${seqId}`,
                    created_at: r.created_at,
                    type: r.run_type === 'baseline' ? 'Full Scan' : 'Ad-hoc Test',
                    alert_count: r.total_alerts,
                    status: r.status
                };
            });

            setReports(mappedReports);

        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load reports data');
        } finally {
            setLoading(false);
        }
    };

    const handleViewDetails = async (runId: string) => {
        setDetailsDialog({ open: true, runId, alerts: [], loading: true });

        try {
            const res = await api.get(`/api/simulation/${runId}/alerts`);
            setDetailsDialog(prev => ({
                ...prev,
                alerts: res.data,
                loading: false
            }));
        } catch (err) {
            console.error("Failed to load alerts", err);
            // Optionally set error state within dialog
            setDetailsDialog(prev => ({ ...prev, loading: false }));
        }
    };

    const handleDownload = (runId: string) => {
        // Direct download via window.open using baseURL
        // Assuming /api/simulation/... is accessible directly if no auth header needed for download OR
        // if auth is cookie based. 
        // If Bearer token is needed, we usually need to fetch blob in JS.
        // For simplicity, trying direct open (often works if auth cookie is set).
        // If direct open fails due to auth, we'll need fetch blob approach.
        // Since api.get works, let's try fetch blob.

        downloadReportBlob(runId);
    };

    const downloadReportBlob = async (runId: string) => {
        try {
            const response = await api.get(`/api/simulation/${runId}/export/excel`, {
                responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `simulation_results_${runId}.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error("Download failed", err);
            // Error is already visible in UI through failed state
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen">
                <CircularProgress />
            </div>
        );
    }

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-8">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-slate-900">Reports & Analytics</h1>
                <p className="text-slate-500 mt-1">View statistics and export compliance reports</p>
            </div>

            {/* Error */}
            {error && (
                <MuiAlert severity="error" onClose={() => setError('')}>
                    {error}
                </MuiAlert>
            )}

            {/* Summary Cards */}
            {summary && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <Card className="shadow-lg">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-slate-600">Total Scenarios</span>
                                <FileText size={20} className="text-blue-500" />
                            </div>
                            <div className="text-3xl font-bold text-slate-900">{summary.total_scenarios}</div>
                        </CardContent>
                    </Card>

                    <Card className="shadow-lg">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-slate-600">Active Rules</span>
                                <TrendingUp size={20} className="text-green-500" />
                            </div>
                            <div className="text-3xl font-bold text-slate-900">{summary.active_scenarios}</div>
                        </CardContent>
                    </Card>

                    <Card className="shadow-lg">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-slate-600">Total Alerts Generated</span>
                                <TrendingUp size={20} className="text-orange-500" />
                            </div>
                            <div className="text-3xl font-bold text-slate-900">{summary.total_alerts}</div>
                        </CardContent>
                    </Card>

                    <Card className="shadow-lg">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-slate-600">Last Simulation</span>
                                <Calendar size={20} className="text-purple-500" />
                            </div>
                            <div className="text-sm font-bold text-slate-900">
                                {summary.last_run !== 'Never' ? formatDateIST(summary.last_run) : 'Never'}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Reports List */}
            <h2 className="text-xl font-bold text-slate-900 pt-4">Simulation History</h2>
            {reports.length === 0 ? (
                <Card className="shadow-lg border-none">
                    <CardContent className="p-12 text-center">
                        <FileText size={48} className="mx-auto text-slate-300 mb-4" />
                        <h3 className="text-xl font-bold text-slate-900 mb-2">No Reports Yet</h3>
                        <p className="text-slate-500">
                            Run simulations to generate compliance reports
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {reports.map((report) => (
                        <Card
                            key={report.report_id}
                            className="hover:shadow-xl transition-shadow cursor-pointer border border-slate-100"
                            onClick={() => handleViewDetails(report.report_id)}
                        >
                            <CardContent className="p-6">
                                <div className="flex justify-between items-start mb-4">
                                    <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
                                        <FileText size={24} />
                                    </div>
                                    <span className={`text-xs font-bold px-2 py-1 rounded uppercase ${report.status === 'completed' ? 'bg-green-100 text-green-700' :
                                        report.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
                                        }`}>
                                        {report.status}
                                    </span>
                                </div>

                                <h3 className="font-bold text-slate-900 mb-0.5">{report.title}</h3>
                                <div className="text-xs font-mono text-slate-400 mb-3 select-all">ID: {report.report_id}</div>
                                <div className="flex items-center text-sm text-slate-500 mb-4">
                                    <Calendar size={14} className="mr-1.5" />
                                    {formatIST(report.created_at)}
                                </div>

                                <div className="bg-slate-50 p-3 rounded mb-4 text-sm flex justify-between">
                                    <span className="text-slate-600">Type: {report.type}</span>
                                    <span className="font-semibold text-slate-900">{report.alert_count} Alerts</span>
                                </div>

                                <button
                                    onClick={(e) => {
                                        e.stopPropagation(); // Prevent card click
                                        handleDownload(report.report_id);
                                    }}
                                    className="w-full py-2 border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 flex items-center justify-center transition-colors"
                                >
                                    <Download size={16} className="mr-2" />
                                    Download Excel
                                </button>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Details Dialog */}
            <Dialog
                open={detailsDialog.open}
                onClose={() => setDetailsDialog(prev => ({ ...prev, open: false }))}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle className="flex justify-between items-center">
                    Simulated Alerts
                    {detailsDialog.alerts.length > 0 && (
                        <Button
                            startIcon={<Download size={16} />}
                            onClick={() => handleDownload(detailsDialog.runId)}
                        >
                            Export Excel
                        </Button>
                    )}
                </DialogTitle>
                <DialogContent dividers>
                    {detailsDialog.loading ? (
                        <div className="flex justify-center p-8"><CircularProgress /></div>
                    ) : detailsDialog.alerts.length === 0 ? (
                        <div className="text-center p-8 text-slate-500">No alerts generated in this run.</div>
                    ) : (
                        <TableContainer component={Paper} className="shadow-none border">
                            <Table size="small">
                                <TableHead className="bg-slate-50">
                                    <TableRow>
                                        <TableCell className="font-bold">Customer ID</TableCell>
                                        <TableCell className="font-bold">Scenario</TableCell>
                                        <TableCell className="font-bold">Risk Score</TableCell>
                                        <TableCell className="font-bold">Date</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {detailsDialog.alerts.map((alert) => (
                                        <TableRow key={alert.alert_id} hover>
                                            <TableCell className="font-mono text-sm">{alert.customer_id}</TableCell>
                                            <TableCell>{alert.scenario_name}</TableCell>
                                            <TableCell>
                                                <span className={`px-2 py-1 rounded text-xs font-bold ${alert.risk_score > 70 ? 'bg-red-100 text-red-700' :
                                                    alert.risk_score > 40 ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                                                    }`}>
                                                    {alert.risk_score}
                                                </span>
                                            </TableCell>
                                            <TableCell className="text-slate-500 text-sm">
                                                <span className="font-semibold text-slate-900">Date Triggered:</span>{' '}
                                                {formatDateIST(alert.alert_date)}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDetailsDialog(prev => ({ ...prev, open: false }))}>
                        Close
                    </Button>
                </DialogActions>
            </Dialog>
        </div>
    );
}
