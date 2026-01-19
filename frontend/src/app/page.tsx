'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Logo } from '@/components/Logo';
import { useSessionStore } from '@/store/useSessionStore';
import { useRouter } from 'next/navigation';
import { UploadCloud, Database, ArrowRight, Loader2, CheckCircle2, Mail, AlertTriangle } from 'lucide-react';
import { supabase } from '@/lib/supabase';
import { formatDateIST, formatIST } from '@/lib/date-utils';
import { DatasetTooLargeModal } from '@/components/DatasetTooLargeModal';
import { TTLCountdown } from '@/components/TTLCountdown';

// --- AUTH COMPONENT ---
function AuthScreen({ onSuccess }: { onSuccess: () => void }) {
    const [email, setEmail] = useState('');

    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const [error, setError] = useState('');
    const setAuth = useSessionStore((s) => s.setAuth);

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            // Magic Link (Passwordless)
            const { error } = await supabase.auth.signInWithOtp({
                email,
                options: {
                    emailRedirectTo: typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : undefined,
                }
            });

            if (error) throw error;
            setSent(true);
        } catch (err: any) {
            setError(err.message || 'Authentication failed');
            setSent(false);
        } finally {
            setLoading(false);
        }
    };

    if (sent) {
        return (
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md border border-slate-100 text-center"
            >
                <div className="mx-auto w-16 h-16 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mb-6">
                    <Mail size={32} />
                </div>
                <h2 className="text-2xl font-bold text-slate-900 mb-2">Check your email</h2>
                <p className="text-slate-500 mb-6">
                    We sent a secure login link to <br /> <span className="font-semibold text-slate-900">{email}</span>
                </p>
                <button
                    onClick={() => setSent(false)}
                    className="text-sm text-blue-600 font-medium hover:underline"
                >
                    Use a different email
                </button>
            </motion.div>
        );
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md border border-slate-100"
        >
            <div className="text-center mb-8">
                <div className="inline-flex justify-center items-center w-12 h-12 rounded-full bg-blue-50 text-blue-600 mb-4">
                    <Mail size={20} />
                </div>
                <h2 className="text-2xl font-bold text-slate-900">Welcome to SecureCore</h2>
                <p className="text-slate-500 text-sm mt-1">Sign in to access your sandbox simulator.</p>
            </div>

            <form onSubmit={handleAuth} className="space-y-6">
                <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Work Email</label>
                    <div className="relative">
                        <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition-all text-sm"
                            placeholder="analyst@bank.com"
                        />
                    </div>
                </div>

                {error && <div className="text-red-500 text-xs bg-red-50 p-2 rounded border border-red-100">{error}</div>}

                <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-bold transition-all shadow-lg shadow-blue-200 flex justify-center items-center disabled:opacity-50"
                >
                    {loading ? <Loader2 size={18} className="animate-spin" /> : 'Send Magic Link'}
                </button>
            </form>

            <div className="mt-6 text-center text-xs text-slate-400">
                <p>Secured by Supabase Auth</p>
            </div>
        </motion.div>
    );
}

