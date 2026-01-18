/**
 * SAS Simulator Domain Models
 * Aligns with backend Pydantic models in `backend/models/*.py`
 */

export interface ScenarioConfig {
    scenario_id: string;
    scenario_name: string;
    description?: string;
    is_active: boolean;
    priority: 'High' | 'Medium' | 'Low';
    config_json?: ScenarioDefinition;
    created_at?: string;
    updated_at?: string;
}

export interface ScenarioDefinition {
    filters: FilterConfig[];
    aggregation?: AggregationConfig;
    threshold: ThresholdConfig;
    trigger_condition: string;
}

export interface FilterConfig {
    field: string;
    operator: '==' | '!=' | '>' | '<' | '>=' | '<=' | 'in' | 'contains';
    value: string | number | string[];
}

export interface AggregationConfig {
    group_by: string[];
    time_window?: {
        value: number;
        unit: 'days' | 'months';
        type: 'rolling' | 'calendar';
    };
    // Flattened for single-metric engine
    method: 'sum' | 'count' | 'avg' | 'max' | 'min';
    field: string;
}

export interface ThresholdConfig {
    type: "fixed" | "field_based" | "segment_based";
    fixed_value?: number;
    field_based?: {
        reference_field: string;
        calculation: string;
    };
    segment_based?: {
        segment_field: string;
        values: Record<string, number>;
        default: number;
    };
}

export interface SimulationRun {
    run_id: string;
    run_type: 'baseline' | 'refined';
    status: 'pending' | 'running' | 'completed' | 'failed';
    total_alerts: number;
    scenarios_run: string[];
    executed_at: string;
    completed_at?: string;
    metadata_info?: Record<string, any>;
}

export interface ComparisonReport {
    baseline_run_id: string;
    refined_run_id: string;
    summary: {
        baseline_alerts: number;
        refined_alerts: number;
        net_change: number;
        percent_reduction: number;
    };
    granular_diff: AlertDiffItem[];
    risk_analysis: RiskAnalysisResult;
}

export interface AlertDiffItem {
    match_key: string;
    customer_id: string;
    scenario_id: string;
    status: 'RETAINED' | 'EXCLUDED' | 'NEW_ALERT' | 'DROPPED_SILENTLY';
    alert_date: string;
    amount?: number;
}

export interface RiskAnalysisResult {
    risk_score: number;
    risk_level: 'SAFE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    sample_exploits: ExploitScenario[];
}

export interface ExploitScenario {
    title: string;
    description: string;
    severity: 'High' | 'Medium' | 'Low';
}
