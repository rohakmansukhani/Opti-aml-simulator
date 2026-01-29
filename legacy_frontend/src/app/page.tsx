'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Logo } from '@/components/Logo';
import { useSessionStore } from '@/store/useSessionStore';
import { useRouter } from 'next/navigation';
import { UploadCloud, Database, ArrowRight, Loader2, CheckCircle2, Mail, AlertTriangle, LogOut } from 'lucide-react';
import { supabase } from '@/lib/supabase';
import { formatDateIST, formatIST } from '@/lib/date-utils';
import { DatasetTooLargeModal } from '@/components/DatasetTooLargeModal';
import { TTLCountdown } from '@/components/TTLCountdown';

// --- AUTH COMPONENT ---
// --- AUTH COMPONENT ---
function AuthScreen({ onSuccess }: { onSuccess: () => void }) {
    const [mode, setMode] = useState<'signin' | 'signup'>('signin');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
    const setAuth = useSessionStore((s) => s.setAuth);

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        try {
            if (mode === 'signup') {
                // 1. Sign Up
                const { data, error } = await supabase.auth.signUp({
                    email,
                    password,
                    options: {
                        data: {
                            full_name: fullName,
                        },
                        emailRedirectTo: typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : undefined,
                    }
                });

                if (error) throw error;

                if (data.user && !data.session) {
                    setMessage({
                        type: 'success',
                        text: 'Account created! Please check your email to verify your account.'
                    });
                } else if (data.session) {
                    onSuccess();
                }
            } else {
                // 2. Sign In
                const { data, error } = await supabase.auth.signInWithPassword({
                    email,
                    password
                });

                if (error) throw error;
                if (data.session) {
                    setAuth(data.session.user, data.session.access_token);
                    onSuccess();
                }
            }
        } catch (err: any) {
            setMessage({
                type: 'error',
                text: err.message || 'Authentication failed'
            });
        } finally {
            setLoading(false);
        }
    };

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
                <p className="text-slate-500 text-sm mt-1">
                    {mode === 'signin' ? 'Sign in to access your sandbox simulator.' : 'Create an account to get started.'}
                </p>
            </div>

            <form onSubmit={handleAuth} className="space-y-4">
                {mode === 'signup' && (
                    <div>
                        <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Full Name</label>
                        <input
                            type="text"
                            required
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition-all text-sm"
                            placeholder="John Doe"
                        />
                    </div>
                )}

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

                <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Password</label>
                    <input
                        type="password"
                        required
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition-all text-sm"
                        placeholder="••••••••"
                        minLength={6}
                    />
                </div>

                {message && (
                    <div className={`text-xs p-3 rounded border ${message.type === 'success'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                        : 'bg-red-50 text-red-700 border-red-100'
                        }`}>
                        {message.text}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-bold transition-all shadow-lg shadow-blue-200 flex justify-center items-center disabled:opacity-50"
                >
                    {loading ? <Loader2 size={18} className="animate-spin" /> : (mode === 'signin' ? 'Sign In' : 'Create Account')}
                </button>

                <button
                    type="button"
                    onClick={() => {
                        setAuth({ id: 'demo-user', email: 'demo@example.com' }, 'demo-token');
                        onSuccess();
                    }}
                    className="w-full bg-slate-50 hover:bg-slate-100 text-slate-600 py-3 rounded-lg font-bold border border-slate-200 transition-all mt-4"
                >
                    Enter in Demo Mode (Dev only)
                </button>
            </form>

            <div className="mt-6 text-center text-sm">
                <p className="text-slate-500">
                    {mode === 'signin' ? "Don't have an account?" : "Already have an account?"}{' '}
                    <button
                        onClick={() => {
                            setMode(mode === 'signin' ? 'signup' : 'signin');
                            setMessage(null);
                        }}
                        className="text-blue-600 font-semibold hover:underline"
                    >
                        {mode === 'signin' ? 'Sign Up' : 'Sign In'}
                    </button>
                </p>
            </div>

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
    const logout = useSessionStore((s) => s.logout);

    const handleSignOut = async () => {
        await supabase.auth.signOut();
        logout();
        window.location.reload();
    };

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
            const token = useSessionStore.getState().token;
            // 1. Upload Customers
            const custRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/data/upload/customers${queryParams}`, {
                method: 'POST',
                headers: token ? { 'Authorization': `Bearer ${token}` } : {},
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
                headers: token ? { 'Authorization': `Bearer ${token}` } : {},
                body: txFormData,
            });

            if (txRes.status === 409 && !force) {
                // If customers succeeded without force, but transactions conflict (rare but possible)
                // We just auto-retry with force because we already committed to this new upload flow
                const txResRetry = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/data/upload/transactions?force_replace=true`, {
                    method: 'POST',
                    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
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
            const token = useSessionStore.getState().token;
            const res = await fetch('http://localhost:8000/api/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
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
                <div className="w-full max-w-5xl relative">
                    {/* Floating Logout Button */}
                    <div className="absolute -top-16 right-0">
                        <button
                            onClick={handleSignOut}
                            className="flex items-center px-4 py-2 text-sm font-medium text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all border border-slate-200 bg-white shadow-sm"
                        >
                            <LogOut size={16} className="mr-2" />
                            Sign Out
                        </button>
                    </div>

                    <div className="grid md:grid-cols-2 gap-8 w-full animate-in fade-in slide-in-from-bottom-8 duration-500">
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
