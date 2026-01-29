
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Select, MenuItem, FormControl, InputLabel } from "@mui/material";
import { useState, useEffect } from "react";
import { AlertTriangle, ArrowRight } from "lucide-react";

interface Mapping {
    original_field: string
    suggestion: string | null
    confidence: string
}

interface MappingModalProps {
    isOpen: boolean
    missingFields: Mapping[]
    availableColumns: string[]
    onConfirm: (mappings: Record<string, string>) => void
    onCancel: () => void
}

export function MappingModal({ isOpen, missingFields, availableColumns, onConfirm, onCancel }: MappingModalProps) {
    const [mappings, setMappings] = useState<Record<string, string>>({})

    // Auto-populate with suggestions on open
    useEffect(() => {
        if (isOpen && missingFields.length > 0) {
            const initial: Record<string, string> = {}
            missingFields.forEach(f => {
                if (f.suggestion) initial[f.original_field] = f.suggestion
            })
            setMappings(initial)
        }
    }, [isOpen, missingFields])

    const handleConfirm = () => {
        onConfirm(mappings)
    }

    const isComplete = missingFields.every(f => !!mappings[f.original_field])

    return (
        <Dialog open={isOpen} onClose={() => onCancel()} maxWidth="md" fullWidth PaperProps={{ sx: { borderRadius: 4 } }}>
            <DialogTitle className="flex items-center gap-2 text-amber-700 bg-amber-50 border-b border-amber-100">
                <AlertTriangle className="text-amber-600" />
                <span className="font-bold">Schema Mismatch Detected</span>
            </DialogTitle>

            <DialogContent className="pt-6">
                <p className="text-slate-600 mb-6 mt-4">
                    This scenario references fields that don't exist in the current database table.
                    Please map them to the correct columns below.
                </p>

                <div className="space-y-4">
                    <div className="grid grid-cols-[1fr_auto_1fr] gap-4 font-bold text-xs uppercase tracking-wider text-slate-400 border-b pb-2">
                        <div>Required Scenario Field</div>
                        <div></div>
                        <div>Available Database Column</div>
                    </div>

                    {missingFields.map((field) => (
                        <div key={field.original_field} className="grid grid-cols-[1fr_auto_1fr] gap-4 items-center">
                            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm font-mono text-slate-700 font-semibold">
                                {field.original_field}
                            </div>

                            <ArrowRight size={16} className="text-slate-300" />

                            <FormControl fullWidth size="small" error={!mappings[field.original_field]}>
                                <InputLabel>Select Column</InputLabel>
                                <Select
                                    value={mappings[field.original_field] || ''}
                                    label="Select Column"
                                    onChange={(e) => setMappings(m => ({ ...m, [field.original_field]: e.target.value }))}
                                >
                                    {availableColumns.map(col => (
                                        <MenuItem key={col} value={col}>
                                            {col}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </div>
                    ))}
                </div>
            </DialogContent>

            <DialogActions className="p-6 border-t border-slate-100 bg-slate-50/50">
                <Button onClick={onCancel} variant="outlined" color="inherit" className="border-slate-300 text-slate-600 hover:bg-slate-100">
                    Cancel
                </Button>
                <Button
                    onClick={handleConfirm}
                    disabled={!isComplete}
                    variant="contained"
                    className={`bg-blue-600 hover:bg-blue-700 shadow-lg ${!isComplete ? 'opacity-50' : ''}`}
                >
                    Apply Mappings & Run
                </Button>
            </DialogActions>
        </Dialog>
    )
}
