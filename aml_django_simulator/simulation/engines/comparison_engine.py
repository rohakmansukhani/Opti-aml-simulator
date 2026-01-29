"""
Comparison Engine - Analyzes two simulation runs to quantify refinement effectiveness (Django Native)
"""

from typing import Dict, List, Any
from simulation.models import Alert, SimulationRun, Transaction, AlertTransaction
import logging
import uuid

logger = logging.getLogger(__name__)

class ComparisonEngine:
    """
    Compares two simulation runs (Baseline vs Refined) to quantify
    refinement effectiveness and security trade-offs.
    """
    
    def compare_runs(
        self, 
        baseline_run_id: str, 
        refined_run_id: str
    ) -> Dict[str, Any]:
        """
        Main comparison method.
        """
        logger.info(f"Comparison started: {baseline_run_id} vs {refined_run_id}")
        
        # Step 1: Load raw alert sets
        baseline_alerts = list(Alert.objects.filter(simulation_run__run_id=baseline_run_id))
        refined_alerts = list(Alert.objects.filter(simulation_run__run_id=refined_run_id))
        
        # Step 2: Calculate high-level summary
        summary = self._calculate_summary(baseline_alerts, refined_alerts)
        
        # Step 3: Granular customer-level diff
        granular_diff = self._calculate_granular_diff(
            baseline_alerts, 
            refined_alerts
        )
        
        # Step 4: Risk analysis
        risk_analysis = self._analyze_risk(
            baseline_alerts,
            refined_alerts,
            granular_diff
        )
        
        result_json = {
            "summary": summary,
            "granular_diff": granular_diff,
            "risk_analysis": risk_analysis,
            "metadata": {
                "baseline_run_id": baseline_run_id,
                "refined_run_id": refined_run_id,
                "comparison_type": "customer_centric"
            }
        }
        
        return result_json
    
    def _calculate_summary(
        self, 
        baseline_alerts: List[Alert], 
        refined_alerts: List[Alert]
    ) -> Dict[str, Any]:
        """Calculate high-level reduction metrics."""
        baseline_customers = set(a.customer_id for a in baseline_alerts)
        refined_customers = set(a.customer_id for a in refined_alerts)
        
        maintained = len(baseline_customers & refined_customers)
        removed = len(baseline_customers - refined_customers)
        added = len(refined_customers - baseline_customers)
        
        baseline_count = len(baseline_alerts)
        refined_count = len(refined_alerts)
        net_change = baseline_count - refined_count
        
        reduction_rate = (net_change / baseline_count * 100) if baseline_count > 0 else 0
        
        return {
            "baseline_alerts": baseline_count,
            "refined_alerts": refined_count,
            "net_change": net_change,
            "reduction_rate": round(reduction_rate, 2),
            "maintained_customers": maintained,
            "removed_customers": removed,
            "added_customers": added
        }
    
    def _calculate_granular_diff(
        self,
        baseline_alerts: List[Alert],
        refined_alerts: List[Alert],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Calculate customer-level granular diff including added, removed, and maintained."""
        
        baseline_map = {a.customer_id: a for a in baseline_alerts}
        refined_map = {a.customer_id: a for a in refined_alerts}
        
        all_customers = set(baseline_map.keys()) | set(refined_map.keys())
        granular_diff = []
        
        for cid in all_customers:
            in_baseline = cid in baseline_map
            in_refined = cid in refined_map
            
            status = "maintained"
            if in_baseline and not in_refined:
                status = "removed"
            elif not in_baseline and in_refined:
                status = "added"
            
            # Use the alert from the most recent run for display data
            alert = refined_map.get(cid) or baseline_map.get(cid)
            
            # Calculate risk change for maintained
            risk_change = 0
            if in_baseline and in_refined:
                risk_change = refined_map[cid].risk_score - baseline_map[cid].risk_score

            granular_diff.append({
                "customer_id": cid,
                "status": status,
                "risk_score": alert.risk_score,
                "risk_change": risk_change,
                "scenario": alert.scenario_name,
                "amount": float(alert.trigger_details.get('aggregated_value', 0)) if alert.trigger_details else 0,
                "reason": alert.trigger_reason
            })
        
        # Sort by risk score (desc) then status
        granular_diff.sort(key=lambda x: (x["risk_score"]), reverse=True)
        
        return granular_diff[:limit] if limit else granular_diff
    
    def _analyze_risk(
        self,
        baseline_alerts: List[Alert],
        refined_alerts: List[Alert],
        granular_diff: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze risk of suppressed alerts."""
        
        high_risk_suppressions = len(granular_diff)
        
        if not granular_diff:
            risk_score = 0.0
            risk_level = "SAFE"
        else:
            # Average of top 10 risk scores
            top_risks = sorted(
                [item["risk_score"] for item in granular_diff],
                reverse=True
            )[:10]
            risk_score = sum(top_risks) / len(top_risks) if top_risks else 0.0
            
            # Classify risk level
            if high_risk_suppressions > 0:
                risk_level = "CRITICAL"
            elif risk_score >= 50:
                risk_level = "DANGEROUS"
            elif risk_score >= 25:
                risk_level = "CAUTION"
            else:
                risk_level = "SAFE"
        
        # Generate sample exploits (top 3 suppressions)
        sample_exploits = []
        for item in granular_diff[:3]:
            sample_exploits.append(
                f"Customer {item['customer_id']}: "
                f"${item['amount']:,.0f} suppressed "
                f"(score: {item['risk_score']})"
            )
        
        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "sample_exploits": sample_exploits,
            "high_risk_suppressions": high_risk_suppressions,
            "total_suppressions": len(granular_diff)
        }
    
    def get_run_metadata(self, run_id: str) -> Dict[str, Any]:
        """Get metadata for a simulation run."""
        try:
            run = SimulationRun.objects.get(run_id=run_id)
            return {
                "run_id": run.run_id,
                "run_type": run.run_type,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "total_alerts": run.total_alerts,
                "total_transactions": run.total_transactions,
                "status": run.status
            }
        except SimulationRun.DoesNotExist:
            return {}
