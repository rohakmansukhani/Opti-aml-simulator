"""
Comparison Engine - Analyzes two simulation runs to quantify refinement effectiveness

Purpose:
    Compare Baseline vs Refined runs to prove refinements reduce noise
    without missing high-risk alerts.

Key Metrics:
    - Alert reduction percentage
    - Customer-level granular diff
    - Risk analysis of suppressed alerts
    
Business Value:
    Data-driven refinement approval with quantified trade-offs
"""

from typing import Dict, List, Any
from sqlalchemy.orm import Session
from models import Alert, SimulationRun
import structlog
import uuid

logger = structlog.get_logger("comparison_engine")


class ComparisonEngine:
    """
    Compares two simulation runs (Baseline vs Refined) to quantify
    refinement effectiveness and security trade-offs.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def compare_runs(
        self, 
        baseline_run_id: str, 
        refined_run_id: str
    ) -> Dict[str, Any]:
        """
        Main comparison method. Persists results to DB.
        """
        # 0. Check for existing comparison
        from models import SimulationComparison
        existing = self.db.query(SimulationComparison).filter(
            SimulationComparison.base_run_id == baseline_run_id,
            SimulationComparison.challenger_run_id == refined_run_id
        ).first()
        
        if existing and existing.comparison_details:
            logger.info("comparison_cache_hit", comparison_id=existing.comparison_id)
            return existing.comparison_details

        logger.info(
            "comparison_started",
            baseline_run_id=baseline_run_id,
            refined_run_id=refined_run_id
        )
        
        # Step 1: Load raw alert sets
        baseline_alerts = self._load_alerts(baseline_run_id)
        refined_alerts = self._load_alerts(refined_run_id)
        
        # Step 2: Calculate high-level summary
        summary = self._calculate_summary(baseline_alerts, refined_alerts)
        
        # Step 3: Granular customer-level diff
        granular_diff = self._calculate_granular_diff(
            baseline_alerts, 
            refined_alerts
        )
        
        # Step 4: Risk analysis (red-teaming)
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
        
        # Persist to DB
        try:
            # Efficiency Score calculation (Simple: % reduction * (1 - risk score/100))
            eff_score = summary['percent_reduction'] * (1 - (risk_analysis['risk_score'] / 100))
            
            comparison_record = SimulationComparison(
                comparison_id=str(uuid.uuid4()),
                base_run_id=baseline_run_id,
                challenger_run_id=refined_run_id,
                alerts_delta=summary['net_change'],
                efficiency_score=eff_score,
                overlap_count=summary['refined_alerts'], # Approximation assuming refined is subset
                comparison_details=result_json
            )
            self.db.add(comparison_record)
            self.db.commit()
        except Exception as e:
            logger.error("comparison_persist_failed", error=str(e))
            self.db.rollback()
        
        return result_json
    
    def _load_alerts(self, run_id: str) -> List[Alert]:
        """
        Load all alerts for a given run.
        
        Args:
            run_id: Simulation run ID
            
        Returns:
            List of Alert objects
        """
        alerts = self.db.query(Alert).filter(
            Alert.run_id == run_id
        ).all()
        
        logger.debug(
            "alerts_loaded",
            run_id=run_id,
            count=len(alerts)
        )
        
        return alerts
    
    def _calculate_summary(
        self, 
        baseline_alerts: List[Alert], 
        refined_alerts: List[Alert]
    ) -> Dict[str, Any]:
        """
        Calculate high-level reduction metrics.
        
        Returns:
            {
                "baseline_alerts": int,
                "refined_alerts": int,
                "net_change": int,
                "percent_reduction": float
            }
        """
        baseline_count = len(baseline_alerts)
        refined_count = len(refined_alerts)
        net_change = baseline_count - refined_count
        
        # Handle edge case: no baseline alerts
        if baseline_count == 0:
            percent_reduction = 0.0
        else:
            percent_reduction = (net_change / baseline_count) * 100
        
        return {
            "baseline_alerts": baseline_count,
            "refined_alerts": refined_count,
            "net_change": net_change,
            "percent_reduction": round(percent_reduction, 2)
        }
    
    def _calculate_granular_diff(
        self,
        baseline_alerts: List[Alert],
        refined_alerts: List[Alert]
    ) -> List[Dict[str, Any]]:
        """
        Calculate customer-level granular diff.
        
        Strategy: Customer-centric matching
        - Identifies customers with alerts in baseline but not in refined
        - Business cares: "Did we suppress alerts for risky customers?"
        
        Returns:
            List of {customer_id, status, alert_count, total_amount}
            Limited to top 50 for UI performance
        """
        # Extract customer IDs from both sets
        baseline_customers = set(alert.customer_id for alert in baseline_alerts)
        refined_customers = set(alert.customer_id for alert in refined_alerts)
        
        # Find removed customers (alerts suppressed by refinement)
        removed_customers = baseline_customers - refined_customers
        
        # Build detailed diff with aggregated metrics
        granular_diff = []
        
        for customer_id in removed_customers:
            # Get all baseline alerts for this customer
            customer_alerts = [
                alert for alert in baseline_alerts 
                if alert.customer_id == customer_id
            ]
            
            # Aggregate metrics
            alert_count = len(customer_alerts)
            total_amount = sum(
                alert.aggregated_amount or 0 
                for alert in customer_alerts
            )
            
            # Get highest risk score
            max_risk_score = max(
                (alert.risk_score or 0 for alert in customer_alerts),
                default=0
            )
            
            granular_diff.append({
                "customer_id": customer_id,
                "status": "removed",
                "alert_count": alert_count,
                "total_amount": round(total_amount, 2),
                "max_risk_score": round(max_risk_score, 2),
                "scenarios": list(set(
                    alert.scenario_id for alert in customer_alerts
                ))
            })
        
        # Sort by risk score (highest first) and limit to top 50
        granular_diff.sort(key=lambda x: x["max_risk_score"], reverse=True)
        
        logger.info(
            "granular_diff_calculated",
            removed_customers=len(removed_customers),
            top_50_limited=len(granular_diff[:50])
        )
        
        return granular_diff[:50]
    
    def _analyze_risk(
        self,
        baseline_alerts: List[Alert],
        refined_alerts: List[Alert],
        granular_diff: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze risk of suppressed alerts (Red-Teaming).
        
        Current: Placeholder implementation
        Future: Integrate RiskEngine for deep analysis
        
        Returns:
            {
                "risk_score": float (0-100),
                "risk_level": str (SAFE/CAUTION/DANGEROUS/CRITICAL),
                "sample_exploits": List[str],
                "high_risk_suppressions": int
            }
        """
        # Count high-risk suppressions (risk_score > 70)
        high_risk_suppressions = sum(
            1 for item in granular_diff 
            if item["max_risk_score"] > 70
        )
        
        # Calculate overall risk score
        if not granular_diff:
            risk_score = 0.0
            risk_level = "SAFE"
        else:
            # Average of top 10 risk scores
            top_risks = sorted(
                [item["max_risk_score"] for item in granular_diff],
                reverse=True
            )[:10]
            risk_score = sum(top_risks) / len(top_risks) if top_risks else 0.0
            
            # Classify risk level
            if risk_score >= 75:
                risk_level = "CRITICAL"
            elif risk_score >= 50:
                risk_level = "DANGEROUS"
            elif risk_score >= 25:
                risk_level = "CAUTION"
            else:
                risk_level = "SAFE"
        
        # Generate sample exploits (top 3 high-risk suppressions)
        sample_exploits = []
        for item in granular_diff[:3]:
            if item["max_risk_score"] > 50:
                sample_exploits.append(
                    f"Customer {item['customer_id']}: "
                    f"${item['total_amount']:,.0f} suppressed "
                    f"(risk: {item['max_risk_score']})"
                )
        
        logger.info(
            "risk_analysis_completed",
            risk_score=risk_score,
            risk_level=risk_level,
            high_risk_suppressions=high_risk_suppressions
        )
        
        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "sample_exploits": sample_exploits,
            "high_risk_suppressions": high_risk_suppressions,
            "total_suppressions": len(granular_diff)
        }
    
    def get_run_metadata(self, run_id: str) -> Dict[str, Any]:
        """
        Get metadata for a simulation run.
        
        Args:
            run_id: Simulation run ID
            
        Returns:
            Run metadata (type, date, scenario count, etc.)
        """
        run = self.db.query(SimulationRun).filter(
            SimulationRun.run_id == run_id
        ).first()
        
        if not run:
            return {}
        
        return {
            "run_id": run.run_id,
            "run_type": run.run_type,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "total_alerts": run.total_alerts,
            "total_transactions": run.total_transactions,
            "status": run.status
        }
