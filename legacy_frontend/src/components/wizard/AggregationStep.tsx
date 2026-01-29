'use client';

import { useBuilderStore } from '@/store/useBuilderStore';
import { Slider } from '@mui/material';
import { Calculator, Calendar, Users, Activity } from 'lucide-react';
import { AggregationConfig } from '@/types/schema';

export default function AggregationStep() {
    const { config, updateNestedConfig, schema } = useBuilderStore();

    // Default values if undefined, explicitly typed to avoid inference errors
    const defaultAgg: AggregationConfig = {
        group_by: ['customer_id'],
        method: 'sum',
        field: 'transaction_amount',
        time_window: { value: 30, unit: 'days', type: 'rolling' }
    };

    const agg = config.config_json?.aggregation || defaultAgg;

    const handleUpdate = (key: string, value: any) => {
        updateNestedConfig('aggregation', { ...agg, [key]: value });
    };

    const handleWindowUpdate = (val: number) => {
        updateNestedConfig('aggregation', {
            ...agg,
            time_window: {
                value: val,
                unit: agg.time_window?.unit || 'days',
                type: agg.time_window?.type || 'rolling'
            }
        });
    };

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center mb-10">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 mb-4 shadow-sm border border-indigo-100">
                    <Calculator size={32} />
                </div>
                <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Define Logic</h2>
                <p className="text-slate-500 mt-2 text-lg">Construct your rule using natural language.</p>
            </div>

            {/* Sentence Builder Card */}
            <div className="bg-white rounded-3xl p-8 shadow-xl shadow-slate-200/50 border border-slate-100">
                <div className="flex flex-wrap items-center gap-4 text-xl md:text-2xl font-medium text-slate-700 leading-relaxed">

                    <span>Calculate the</span>

                    {/* Method Dropdown */}
                    <div className="relative group">
                        <select
                            value={agg.method || 'sum'}
                            onChange={(e) => handleUpdate('method', e.target.value)}
                            className="appearance-none bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold py-2 pl-4 pr-10 rounded-xl cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all border-none"
                        >
                            <option value="sum">Total Sum</option>
                            <option value="count">Count</option>
                            <option value="avg">Average</option>
                            <option value="max">Maximum</option>
                            <option value="min">Minimum</option>
                        </select>
                        <Activity size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-blue-400 pointer-events-none" />
                    </div>

                    <span>of</span>

                    {/* Field Dropdown */}
                    <div className="relative group">
                        <select
                            value={agg.field || ''}
                            onChange={(e) => handleUpdate('field', e.target.value)}
                            className="appearance-none bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold py-2 pl-4 pr-10 rounded-xl cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all border-none"
                        >
                            <option value="" disabled>Select Metric...</option>
                            <optgroup label="Available Fields">
                                {schema?.transactions?.filter((col: any) => {
                                    // If method is 'count', allow all fields. Otherwise, restrict to numeric.
                                    if (agg.method === 'count') return true;
                                    return ['DECIMAL', 'Integer', 'Float', 'number'].some(t => col.type.toLowerCase().includes(t.toLowerCase()));
                                }).map((col: any) => (
                                    <option key={col.name} value={col.name}>{col.label || col.name}</option>
                                ))}
                            </optgroup>
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                            <span className="text-xs font-mono text-emerald-600/50">VAR</span>
                        </div>
                    </div>

                    <span>grouped by</span>

                    {/* Group By Dropdown - Fully Dynamic from Customer Schema */}
                    <div className="relative group">
                        <select
                            value={agg.group_by?.[0] || 'customer_id'}
                            onChange={(e) => handleUpdate('group_by', [e.target.value])}
                            className="appearance-none bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold py-2 pl-4 pr-10 rounded-xl cursor-pointer focus:outline-none focus:ring-2 focus:ring-amber-500 transition-all border-none"
                        >
                            <optgroup label="Customer Attributes">
                                {schema?.customers?.map((col: any) => (
                                    <option key={col.name} value={col.name}>{col.label || col.name}</option>
                                ))}
                            </optgroup>
                            {/* Fallback for customer_id if schema is missing */}
                            {!schema?.customers && <option value="customer_id">Customer</option>}
                        </select>
                        <Users size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-amber-400 pointer-events-none" />
                    </div>

                    <span>over the last</span>

                    {/* Window Size Value */}
                    <span className="font-bold text-slate-900 border-b-2 border-slate-300 px-1">
                        {agg.time_window?.value || 30}
                    </span>

                    <span>days.</span>
                </div>

                {/* Slider Control */}
                <div className="mt-12 bg-slate-50 rounded-2xl p-6">
                    <div className="flex items-center gap-3 mb-4 text-slate-500 font-medium text-sm uppercase tracking-wider">
                        <Calendar size={16} />
                        Time Window Adjustment
                    </div>
                    <Slider
                        value={agg.time_window?.value || 30}
                        onChange={(_, val) => handleWindowUpdate(val as number)}
                        min={1}
                        max={90}
                        valueLabelDisplay="auto"
                        classes={{
                            thumb: 'bg-indigo-600 hover:shadow-lg hover:shadow-indigo-200',
                            track: 'bg-indigo-500',
                            rail: 'bg-slate-200'
                        }}
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-2 font-mono">
                        <span>1 Day</span>
                        <span>90 Days</span>
                    </div>
                </div>
            </div>

            <div className="mt-6 text-center">
                <p className="text-sm text-slate-400 italic">
                    Output Alias: <code className="bg-slate-100 px-2 py-1 rounded text-slate-600 font-mono">
                        {agg.method}_{agg.field}
                    </code>
                </p>
            </div>
        </div>
    );
}
