'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    IconButton,
    Chip,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    CircularProgress,
    Alert
} from '@mui/material';
import { Edit, Trash2, Search, CheckCircle2, Info, Calendar } from 'lucide-react';
import { formatDateIST } from '@/lib/date-utils';

interface Scenario {
    scenario_id: string;
    scenario_name: string;
    enabled: boolean;
    config_json: any;
    updated_at: string;
}

export default function RulesPage() {
    const router = useRouter();
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');

    // Dialog States
    const [deleteDialog, setDeleteDialog] = useState<{ open: boolean; scenario: Scenario | null }>({
        open: false,
        scenario: null
    });

    useEffect(() => {
        fetchScenarios();
    }, []);

    const fetchScenarios = async () => {
        try {
            setLoading(true);
            const res = await api.get('/api/rules/scenarios');
            setScenarios(res.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load scenarios');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteDialog.scenario) return;

        try {
            await api.delete(`/api/rules/scenarios/${deleteDialog.scenario.scenario_id}`);
            setDeleteDialog({ open: false, scenario: null });
            fetchScenarios(); // Refresh list
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete scenario');
        }
    };

    const handleEdit = (scenario: Scenario) => {
        // Store scenario data in localStorage for builder to load
        localStorage.setItem('editScenario', JSON.stringify({
            scenario_id: scenario.scenario_id,
            scenario_name: scenario.scenario_name,
            priority: 'High',
            is_active: scenario.enabled,
            config_json: scenario.config_json
        }));

        // Navigate to builder
        router.push('/dashboard/builder');
    };

    const filteredScenarios = scenarios.filter(s =>
        s.scenario_name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen">
                <CircularProgress />
            </div>
        );
    }

    return (
        <div className="p-8 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Detection Rules</h1>
                    <p className="text-slate-500 mt-1">Manage your saved scenario configurations</p>
                </div>
                <div className="space-x-4">
                    <Button
                        variant="contained"
                        onClick={() => router.push('/dashboard/builder')}
                        className="bg-blue-600 hover:bg-blue-700"
                    >
                        Create New Rule
                    </Button>
                </div>
            </div>

            {/* Search */}
            <TextField
                fullWidth
                size="small"
                placeholder="Search scenarios..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                    startAdornment: <Search size={20} className="mr-2 text-slate-400" />
                }}
            />

            {/* Error Alert */}
            {error && (
                <Alert severity="error" onClose={() => setError('')}>
                    {error}
                </Alert>
            )}

            {/* Table */}
            <TableContainer component={Paper} className="shadow-lg">
                <Table>
                    <TableHead className="bg-slate-50">
                        <TableRow>
                            <TableCell className="font-bold">Scenario Name</TableCell>
                            <TableCell className="font-bold">Status</TableCell>
                            <TableCell className="font-bold">Last Updated</TableCell>
                            <TableCell className="font-bold text-right">Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {filteredScenarios.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={4} className="text-center text-slate-500 py-8">
                                    No scenarios found. Create your first detection rule!
                                </TableCell>
                            </TableRow>
                        ) : (
                            filteredScenarios.map((scenario) => (
                                <TableRow key={scenario.scenario_id} hover>
                                    <TableCell className="font-medium">{scenario.scenario_name}</TableCell>
                                    <TableCell>
                                        <Chip
                                            label={scenario.enabled ? 'Active' : 'Inactive'}
                                            color={scenario.enabled ? 'success' : 'default'}
                                            size="small"
                                        />
                                    </TableCell>
                                    <TableCell className="text-slate-600 flex items-center">
                                        <Calendar size={12} className="mr-1" />
                                        {formatDateIST(scenario.updated_at)}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <IconButton
                                            size="small"
                                            onClick={() => handleEdit(scenario)}
                                            title="Edit"
                                        >
                                            <Edit size={18} />
                                        </IconButton>
                                        <IconButton
                                            size="small"
                                            onClick={() => setDeleteDialog({ open: true, scenario })}
                                            title="Delete"
                                            className="text-red-600"
                                        >
                                            <Trash2 size={18} />
                                        </IconButton>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Delete Confirmation Dialog */}
            <Dialog open={deleteDialog.open} onClose={() => setDeleteDialog({ open: false, scenario: null })}>
                <DialogTitle>Delete Scenario</DialogTitle>
                <DialogContent>
                    Are you sure you want to delete "{deleteDialog.scenario?.scenario_name}"? This action cannot be undone.
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteDialog({ open: false, scenario: null })}>Cancel</Button>
                    <Button onClick={handleDelete} color="error" variant="contained">
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </div>
    );
}
