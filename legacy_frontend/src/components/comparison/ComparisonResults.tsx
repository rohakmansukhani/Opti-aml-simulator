/**
 * ComparisonResults Component
 * 
 * Displays comparison metrics and customer-level differences
 */

import { TrendingDown, Users, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { motion } from 'framer-motion';

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
}

interface ComparisonResultsProps {
    data: ComparisonData;
}

export function ComparisonResults({ data }: ComparisonResultsProps) {
    const { summary, customer_level_diff } = data;

    return (
        <div className="space-y-6">
            {/* Summary Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <MetricCard
                    title="Baseline Alerts"
                    value={summary.baseline_alerts}
                    icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
                    color="amber"
                />
                <MetricCard
                    title="Refined Alerts"
                    value={summary.refined_alerts}
                    icon={<CheckCircle className="w-5 h-5 text-green-600" />}
                    color="green"
                />
                <MetricCard
                    title="Net Reduction"
                    value={Math.abs(summary.net_change)}
                    icon={<TrendingDown className="w-5 h-5 text-blue-600" />}
                    color="blue"
                    suffix={summary.net_change > 0 ? "↓" : "↑"}
                />
                <MetricCard
                    title="Reduction %"
                    value={`${summary.percent_reduction.toFixed(1)}%`}
                    icon={<TrendingDown className="w-5 h-5 text-purple-600" />}
                    color="purple"
                />
            </div>

            {/* Customer-Level Diff Table */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200">
                    <div className="flex items-center gap-2">
                        <Users className="w-5 h-5 text-slate-600" />
                        <h3 className="text-lg font-semibold">Customer-Level Changes</h3>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Customer
                                </th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Baseline
                                </th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Refined
                                </th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    Change
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                            {customer_level_diff.map((customer, index) => (
                                <motion.tr
                                    key={customer.customer_id}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="hover:bg-slate-50"
                                >
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="text-sm font-medium text-slate-900">
                                            {customer.customer_name}
                                        </div>
                                        <div className="text-xs text-slate-500">
                                            {customer.customer_id}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        <span className="text-sm text-slate-900">
                                            {customer.baseline_alerts}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        <span className="text-sm text-slate-900">
                                            {customer.refined_alerts}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        <ChangeIndicator value={customer.net_change} />
                                    </td>
                                </motion.tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

function MetricCard({ title, value, icon, color, suffix }: any) {
    const colorClasses: Record<string, string> = {
        amber: 'bg-amber-50 border-amber-200',
        green: 'bg-green-50 border-green-200',
        blue: 'bg-blue-50 border-blue-200',
        purple: 'bg-purple-50 border-purple-200'
    };

    return (
        <div className={`${colorClasses[color] || 'bg-slate-50 border-slate-200'} border rounded-lg p-4`}>
            <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-600">{title}</span>
                {icon}
            </div>
            <div className="text-2xl font-bold text-slate-900">
                {value} {suffix && <span className="text-lg">{suffix}</span>}
            </div>
        </div>
    );
}

function ChangeIndicator({ value }: { value: number }) {
    if (value === 0) {
        return <span className="text-sm text-slate-500">No change</span>;
    }

    const isReduction = value < 0;
    return (
        <div className={`inline-flex items-center gap-1 px-2 py-1 rounded ${isReduction ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>
            {isReduction ? (
                <CheckCircle className="w-4 h-4" />
            ) : (
                <XCircle className="w-4 h-4" />
            )}
            <span className="text-sm font-medium">
                {Math.abs(value)} {isReduction ? '↓' : '↑'}
            </span>
        </div>
    );
}
