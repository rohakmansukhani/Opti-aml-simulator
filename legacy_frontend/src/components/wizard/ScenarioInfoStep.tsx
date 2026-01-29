'use client';

import { useBuilderStore } from '@/store/useBuilderStore';
import { TextField, MenuItem, FormControl, InputLabel, Select, Switch, FormControlLabel } from '@mui/material';
import { FileText, Tag, Activity, AlertCircle } from 'lucide-react';

export default function ScenarioInfoStep() {
    const { config, updateConfig } = useBuilderStore();

    return (
        <div className="max-w-3xl mx-auto">
            <div className="text-center mb-10">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 mb-4 shadow-sm border border-blue-100">
                    <FileText size={32} />
                </div>
                <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Scenario Basics</h2>
                <p className="text-slate-500 mt-2 text-lg">Give your detection scenario a clear identity.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Left Col */}
                <div className="space-y-6">
                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 transition-colors hover:border-blue-200 group">
                        <div className="flex items-center gap-3 mb-4 text-slate-700 font-semibold">
                            <Tag size={18} className="text-blue-500" />
                            <span>Identity</span>
                        </div>
                        <TextField
                            fullWidth
                            label="Scenario Name"
                            placeholder="e.g. Rapid Fund Movement"
                            variant="outlined"
                            className="bg-white"
                            value={config.scenario_name}
                            onChange={(e) => updateConfig({ scenario_name: e.target.value })}
                        />
                    </div>

                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 transition-colors hover:border-blue-200">
                        <div className="flex items-center gap-3 mb-4 text-slate-700 font-semibold">
                            <Activity size={18} className="text-emerald-500" />
                            <span>Status</span>
                        </div>
                        <div className="flex items-center justify-between bg-white p-3 rounded-xl border border-slate-200">
                            <span className="text-sm font-medium text-slate-600 pl-2">Enable Detection</span>
                            <Switch
                                checked={config.is_active}
                                onChange={(e) => updateConfig({ is_active: e.target.checked })}
                                className="mr-2"
                            />
                        </div>
                    </div>
                </div>

                {/* Right Col */}
                <div className="space-y-6">
                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 transition-colors hover:border-blue-200 h-full">
                        <div className="flex items-center gap-3 mb-4 text-slate-700 font-semibold">
                            <AlertCircle size={18} className="text-amber-500" />
                            <span>Configuration</span>
                        </div>

                        <div className="space-y-6">
                            <FormControl fullWidth>
                                <InputLabel id="priority-label">Priority Level</InputLabel>
                                <Select
                                    labelId="priority-label"
                                    value={config.priority || 'Medium'}
                                    label="Priority Level"
                                    className="bg-white"
                                    onChange={(e) => updateConfig({ priority: e.target.value as any })}
                                >
                                    <MenuItem value="Low" className="text-slate-600">Low</MenuItem>
                                    <MenuItem value="Medium" className="text-amber-600 font-medium">Medium</MenuItem>
                                    <MenuItem value="High" className="text-red-600 font-bold">High</MenuItem>
                                </Select>
                            </FormControl>

                            <div className="mt-8">
                                <TextField
                                    fullWidth
                                    multiline
                                    rows={4}
                                    label="Description"
                                    placeholder="Explain the logic..."
                                    className="bg-white"
                                    InputProps={{
                                        className: "bg-white"
                                    }}
                                    sx={{
                                        '& .MuiInputLabel-root': {
                                            backgroundColor: 'white',
                                            padding: '0 4px'
                                        }
                                    }}
                                    value={config.description || ''}
                                    onChange={(e) => updateConfig({ description: e.target.value })}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
