from sqlalchemy.orm import Session
from models import Alert, SimulationRun
import pandas as pd
from typing import Dict, Any

class ComparisonEngine:
    """
    Compares two simulation runs (Baseline vs Refined) to quantify improvement.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def compare(self, baseline_run_id: str, refined_run_id: str) -> Dict[str, Any]:
        """
        Compare two runs and return diff stats.
        """
        # Load alerts from both runs
        baseline_alerts = self.db.query(Alert).filter(
            Alert.run_id == baseline_run_id
        ).all()
        
        refined_alerts = self.db.query(Alert).filter(
            Alert.run_id == refined_run_id
        ).all()
        
        # Simple diff
        baseline_count = len(baseline_alerts)
        refined_count = len(refined_alerts)
        
        reduction = baseline_count - refined_count
        pct = (reduction / baseline_count * 100) if baseline_count > 0 else 0
        
        # Granular Diff Logic
        # Identify which alerts were removed (True Positives vs False Positives logic requires ground truth, 
        # so here we just track net reduction)
        
        removed_ids = set([a.customer_id for a in baseline_alerts]) - set([a.customer_id for a in refined_alerts])
        
        return {
            "summary": {
                "baseline_alerts": baseline_count,
                "refined_alerts": refined_count,
                "net_change": reduction,
                "percent_reduction": round(pct, 2)
            },
            "granular_diff": [
                {"customer_id": cid, "status": "removed"} for cid in list(removed_ids)[:50] # Limit sample
            ],
            "risk_analysis": {
                "risk_score": 0, # Placeholder for real risk scoring model
                "risk_level": "LOW",
                "sample_exploits": []
            }
        }
