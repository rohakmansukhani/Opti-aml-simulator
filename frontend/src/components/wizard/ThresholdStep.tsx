'use client';
import { useBuilderStore } from "@/store/useBuilderStore";
import { useState } from "react";
import {
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Button,
    IconButton,
    ListSubheader,
    Tooltip,
    Chip
} from "@mui/material";
import { Target, Plus, Trash2, Calculator, Info } from "lucide-react";
import { ThresholdConfig } from "@/types/schema";

export default function ThresholdStep() {
    const { config, updateNestedConfig, schema } = useBuilderStore();

    const threshold = config.config_json?.threshold || {
        type: "fixed",
        fixed_value: 0
    };

    const handleTypeChange = (type: string) => {
        const newType = type as ThresholdConfig['type'];
        let newThreshold: Partial<ThresholdConfig> = { type: newType };

        if (type === "fixed") {
            newThreshold.fixed_value = 0;
        } else if (type === "field_based") {
            newThreshold.field_based = {
                reference_field: "annual_income",
                calculation: "reference_field / 12 * 3"
            };
        } else if (type === "segment_based") {
            newThreshold.segment_based = {
                segment_field: "occupation",
                values: {
                    "Student": 2000,
                    "Salaried": 10000,
                    "Self-employed": 15000
                },
                default: 5000
            };
        }

        updateNestedConfig("threshold", newThreshold as ThresholdConfig);
    };

    const handleFieldBasedUpdate = (key: string, value: any) => {
        updateNestedConfig("threshold", {
            ...threshold,
            field_based: {
                reference_field: threshold.field_based?.reference_field || "",
                calculation: threshold.field_based?.calculation || "",
                [key]: value
            }
        } as ThresholdConfig);
    };

    const handleSegmentUpdate = (key: string, value: any) => {
        updateNestedConfig("threshold", {
            ...threshold,
            segment_based: {
                segment_field: threshold.segment_based?.segment_field || "",
                values: threshold.segment_based?.values || {},
                default: threshold.segment_based?.default || 0,
                [key]: value
            }
        } as ThresholdConfig);
    };

    const addSegmentValue = () => {
        const newValues = { ...(threshold.segment_based?.values || {}) };
        newValues["New Segment"] = 0;
        handleSegmentUpdate("values", newValues);
    };

    const removeSegmentValue = (key: string) => {
        const newValues = { ...(threshold.segment_based?.values || {}) };
        delete newValues[key];
        handleSegmentUpdate("values", newValues);
    };

    return (
        <div className="space-y-6">
            <div className="bg-white rounded-3xl p-8 shadow-xl shadow-slate-200/50 border border-slate-100 space-y-6">
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <label className="text-sm font-semibold text-slate-700">Threshold Type</label>
                        <Tooltip
                            title={
                                threshold.type === "fixed"
                                    ? "A single fixed amount applies to all transactions"
                                    : threshold.type === "field_based"
                                        ? "Threshold calculated based on customer data (e.g., 3x monthly income)"
                                        : "Different thresholds for different customer segments (e.g., Students vs Business owners)"
                            }
                            placement="right"
                        >
                            <Info size={16} className="text-blue-500 cursor-help" />
                        </Tooltip>
                    </div>
                    <FormControl fullWidth size="small">
                        <Select
                            value={threshold.type}
                            onChange={(e) => handleTypeChange(e.target.value)}
                            displayEmpty
                        >
                            <MenuItem value="fixed">Fixed Value</MenuItem>
                            <MenuItem value="field_based">Field-Based (Dynamic)</MenuItem>
                            <MenuItem value="segment_based">Segment-Based</MenuItem>
                        </Select>
                    </FormControl>
                </div>

                {/* Fixed Value */}
                {threshold.type === "fixed" && (
                    <TextField
                        fullWidth
                        type="number"
                        label="Threshold Amount"
                        value={threshold.fixed_value || 0}
                        onChange={(e) => updateNestedConfig("threshold", { ...threshold, fixed_value: Number(e.target.value) })}
                        size="small"
                        helperText="Alert triggers when transaction exceeds this amount"
                    />
                )}

                {/* Field-Based (Dynamic) */}
                {threshold.type === "field_based" && (
                    <div className="space-y-6 bg-amber-50 p-6 rounded-xl border border-amber-200">
                        <div className="flex items-center gap-2 text-amber-700 font-bold">
                            <Calculator size={20} />
                            <span>Dynamic Threshold Formula</span>
                        </div>

                        <FormControl fullWidth size="small">
                            <InputLabel>Reference Field</InputLabel>
                            <Select
                                value={threshold.field_based?.reference_field || ""}
                                label="Reference Field"
                                onChange={(e) => handleFieldBasedUpdate("reference_field", e.target.value)}
                            >
                                <ListSubheader>Customer Fields</ListSubheader>
                                {schema?.customers?.map((col: any) => (
                                    <MenuItem key={col.name} value={col.name}>
                                        {col.label} <span className="text-xs text-slate-400 ml-2">({col.name})</span>
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <TextField
                            fullWidth
                            label="Calculation Formula"
                            value={threshold.field_based?.calculation || ""}
                            onChange={(e) => handleFieldBasedUpdate("calculation", e.target.value)}
                            placeholder="reference_field / 12 * 3"
                            size="small"
                            helperText="Use 'reference_field' as the variable. Example: reference_field / 12 * 3"
                        />

                        <div className="bg-white p-4 rounded-lg border border-amber-300">
                            <div className="text-xs font-bold text-amber-800 uppercase mb-2">Example</div>
                            <div className="text-sm text-slate-700">
                                If <code className="bg-slate-100 px-1 rounded">{threshold.field_based?.reference_field || 'field'}</code> = 8000,
                                then threshold = <code className="bg-emerald-100 px-1 rounded">
                                    {(threshold.field_based?.calculation || "").replace("reference_field", "8000")}
                                </code>
                            </div>
                        </div>
                    </div>
                )}

                {/* Segment-Based */}
                {threshold.type === "segment_based" && (
                    <div className="space-y-6 bg-purple-50 p-6 rounded-xl border border-purple-200">
                        <div className="flex items-center gap-2 text-purple-700 font-bold">
                            <Target size={20} />
                            <span>Segment-Specific Thresholds</span>
                        </div>

                        <FormControl fullWidth size="small">
                            <InputLabel>Segment Field</InputLabel>
                            <Select
                                value={threshold.segment_based?.segment_field || ""}
                                label="Segment Field"
                                onChange={(e) => handleSegmentUpdate("segment_field", e.target.value)}
                            >
                                <ListSubheader>Customer Fields</ListSubheader>
                                {schema?.customers?.map((col: any) => (
                                    <MenuItem key={col.name} value={col.name}>
                                        {col.label} <span className="text-xs text-slate-400 ml-2">({col.name})</span>
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <div className="space-y-3">
                            <div className="text-sm font-semibold text-slate-700">Segment Values</div>
                            {Object.entries(threshold.segment_based?.values || {}).map(([key, value]) => (
                                <div key={key} className="flex items-center gap-3">
                                    <TextField
                                        label="Segment"
                                        value={key}
                                        size="small"
                                        className="flex-1"
                                        disabled
                                    />
                                    <TextField
                                        label="Threshold"
                                        type="number"
                                        value={value}
                                        onChange={(e) => {
                                            const newValues = { ...threshold.segment_based?.values };
                                            newValues[key] = Number(e.target.value);
                                            handleSegmentUpdate("values", newValues);
                                        }}
                                        size="small"
                                        className="flex-1"
                                    />
                                    <IconButton
                                        onClick={() => removeSegmentValue(key)}
                                        size="small"
                                        className="text-red-600"
                                    >
                                        <Trash2 size={18} />
                                    </IconButton>
                                </div>
                            ))}
                            <Button
                                startIcon={<Plus size={18} />}
                                onClick={addSegmentValue}
                                variant="outlined"
                                size="small"
                            >
                                Add Segment
                            </Button>
                        </div>

                        <TextField
                            fullWidth
                            type="number"
                            label="Default Threshold"
                            value={threshold.segment_based?.default || 0}
                            onChange={(e) => handleSegmentUpdate("default", Number(e.target.value))}
                            size="small"
                            helperText="Used for segments not explicitly defined above"
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
