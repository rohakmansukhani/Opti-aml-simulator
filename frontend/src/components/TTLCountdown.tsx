'use client';

import { useEffect, useState } from 'react';
import { Clock, AlertCircle } from 'lucide-react';
import { Button } from '@mui/material';

interface TTLCountdownProps {
    expiresAt: string; // ISO timestamp
    uploadId: string;
    onExtend?: () => void;
}

export function TTLCountdown({ expiresAt, uploadId, onExtend }: TTLCountdownProps) {
    const [timeRemaining, setTimeRemaining] = useState('');
    const [isWarning, setIsWarning] = useState(false);

    useEffect(() => {
        const calculateTimeRemaining = () => {
            const now = new Date().getTime();
            const expiry = new Date(expiresAt).getTime();
            const diff = expiry - now;

            if (diff <= 0) {
                setTimeRemaining('Expired');
                return;
            }

            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

            // Warning if less than 6 hours
            setIsWarning(hours < 6);

            if (hours > 24) {
                const days = Math.floor(hours / 24);
                setTimeRemaining(`${days}d ${hours % 24}h`);
            } else if (hours > 0) {
                setTimeRemaining(`${hours}h ${minutes}m`);
            } else {
                setTimeRemaining(`${minutes}m`);
            }
        };

        calculateTimeRemaining();
        const interval = setInterval(calculateTimeRemaining, 60000); // Update every minute

        return () => clearInterval(interval);
    }, [expiresAt]);

    if (timeRemaining === 'Expired') {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-3">
                <AlertCircle className="text-red-600" size={20} />
                <div className="flex-1">
                    <p className="text-sm font-semibold text-red-900">Data Expired</p>
                    <p className="text-xs text-red-700">Your uploaded data has been automatically deleted</p>
                </div>
            </div>
        );
    }

    return (
        <div className={`border rounded-lg p-3 flex items-center gap-3 ${isWarning
                ? 'bg-amber-50 border-amber-200'
                : 'bg-blue-50 border-blue-200'
            }`}>
            <Clock className={isWarning ? 'text-amber-600' : 'text-blue-600'} size={20} />
            <div className="flex-1">
                <p className="text-sm font-semibold text-slate-900">
                    {isWarning ? 'Expiring Soon' : 'Data Active'}
                </p>
                <p className="text-xs text-slate-600">
                    {timeRemaining} remaining • Auto-deletes after 48 hours
                </p>
            </div>
            {onExtend && isWarning && (
                <Button
                    size="small"
                    variant="outlined"
                    onClick={onExtend}
                >
                    Extend +24h
                </Button>
            )}
        </div>
    );
}
