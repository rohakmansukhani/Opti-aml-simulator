'use client';

import { useRef, useEffect } from 'react';

import { WizardFrame } from '@/components/wizard/WizardFrame';
import ScenarioInfoStep from '@/components/wizard/ScenarioInfoStep';
import FilterConfigStep from '@/components/wizard/FilterConfigStep';
import AggregationStep from '@/components/wizard/AggregationStep';
import ThresholdStep from '@/components/wizard/ThresholdStep';
import ReviewStep from '@/components/wizard/ReviewStep';
import { useBuilderStore } from '@/store/useBuilderStore';
import { Button } from '@mui/material';
import { ArrowLeft, ArrowRight } from 'lucide-react';

export default function BuilderPage() {
    const { currentStep, nextStep, prevStep, fetchSchema, updateConfig } = useBuilderStore();

    // Fetch schema when builder opens
    useEffect(() => {
        fetchSchema();
    }, [fetchSchema]);

    // Load scenario from localStorage if editing
    useEffect(() => {
        const editScenarioData = localStorage.getItem('editScenario');
        if (editScenarioData) {
            try {
                const scenario = JSON.parse(editScenarioData);

                // Populate the builder store with scenario data
                updateConfig({
                    scenario_id: scenario.scenario_id,
                    scenario_name: scenario.scenario_name,
                    priority: scenario.priority || 'High',
                    is_active: scenario.is_active,
                    config_json: scenario.config_json
                });

                // Clear localStorage after loading
                localStorage.removeItem('editScenario');
            } catch (err) {
                console.error('Failed to load edit scenario:', err);
            }
        }
    }, [updateConfig]);

    const renderStep = () => {
        switch (currentStep) {
            case 0: return <ScenarioInfoStep />;
            case 1: return <FilterConfigStep />;
            case 2: return <AggregationStep />;
            case 3: return <ThresholdStep />;
            case 4: return <ReviewStep />;
            default: return null;
        }
    };

    return (
        <div className="p-8">
            <div className="mb-8 ">
                <h1 className="text-3xl font-bold text-slate-900">Scenario Builder</h1>
                <p className="text-slate-500">Create new detection logic using the visual wizard.</p>
            </div>

            <WizardFrame>
                {renderStep()}

                {/* Navigation Actions (Bottom Bar) */}
                <div className="mt-12 flex justify-between border-t border-slate-100 pt-6">
                    <Button
                        variant="text"
                        startIcon={<ArrowLeft size={18} />}
                        onClick={prevStep}
                        disabled={currentStep === 0}
                        className="text-slate-500"
                    >
                        Back
                    </Button>

                    {currentStep < 4 && (
                        <Button
                            variant="contained"
                            endIcon={<ArrowRight size={18} />}
                            onClick={nextStep}
                            disableElevation
                        >
                            Continue
                        </Button>
                    )}
                </div>
            </WizardFrame>
        </div>
    );
}
