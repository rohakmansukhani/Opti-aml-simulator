'use client';

import { ComparisonReport, AlertDiffItem } from '@/types/schema';
import { Card, CardContent } from '@mui/material';
import { CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react';

interface Props {
    report: ComparisonReport;
}

export default function DiffVisualization({ report }: Props) {
    const { granular_diff, risk_analysis } = report;

    // Group alerts by status
    const retained = granular_diff.filter(x => x.status === 'RETAINED');
    const excluded = granular_diff.filter(x => x.status === 'EXCLUDED');
    const newAlerts = granular_diff.filter(x => x.status === 'NEW_ALERT');

    return (
        <div className="space-y-8">
            {/* High Level Stats */}
            <div className="grid grid-cols-3 gap-6">
                <Card className="bg-emerald-50 border-emerald-100 shadow-none">
                    <CardContent className="flex items-center gap-4 p-6">
                        <div className="p-3 bg-white rounded-full text-emerald-600 shadow-sm"><CheckCircle size={24} /></div>
                        <div>
                            <div className="text-2xl font-bold text-slate-900">{retained.length}</div>
                            <div className="text-sm font-medium text-emerald-700">Valid Alerts Retained</div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-amber-50 border-amber-100 shadow-none">
                    <CardContent className="flex items-center gap-4 p-6">
                        <div className="p-3 bg-white rounded-full text-amber-600 shadow-sm"><XCircle size={24} /></div>
                        <div>
                            <div className="text-2xl font-bold text-slate-900">{excluded.length}</div>
                            <div className="text-sm font-medium text-amber-700">False Positives Dropped</div>
                        </div>
                    </CardContent>
                </Card>

                <Card className={`border shadow-none ${risk_analysis.risk_score > 0 ? 'bg-red-50 border-red-100' : 'bg-slate-50 border-slate-100'}`}>
                    <CardContent className="flex items-center gap-4 p-6">
                        <div className={`p-3 bg-white rounded-full shadow-sm ${risk_analysis.risk_score > 0 ? 'text-red-600' : 'text-slate-500'}`}>
                            <AlertTriangle size={24} />
                        </div>
                        <div>
                            <div className="text-2xl font-bold text-slate-900">{risk_analysis.risk_score}%</div>
                            <div className={`text-sm font-medium ${risk_analysis.risk_score > 0 ? 'text-red-700' : 'text-slate-600'}`}>Risk Gap Score</div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Detailed Lists */}
            <div className="grid grid-cols-2 gap-8">
                <div>
                    <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
                        <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2" />
                        Retained Alerts (Safe)
                    </h3>
                    <div className="max-h-96 overflow-y-auto space-y-3 pr-2">
                        {retained.map((alert, i) => (
                            <div key={i} className="p-4 bg-white border border-slate-200 rounded-lg shadow-sm text-sm">
                                <div className="font-semibold text-slate-900">{alert.customer_id}</div>
                                <div className="text-slate-500 flex justify-between mt-1">
                                    <span>{alert.alert_date}</span>
                                    {alert.amount && <span>${alert.amount.toLocaleString()}</span>}
                                </div>
                            </div>
                        ))}
                        {retained.length === 0 && <div className="text-slate-400 italic">No retained alerts</div>}
                    </div>
                </div>

                <div>
                    <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center">
                        <span className="w-2 h-2 bg-amber-500 rounded-full mr-2" />
                        Excluded Alerts (Refined)
                    </h3>
                    <div className="max-h-96 overflow-y-auto space-y-3 pr-2">
                        {excluded.map((alert, i) => (
                            <div key={i} className="p-4 bg-white border border-amber-200 rounded-lg shadow-sm bg-amber-50/10 text-sm opacity-75">
                                <div className="font-semibold text-slate-900">{alert.customer_id}</div>
                                <div className="text-slate-500 flex justify-between mt-1">
                                    <span>{alert.alert_date}</span>
                                    <span className="text-amber-600 font-medium">Excluded</span>
                                </div>
                            </div>
                        ))}
                        {excluded.length === 0 && <div className="text-slate-400 italic">No excluded alerts</div>}
                    </div>
                </div>
            </div>
        </div>
    );
}
