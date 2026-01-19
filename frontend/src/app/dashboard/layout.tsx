'use client';

import { Logo } from '@/components/Logo';
import { useSessionStore } from '@/store/useSessionStore';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    LayoutDashboard,
    PlayCircle,
    GitCompare,
    FileText,
    Settings,
    LogOut,
    Database,
    X,
    FileCheck,
} from 'lucide-react';
import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { Tooltip } from '@mui/material';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const disconnect = useSessionStore((s) => s.disconnect);
    const logout = useSessionStore((s) => s.logout);

    const [showDisconnectModal, setShowDisconnectModal] = useState(false);

    const handleDisconnectDB = () => {
        disconnect(); // Clear only DB connection
        window.location.href = '/';
    };

    const handleSignOut = async () => {
        await supabase.auth.signOut();
        logout(); // Clear everything
        window.location.href = '/';
    };

    const navItems = [
        { name: 'Overview', href: '/dashboard', icon: LayoutDashboard },
        { name: 'Builder', href: '/dashboard/builder', icon: PlayCircle },
        { name: 'Rules', href: '/dashboard/rules', icon: FileCheck },
        { name: 'Comparison', href: '/dashboard/compare', icon: GitCompare },
        { name: 'Reports', href: '/dashboard/reports', icon: FileText },
    ];

    return (
        <div className="min-h-screen bg-slate-50 flex">
            {/* Sidebar */}
            <aside className="w-64 bg-white border-r border-slate-200 fixed h-full z-10 hidden md:flex flex-col">
                <div className="p-6 border-b border-slate-100">
                    <Logo width={40} height={40} />
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.name}
                                href={item.href}
                                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${isActive
                                    ? 'bg-blue-50 text-blue-700'
                                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                                    }`}
                            >
                                <item.icon size={20} className={`mr-3 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                                {item.name}
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-4 space-y-2 border-t border-slate-100">
                    {/* User Profile Info */}
                    <div className="flex items-center px-4 py-3 mb-2 bg-slate-50 rounded-xl border border-slate-100">
                        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
                            {useSessionStore.getState().user?.email?.[0].toUpperCase() || 'U'}
                        </div>
                        <div className="ml-3 overflow-hidden flex-1">
                            <Tooltip title={useSessionStore.getState().user?.email || 'User'} arrow placement="right">
                                <div
                                    className="text-xs font-semibold text-slate-900 break-all line-clamp-1 cursor-help"
                                >
                                    {useSessionStore.getState().user?.email || 'User'}
                                </div>
                            </Tooltip>
                            <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                                Active Account
                            </div>
                        </div>
                    </div>

                    <button
                        className="flex items-center w-full px-4 py-3 text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors group"
                        onClick={() => setShowDisconnectModal(true)}
                    >
                        <LogOut size={20} className="mr-3 text-slate-400 group-hover:text-red-500 transition-colors" />
                        Disconnect
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 md:ml-64 relative">
                {children}
            </main>

            {/* Disconnect Modal */}
            {showDisconnectModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm border border-slate-100 overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-6">
                            <div className="flex justify-between items-start mb-4">
                                <div className="p-3 bg-red-50 rounded-full text-red-600">
                                    <LogOut size={24} />
                                </div>
                                <button
                                    onClick={() => setShowDisconnectModal(false)}
                                    className="text-slate-400 hover:text-slate-600 transition-colors"
                                >
                                    <X size={20} />
                                </button>
                            </div>

                            <h3 className="text-lg font-bold text-slate-900 mb-2">Disconnect Session</h3>
                            <p className="text-slate-500 text-sm mb-6">
                                How would you like to disconnect?
                            </p>

                            <div className="space-y-3">
                                <button
                                    onClick={handleDisconnectDB}
                                    className="w-full flex items-center p-4 rounded-xl border border-slate-200 hover:border-blue-500 hover:bg-blue-50 transition-all group text-left"
                                >
                                    <div className="p-2 bg-slate-100 rounded-lg text-slate-600 group-hover:bg-blue-100 group-hover:text-blue-600 mr-4">
                                        <Database size={20} />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-slate-900 group-hover:text-blue-700 text-sm">Disconnect Database</div>
                                        <div className="text-xs text-slate-500">Switch dataset but stay logged in</div>
                                    </div>
                                </button>

                                <button
                                    onClick={handleSignOut}
                                    className="w-full flex items-center p-4 rounded-xl border border-slate-200 hover:border-red-500 hover:bg-red-50 transition-all group text-left"
                                >
                                    <div className="p-2 bg-slate-100 rounded-lg text-slate-600 group-hover:bg-red-100 group-hover:text-red-600 mr-4">
                                        <LogOut size={20} />
                                    </div>
                                    <div>
                                        <div className="font-semibold text-slate-900 group-hover:text-red-700 text-sm">Sign Out</div>
                                        <div className="text-xs text-slate-500">Log out of your account</div>
                                    </div>
                                </button>
                            </div>
                        </div>

                        <div className="bg-slate-50 p-4 flex justify-center">
                            <button
                                onClick={() => setShowDisconnectModal(false)}
                                className="text-sm font-medium text-slate-500 hover:text-slate-800"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
