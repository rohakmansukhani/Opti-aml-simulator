'use client';

import { useBuilderStore } from '@/store/useBuilderStore';
import { motion, AnimatePresence } from 'framer-motion';
import { Check } from 'lucide-react';

const STEPS = [
    'Details',
    'Filters',
    'Aggregation',
    'Thresholds',
    'Review'
];

export function WizardFrame({ children }: { children: React.ReactNode }) {
    const { currentStep } = useBuilderStore();

    return (
        <div className="max-w-6xl mx-auto py-4">
            {/* Stepper Header */}
            <div className="mb-8 px-4">
                <div className="flex justify-between items-center relative">
                    {/* Line Background */}
                    <div className="absolute top-1/2 left-0 w-full h-[2px] bg-slate-200 -z-10" />
                    <motion.div
                        className="absolute top-1/2 left-0 h-[2px] bg-gradient-to-r from-blue-600 to-indigo-500 -z-10"
                        initial={{ width: 0 }}
                        animate={{ width: `${(currentStep / (STEPS.length - 1)) * 100}%` }}
                        transition={{ duration: 0.5, ease: "easeInOut" }}
                    />

                    {STEPS.map((step, idx) => {
                        const isCompleted = idx < currentStep;
                        const isCurrent = idx === currentStep;

                        return (
                            <div key={idx} className="flex flex-col items-center relative z-10 group cursor-default">
                                <motion.div
                                    initial={false}
                                    animate={{
                                        scale: isCurrent ? 1.1 : 1,
                                        backgroundColor: isCompleted || isCurrent ? '#fff' : '#F8FAFC',
                                        borderColor: isCompleted || isCurrent ? '#2563EB' : '#E2E8F0',
                                    }}
                                    className={`w-12 h-12 rounded-2xl rotate-45 flex items-center justify-center border-2 shadow-sm transition-all duration-300 ${isCurrent ? 'shadow-blue-200 border-blue-500' : ''}`}
                                >
                                    <div className="-rotate-45 flex items-center justify-center w-full h-full">
                                        {isCompleted ? (
                                            <Check size={20} className="text-blue-600" strokeWidth={3} />
                                        ) : (
                                            <span className={`text-sm font-bold ${isCurrent ? 'text-blue-600' : 'text-slate-400'}`}>
                                                {idx + 1}
                                            </span>
                                        )}
                                    </div>
                                </motion.div>
                                <span className={`absolute top-16 text-xs font-bold tracking-wide transition-colors duration-300 ${isCurrent ? 'text-blue-700' : 'text-slate-400'}`}>
                                    {step}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Step Content Card */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={currentStep}
                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.98 }}
                    transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                    className="mt-12 bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl shadow-slate-200/50 border border-white/50 p-10 min-h-[550px] relative"
                >
                    {/* Decorative Background Elements */}
                    <div className="absolute top-0 right-0 w-64 h-64 bg-blue-50/50 rounded-full blur-3xl -z-10 transform translate-x-1/3 -translate-y-1/3" />
                    <div className="absolute bottom-0 left-0 w-64 h-64 bg-indigo-50/50 rounded-full blur-3xl -z-10 transform -translate-x-1/3 translate-y-1/3" />

                    {children}
                </motion.div>
            </AnimatePresence>
        </div>
    );
}
