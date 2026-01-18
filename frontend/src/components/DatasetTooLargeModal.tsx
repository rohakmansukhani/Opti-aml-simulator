'use client';

import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import { AlertTriangle, Database, TrendingUp, Shield, Clock } from 'lucide-react';

interface DatasetTooLargeModalProps {
    open: boolean;
    onClose: () => void;
    recordCount: number;
    maxAllowed: number;
    onConnectDatabase: () => void;
}

export function DatasetTooLargeModal({
    open,
    onClose,
    recordCount,
    maxAllowed,
    onConnectDatabase
}: DatasetTooLargeModalProps) {
    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-amber-50 rounded-full flex items-center justify-center">
                        <AlertTriangle className="text-amber-600" size={24} />
                    </div>
                    <span className="text-xl font-semibold">Dataset Too Large</span>
                </div>
            </DialogTitle>

            <DialogContent>
                <div className="space-y-4">
                    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
                        <p className="text-sm text-slate-700">
                            Your file contains <span className="font-bold text-slate-900">{recordCount.toLocaleString()}</span> records,
                            which exceeds our limit of <span className="font-bold text-slate-900">{maxAllowed.toLocaleString()}</span> for temporary uploads.
                        </p>
                    </div>

                    <div className="space-y-3">
                        <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                            <Database size={18} className="text-blue-600" />
                            Connect Your Own Database
                        </h3>
                        <p className="text-sm text-slate-600">
                            For large datasets, we recommend connecting your own PostgreSQL or MySQL database:
                        </p>

                        <div className="grid gap-2 mt-3">
                            <div className="flex items-start gap-2 text-sm">
                                <TrendingUp size={16} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                                <span className="text-slate-700"><strong>Better Performance</strong> - Optimized for large-scale data</span>
                            </div>
                            <div className="flex items-start gap-2 text-sm">
                                <Shield size={16} className="text-blue-600 mt-0.5 flex-shrink-0" />
                                <span className="text-slate-700"><strong>No Size Limits</strong> - Process millions of records</span>
                            </div>
                            <div className="flex items-start gap-2 text-sm">
                                <Clock size={16} className="text-purple-600 mt-0.5 flex-shrink-0" />
                                <span className="text-slate-700"><strong>Persistent Data</strong> - No 48-hour expiry</span>
                            </div>
                        </div>
                    </div>
                </div>
            </DialogContent>

            <DialogActions className="p-4">
                <Button onClick={onClose} variant="outlined" color="inherit">
                    Cancel
                </Button>
                <Button
                    onClick={onConnectDatabase}
                    variant="contained"
                    startIcon={<Database size={16} />}
                    className="bg-blue-600 hover:bg-blue-700"
                >
                    Connect Database
                </Button>
            </DialogActions>
        </Dialog>
    );
}
