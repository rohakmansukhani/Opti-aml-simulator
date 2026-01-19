import { useState, useCallback } from 'react';
import { useBuilderStore } from '@/store/useBuilderStore';
import { Button, IconButton, TextField, MenuItem, Select, FormControl, InputLabel, ListSubheader, Alert, CircularProgress, Autocomplete, Chip } from '@mui/material';
import { Plus, Trash2, CheckCircle, AlertTriangle, Play } from 'lucide-react';
import { FilterConfig } from '@/types/schema';
import { api } from '@/lib/api';
// import debounce from 'lodash/debounce'; // Removed to avoid dependency issues

export default function FilterConfigStep() {
    const { config, updateNestedConfig, schema } = useBuilderStore();
    const filters = config.config_json?.filters || [];

    const [validating, setValidating] = useState(false);
    const [validationResult, setValidationResult] = useState<{
        match_count: number;
        match_count_customers?: number;
        total_records: number;
        status: string;
    } | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Autocomplete State
    const [optionsMap, setOptionsMap] = useState<Record<number, string[]>>({});

    // Debounce Ref
    const debounceRef = useState<Record<number, NodeJS.Timeout>>({})[0];

    const fetchOptions = (field: string, search: string, index: number) => {
        if (!field) return;

        // Clear existing timeout for this index
        if (debounceRef[index]) clearTimeout(debounceRef[index]);

        // Set new timeout
        debounceRef[index] = setTimeout(async () => {
            try {
                const { data } = await api.get('/api/data/values', {
                    params: { field, search }
                });
                console.log(`[Autocomplete] Fetched ${data.values?.length} values for index ${index}:`, data.values);
                setOptionsMap(prev => ({ ...prev, [index]: data.values || [] }));
            } catch (e) {
                console.error("Failed to fetch values", e);
            }
        }, 300);
    };

    const addFilter = () => {
        const newFilter: FilterConfig = { field: '', operator: '==', value: '' };
        updateNestedConfig('filters', [...filters, newFilter]);
        setValidationResult(null); // Reset validation on change
    };

    const removeFilter = (index: number) => {
        const newFilters = filters.filter((_, i) => i !== index);
        updateNestedConfig('filters', newFilters);
        setValidationResult(null);
    };

    const updateFilter = (index: number, field: keyof FilterConfig, value: any) => {
        const newFilters = [...filters];
        newFilters[index] = { ...newFilters[index], [field]: value };
        updateNestedConfig('filters', newFilters);
        setValidationResult(null);
    };

    const handleValidate = async () => {
        setValidating(true);
        setError(null);
        setValidationResult(null);
        try {
            const { data } = await api.post('/api/validation/filters', filters);
            setValidationResult(data);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Validation failed");
        } finally {
            setValidating(false);
        }
    };

    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-slate-900">Define Scope Filters</h2>
                <p className="text-slate-500 mt-1">Select fields from your data to narrow down the analysis.</p>
            </div>

            <div className="space-y-4">
                {filters.map((filter, idx) => (
                    <div key={idx} className="flex gap-4 items-center bg-slate-50 p-4 rounded-xl border border-slate-200">

                        {/* Field Selector (Schema Aware) */}
                        <FormControl size="small" className="flex-1">
                            <InputLabel>Field</InputLabel>
                            <Select
                                value={filter.field}
                                label="Field"
                                onChange={(e) => updateFilter(idx, 'field', e.target.value)}
                            >
                                <ListSubheader>Transactions</ListSubheader>
                                {schema?.transactions?.map((col: any) => (
                                    <MenuItem key={`tx_${col.name}`} value={col.name}>
                                        {col.label} <span className="text-xs text-slate-400 ml-2">({col.name})</span>
                                    </MenuItem>
                                ))}
                                <ListSubheader>Customers</ListSubheader>
                                {schema?.customers?.map((col: any) => (
                                    <MenuItem key={`cust_${col.name}`} value={col.name}>
                                        {col.label} <span className="text-xs text-slate-400 ml-2">({col.name})</span>
                                    </MenuItem>
                                ))}
                                {!schema && <MenuItem value={filter.field || ''}>{filter.field || 'Loading Schema...'}</MenuItem>}
                            </Select>
                        </FormControl>

                        <FormControl size="small" className="w-40">
                            <InputLabel>Operator</InputLabel>
                            <Select
                                value={filter.operator}
                                label="Operator"
                                onChange={(e) => updateFilter(idx, 'operator', e.target.value)}
                            >
                                <MenuItem value="==">Equals (==)</MenuItem>
                                <MenuItem value="!=">Not Equals (!=)</MenuItem>
                                <MenuItem value=">">Greater ({'>'})</MenuItem>
                                <MenuItem value="<">Less ({'<'})</MenuItem>
                                <MenuItem value="in">In List</MenuItem>
                            </Select>
                        </FormControl>

                        {/* Value Input (Context Aware) */}
                        {(() => {
                            // Determine field type from schema (STRICT)
                            const allFields = [...(schema?.transactions || []), ...(schema?.customers || [])];
                            const selectedField = allFields.find(f => f.name === filter.field);
                            const type = selectedField?.type || 'string';

                            let inputType = 'text';
                            let inputProps = {};

                            if (type === 'date') {
                                inputType = 'date';
                                inputProps = { shrink: true };
                            } else if (type === 'datetime') {
                                inputType = 'datetime-local';
                                inputProps = { shrink: true };
                            } else if (type === 'integer') {
                                inputType = 'number';
                            } else if (type === 'float') {
                                inputType = 'number';
                            }

                            // Helper to cast value safely for Autocomplete
                            const isMultiple = filter.operator === 'in';

                            // Safe value handling for single vs multiple
                            let safeValue: any = filter.value || '';
                            if (isMultiple) {
                                if (Array.isArray(filter.value)) {
                                    safeValue = filter.value;
                                } else if (typeof filter.value === 'string' && filter.value) {
                                    // Try to parse existing CSV string if switching modes
                                    safeValue = filter.value.split(',').map((s: string) => s.trim());
                                } else {
                                    safeValue = [];
                                }
                            } else {
                                safeValue = String(filter.value || '');
                            }

                            return (
                                <Autocomplete
                                    freeSolo
                                    size="small"
                                    multiple={isMultiple}
                                    options={optionsMap[idx] || []}
                                    filterOptions={(x) => x}
                                    noOptionsText="No matching values found"
                                    className="flex-1"
                                    value={safeValue}
                                    onInputChange={(_, newValue) => {
                                        // For multiple, input change is just typing (searching)
                                        // For single, it's the value itself

                                        // Optimization: Don't fetch for empty/short inputs
                                        if (newValue && newValue.length >= 1) {
                                            fetchOptions(filter.field, newValue, idx);
                                        }

                                        // For single mode, we update value on type
                                        if (!isMultiple && newValue !== undefined) {
                                            updateFilter(idx, 'value', newValue);
                                        }
                                    }}
                                    onChange={(_, newValue) => {
                                        // newValue is Array if multiple, String/null if single
                                        updateFilter(idx, 'value', newValue);
                                    }}
                                    renderTags={(value: readonly string[], getTagProps) =>
                                        value.map((option: string, index: number) => (
                                            <Chip
                                                label={option}
                                                size="small"
                                                {...getTagProps({ index })}
                                                key={option}
                                            />
                                        ))
                                    }
                                    renderInput={(params) => (
                                        <TextField
                                            {...params}
                                            label={`Value ${optionsMap[idx]?.length > 0 ? `(${optionsMap[idx].length} found)` : ''}`}
                                            placeholder={inputType === 'text' ? (isMultiple ? "Select multiple..." : "Type to search...") : ""}
                                            InputLabelProps={inputProps}
                                        />
                                    )}
                                />
                            );
                        })()}

                        <IconButton onClick={() => removeFilter(idx)} color="error">
                            <Trash2 size={20} />
                        </IconButton>
                    </div>
                ))}

                {filters.length === 0 && (
                    <div className="text-center p-8 border-2 border-dashed border-slate-200 rounded-xl text-slate-400 bg-slate-50/50">
                        No filters defined. All transactions will be processed.
                    </div>
                )}
            </div>

            {/* Validation Result UI */}
            {error && (
                <Alert severity="error" icon={<AlertTriangle />}>
                    Validation Error: {error}
                </Alert>
            )}

            {validationResult && (
                <Alert
                    severity={validationResult.match_count > 0 ? "success" : "warning"}
                    icon={validationResult.match_count > 0 ? <CheckCircle /> : <AlertTriangle />}
                    className="border border-opacity-20"
                >
                    <div className="font-semibold">
                        {validationResult.match_count} transactions found
                    </div>
                    <div className="text-xs opacity-90">
                        {validationResult.match_count_customers !== undefined && (
                            <span className="font-medium">from {validationResult.match_count_customers} distinct customers </span>
                        )}
                        (out of {validationResult.total_records} total transactions)
                    </div>
                </Alert>
            )}

            <div className="flex gap-4">
                <Button
                    variant="outlined"
                    startIcon={<Plus size={18} />}
                    onClick={addFilter}
                    className="flex-1 h-12 border-dashed border-2 hover:bg-blue-50 hover:border-blue-200 transition-colors"
                >
                    Add Filter Rule
                </Button>

                <Button
                    variant="contained"
                    color="secondary"
                    onClick={handleValidate}
                    disabled={validating || filters.length === 0}
                    startIcon={validating ? <CircularProgress size={18} color="inherit" /> : <Play size={18} />}
                    className="h-12 w-48 bg-slate-800 hover:bg-slate-900"
                >
                    {validating ? 'Checking...' : 'Test Filters'}
                </Button>
            </div>
        </div>
    );
}