// --- MAIN BOOT SCREEN ---
export default function BootScreen() {
    const router = useRouter();
    const { setConnection, isConnected, user, setAuth } = useSessionStore();

    // State for DB Connection
    const [dbUrl, setDbUrl] = useState('');
    const [dbLoading, setDbLoading] = useState(false);
    const [dbError, setDbError] = useState('');

    // State for File Upload
    const [uploadLoading, setUploadLoading] = useState(false);
    const [uploadError, setUploadError] = useState('');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [customerFile, setCustomerFile] = useState<File | null>(null);

    // TTL State
    const [showTooLargeModal, setShowTooLargeModal] = useState(false);
    const [tooLargeData, setTooLargeData] = useState<{ count: number, maxAllowed: number } | null>(null);
    const [uploadMetadata, setUploadMetadata] = useState<{ uploadId: string, expiresAt: string } | null>(null);

    // Initial Auth Check
    const [authChecked, setAuthChecked] = useState(false);

    useEffect(() => {
        // Recover session if exists
        const checkSession = async () => {
            const { data } = await supabase.auth.getSession();
            if (data.session) {
                setAuth(data.session.user, data.session.access_token);
            }
            setAuthChecked(true);
        };
        checkSession();
    }, [setAuth]);

    // If connected, redirect
    useEffect(() => {
        if (isConnected && user) {
            router.push('/dashboard');
        }
    }, [isConnected, user, router]);

    // --- Conflict Handling ---
    const [conflictError, setConflictError] = useState<{
        message: string;
        expiresAt: string;
        suggestion: string;
    } | null>(null);
    const [pendingFiles, setPendingFiles] = useState<{ cust: File, tx: File } | null>(null);

    const proceedWithUpload = async (custFile: File, txFile: File, force: boolean) => {
        setConflictError(null);
        setUploadLoading(true);

        const txFormData = new FormData();
        txFormData.append('file', txFile);

        const custFormData = new FormData();
        custFormData.append('file', custFile);

        const queryParams = force ? '?force_replace=true' : '';

        try {
            // 1. Upload Customers
            const custRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/data/upload/customers${queryParams}`, {
                method: 'POST',
                body: custFormData,
            });

            if (custRes.status === 409) {
                const err = await custRes.json();
                setConflictError({
                    message: err.detail.message,
                    expiresAt: err.detail.expires_at || new Date().toISOString(),
                    suggestion: err.detail.suggestion
                });
                setPendingFiles({ cust: custFile, tx: txFile });
                setUploadLoading(false);
                return;
            }

            if (custRes.status === 413) {
                const err = await custRes.json();
                setTooLargeData({ count: err.count, maxAllowed: err.max_allowed });
                setShowTooLargeModal(true);
                setUploadLoading(false);
                return;
            }

            if (!custRes.ok) throw new Error('Customer upload failed');

            // 2. Upload Transactions
            // If we forced customers, we should force transactions to avoid conflict with the just-uploaded customers record
            const txRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/data/upload/transactions${queryParams}`, {
                method: 'POST',
                body: txFormData,
            });

            if (txRes.status === 409 && !force) {
                // If customers succeeded without force, but transactions conflict (rare but possible)
                // We just auto-retry with force because we already committed to this new upload flow
                const txResRetry = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/data/upload/transactions?force_replace=true`, {
                    method: 'POST',
                    body: txFormData,
                });
                if (!txResRetry.ok) throw new Error('Transaction upload failed on retry');
            } else if (!txRes.ok) {
                throw new Error('Transaction upload failed');
            }

            const txData = await txRes.json();
            if (txData.upload_id && txData.expires_at) {
                setUploadMetadata({
                    uploadId: txData.upload_id,
                    expiresAt: txData.expires_at
                });
            }

            setConnection('default', 'enterprise');
            router.push('/dashboard');

        } catch (e: any) {
            setUploadError(e.message || 'Upload failed');
            setUploadLoading(false);
        }
    };

    const handleFileUpload = () => {
        if (!selectedFile || !customerFile) return;
        proceedWithUpload(customerFile, selectedFile, false);
    };

    const handleEnterpriseConnect = async () => {
        if (!dbUrl) return;

        // Client-side validation: ensure PostgreSQL URL
        if (!dbUrl.startsWith('postgresql://') && !dbUrl.startsWith('postgres://')) {
            setDbError('Only PostgreSQL databases are supported. URL must start with "postgresql://" or "postgres://"');
            return;
        }

        setDbLoading(true);
        setDbError('');

        try {
            const res = await fetch('http://localhost:8000/api/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ db_url: dbUrl }),
            });

            const data = await res.json();

            if (data.status === 'connected') {
                setConnection(dbUrl, 'enterprise');
                router.push('/dashboard');
            } else {
                setDbError(data.message || 'Connection failed');
                setDbLoading(false);
            }
        } catch (e) {
            setDbError('Could not reach backend server');
            setDbLoading(false);
        }
    };

    if (!authChecked) return null; // Loading state

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-slate-50">
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-12"
            >
                <Logo width={64} height={64} className="scale-125" />
            </motion.div>

            {!user ? (
                // --- AUTH VIEW ---
                <AuthScreen onSuccess={() => { }} />
            ) : (
                // --- SETUP VIEW (Only if authenticated) ---
                <div className="grid md:grid-cols-2 gap-8 w-full max-w-5xl animate-in fade-in slide-in-from-bottom-8 duration-500">
                    {/* Option 1: Upload Dataset */}
                    <div
                        className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden flex flex-col"
                    >
                        <div className="flex items-start justify-between mb-2">
                            <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600">
                                <UploadCloud size={24} />
                            </div>
                        </div>

                        <h2 className="text-2xl font-bold text-slate-900 mb-2">Upload Data</h2>
                        <p className="text-slate-500 mb-6 leading-relaxed">
                            Initialize simulation with your data. <br />
                            <span className="text-sm text-slate-400">*Both files are required for accurate simulation.</span>
                        </p>

                        <div className="space-y-4 flex-grow">
                            {/* Transaction Upload */}
                            <div className="relative">
                                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1 block flex justify-between">
                                    <span>Transaction Data <span className="text-red-500">*</span></span>
                                    {selectedFile && <CheckCircle2 size={16} className="text-emerald-500" />}
                                </label>
                                <input
                                    type="file"
                                    accept=".csv,.xlsx,.xls"
                                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                                    className="block w-full text-sm text-slate-500
                                      file:mr-4 file:py-2 file:px-4
                                      file:rounded-full file:border-0
                                      file:text-sm file:font-semibold
                                      file:bg-blue-50 file:text-blue-700
                                      hover:file:bg-blue-100
                                      cursor-pointer border border-slate-200 rounded-lg p-1"
                                />
                            </div>

                            {/* Customer Upload */}
                            <div className="relative">
                                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1 block flex justify-between">
                                    <span>Customer Data <span className="text-red-500">*</span></span>
                                    {customerFile && <CheckCircle2 size={16} className="text-emerald-500" />}
                                </label>
                                <input
                                    type="file"
                                    accept=".csv,.xlsx,.xls"
                                    onChange={(e) => setCustomerFile(e.target.files?.[0] || null)}
                                    className="block w-full text-sm text-slate-500
                                      file:mr-4 file:py-2 file:px-4
                                      file:rounded-full file:border-0
                                      file:text-sm file:font-semibold
                                      file:bg-emerald-50 file:text-emerald-700
                                      hover:file:bg-emerald-100
                                      cursor-pointer border border-slate-200 rounded-lg p-1"
                                />
                            </div>

                            {uploadError && (
                                <div className="text-red-500 text-sm bg-red-50 p-2 rounded border border-red-100">
                                    {uploadError}
                                </div>
                            )}
                        </div>

                        <button
                            onClick={handleFileUpload}
                            disabled={uploadLoading || !selectedFile || !customerFile}
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-bold transition-all flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed mt-6 shadow-lg shadow-blue-200"
                        >
                            {uploadLoading ? <Loader2 size={18} className="animate-spin mr-2" /> : <div className="flex items-center">Ignite Simulation <ArrowRight size={18} className="ml-2" /></div>}
                        </button>
                    </div>

                    {/* Option 2: Connect DB */}
                    <div
                        className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden flex flex-col"
                    >
                        <div className="w-12 h-12 bg-slate-100 rounded-xl flex items-center justify-center mb-6 text-slate-700">
                            <Database size={24} />
                        </div>

                        <h2 className="text-2xl font-bold text-slate-900 mb-2">Connect Database</h2>
                        <p className="text-slate-500 mb-6 leading-relaxed flex-grow">
                            Connect to an existing Enterprise PostgreSQL instance for live production data analysis.
                        </p>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Database Connection String</label>
                                <input
                                    type="text"
                                    placeholder="postgresql://user:pass@host:5432/db"
                                    className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-sm font-mono"
                                    value={dbUrl}
                                    onChange={(e) => setDbUrl(e.target.value)}
                                />
                            </div>

                            {dbError && (
                                <div className="text-red-500 text-sm bg-red-50 p-2 rounded border border-red-100">
                                    {dbError}
                                </div>
                            )}

                            <button
                                onClick={handleEnterpriseConnect}
                                disabled={dbLoading || !dbUrl}
                                className="w-full bg-slate-900 hover:bg-slate-800 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {dbLoading ? <Loader2 size={18} className="animate-spin mr-2" /> : <div className="flex items-center">Connect & Boot <ArrowRight size={16} className="ml-2" /></div>}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Dataset Too Large Modal */}
            {tooLargeData && (
                <DatasetTooLargeModal
                    open={showTooLargeModal}
                    onClose={() => setShowTooLargeModal(false)}
                    recordCount={tooLargeData.count}
                    maxAllowed={tooLargeData.maxAllowed}
                    onConnectDatabase={() => {
                        setShowTooLargeModal(false);
                        // Scroll to database connection section
                        const dbSection = document.querySelector('[data-section="db-connect"]');
                        dbSection?.scrollIntoView({ behavior: 'smooth' });
                    }}
                />
            )}

            {/* Conflict Modal */}
            {conflictError && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
                >
                    <motion.div
                        initial={{ scale: 0.95 }}
                        animate={{ scale: 1 }}
                        className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-slate-200"
                    >
                        <div className="flex items-center gap-3 text-amber-600 mb-4">
                            <div className="p-2 bg-amber-50 rounded-lg">
                                <AlertTriangle size={24} />
                            </div>
                            <h3 className="text-lg font-bold text-slate-900">Existing Data Found</h3>
                        </div>

                        <p className="text-slate-600 mb-4 leading-relaxed">
                            {conflictError.message}
                        </p>

                        <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-6 text-sm">
                            <p className="flex justify-between mb-2">
                                <span className="text-slate-500">Expires At:</span>
                                <span className="font-medium text-slate-900">
                                    <span className="font-semibold">Expiry (IST):</span>{' '}
                                    {formatIST(conflictError.expiresAt)}
                                </span>
                            </p>
                            <p className="text-amber-700 text-xs mt-2 italic">
                                {conflictError.suggestion}
                            </p>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setConflictError(null)}
                                className="flex-1 py-2.5 px-4 rounded-lg font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    if (pendingFiles) {
                                        proceedWithUpload(pendingFiles.cust, pendingFiles.tx, true);
                                    }
                                }}
                                className="flex-1 py-2.5 px-4 rounded-lg font-medium bg-amber-600 text-white hover:bg-amber-700 transition-colors shadow-sm"
                            >
                                Replace Data
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}


            <p className="mt-12 text-slate-400 text-sm font-medium">
                SecureCore Sandbox Simulator v1.5
            </p>
        </div>
    );
}
