/**
 * SimulationDialog Component
 * 
 * Modal dialog for running simulations with progress tracking
 */

import { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, CircularProgress, LinearProgress } from '@mui/material';
import { Play, CheckCircle, XCircle } from 'lucide-react';
import { useSimulationRunner } from '@/hooks/useSimulationRunner';

interface SimulationDialogProps {
    open: boolean;
    onClose: () => void;
    scenarioId: string;
    scenarioName: string;
    onComplete: (runId: string) => void;
}

export function SimulationDialog({ open, onClose, scenarioId, scenarioName, onComplete }: SimulationDialogProps) {
    const { runSimulation, progress, isRunning, error } = useSimulationRunner();
    const [dateRange, setDateRange] = useState({ start: '', end: '' });

    const handleRun = async () => {
        const runId = await runSimulation(scenarioId, dateRange.start && dateRange.end ? dateRange : undefined);
        if (runId && progress?.status === 'completed') {
            onComplete(runId);
            onClose();
        }
    };

    return (
        <Dialog open={open} onClose={isRunning ? undefined : onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                <div className="flex items-center gap-2">
                    <Play className="w-5 h-5 text-blue-600" />
                    <span>Run Simulation</span>
                </div>
            </DialogTitle>

            <DialogContent>
                <div className="space-y-4">
                    <div>
                        <p className="text-sm text-slate-600 mb-2">Scenario:</p>
                        <p className="font-medium">{scenarioName}</p>
                    </div>

                    {/* Date Range (Optional) */}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">
                                Start Date
                            </label>
                            <input
                                type="date"
                                value={dateRange.start}
                                onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                                disabled={isRunning}
                                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">
                                End Date
                            </label>
                            <input
                                type="date"
                                value={dateRange.end}
                                onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                                disabled={isRunning}
                                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>

                    {/* Progress */}
                    {isRunning && progress && (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-slate-600">Progress</span>
                                <span className="font-medium">{progress.progress_percentage}%</span>
                            </div>
                            <LinearProgress variant="determinate" value={progress.progress_percentage} />
                            <p className="text-xs text-slate-500">
                                Status: {progress.status}
                            </p>
                        </div>
                    )}

                    {/* Success */}
                    {progress?.status === 'completed' && (
                        <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                            <CheckCircle className="w-5 h-5 text-green-600" />
                            <div>
                                <p className="text-sm font-medium text-green-900">Simulation Complete</p>
                                <p className="text-xs text-green-700">
                                    Generated {progress.total_alerts} alerts
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                            <XCircle className="w-5 h-5 text-red-600" />
                            <div>
                                <p className="text-sm font-medium text-red-900">Simulation Failed</p>
                                <p className="text-xs text-red-700">{error}</p>
                            </div>
                        </div>
                    )}
                </div>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} disabled={isRunning}>
                    Cancel
                </Button>
                <Button
                    onClick={handleRun}
                    variant="contained"
                    disabled={isRunning || !scenarioId}
                    startIcon={isRunning ? <CircularProgress size={16} /> : <Play className="w-4 h-4" />}
                >
                    {isRunning ? 'Running...' : 'Run Simulation'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
