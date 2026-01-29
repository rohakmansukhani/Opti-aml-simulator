import logging
import json
from typing import List, Dict, Any, Optional
from django.db.models import Q, Sum, Count, F
from django.utils import timezone
from simulation.models import Alert, Customer, Transaction, ScenarioConfig

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Risk Engine 2.0: Advanced Security & Gap Analysis Module (Django Native).
    
    This engine is responsible for "Red Teaming" proposed rule refinements.
    It analyzes alerts that would be DROPPED by a new rule and calculates a
    'Risk Score' to determine if safe, legitimate alerts are being suppressed.
    
    Optimization: Removed Pandas dependency for lower memory footprint and pure ORM usage.
    """

    ML_SCENARIOS = {
        "structuring": {
            "name": "Structuring / Smurfing",
            "risk_level": "HIGH",
            "indicators": ["small_amount", "high_frequency"],
            "base_coverage": 0.95
        },
        "education_fraud": {
            "name": "Education / Tuition Fraud",
            "risk_level": "HIGH",
            "indicators": ["education_keywords", "unverified_beneficiary"],
            "base_coverage": 0.85
        },
        "loan_circularity": {
            "name": "Loan / FD Circularity",
            "risk_level": "MEDIUM",
            "indicators": ["loan_keywords", "fd_keywords", "circular_pattern"],
            "base_coverage": 0.80
        }
    }

    def analyze_risk_gap(self, refinements: List[Dict], baseline_run_id: str) -> Dict[str, Any]:
        """
        Analyzes the security gap introduced by proposed refinements using Django ORM.
        """
        # 1. Fetch Baseline Alerts
        # Using iterator() to handle large datasets memory-efficiently
        baseline_alerts = Alert.objects.filter(simulation_run_id=baseline_run_id).iterator()
        
        # Check if any exist (efficient count)
        if not Alert.objects.filter(simulation_run_id=baseline_run_id).exists():
            return {
                "risk_score": 0, 
                "risk_level": "SAFE", 
                "explanations": ["No baseline alerts to analyze"], 
                "excluded_count": 0, 
                "sample_exploits": []
            }

        excluded_alerts_data = []
        risk_score_total = 0.0
        
        # 2. Simulate Refinement Impact (Stream processing)
        for alert in baseline_alerts:
            # Safely parse JSON details
            trigger_details = alert.trigger_details or {}
            if isinstance(trigger_details, str):
                try: 
                    trigger_details = json.loads(trigger_details)
                except json.JSONDecodeError: 
                    trigger_details = {}

            narrative = (alert.scenario_description or "").lower()
            
            # Apply Rules
            for rule in refinements:
                if rule.get('type') == 'event_based':
                    excluded_events = rule.get('excluded_events', [])
                    
                    is_excluded = False
                    exclusion_reason = ""
                    
                    # Logic: Check if alert narrative matches exclusion criteria
                    if 'education' in excluded_events and ('tuition' in narrative or 'university' in narrative):
                        is_excluded = True
                        exclusion_reason = "Education Exclusion"
                    
                    if is_excluded:
                        # 3. Calculate Risk of Exclusion
                        risk_result = self._calculate_alert_risk(alert, trigger_details, exclusion_reason)
                        risk_score_total += risk_result['score']
                        
                        excluded_alerts_data.append({
                            "alert_id": str(alert.alert_id),
                            "reason": exclusion_reason,
                            "risk_analysis": risk_result
                        })
                        # Break rule loop if excluded (one exclusion is enough)
                        break
                        
        # 4. Normalize Score (Cap at 100)
        normalized_score = min(risk_score_total, 100.0)
        
        risk_level = self._get_risk_level(normalized_score)

        return {
            "risk_score": round(normalized_score, 1),
            "risk_level": risk_level,
            "excluded_count": len(excluded_alerts_data),
            "sample_exploits": self._generate_sample_exploits(excluded_alerts_data)
        }

    def _calculate_alert_risk(self, alert: Alert, details: Dict, exclusion_reason: str) -> Dict[str, Any]:
        """
        Scoring Engine for a single excluded alert.
        """
        score = 0.0
        factors = []
        
        # Factor A: Amount Reasonability
        # Handle decimal conversion safely
        try:
            amt_val = details.get('aggregated_value') or details.get('transaction_amount') or 0
            amount = float(amt_val)
        except (ValueError, TypeError):
            amount = 0.0

        reason_lower = exclusion_reason.lower()
        
        if "education" in reason_lower:
            if amount > 50000:
                score += 15.0
                factors.append(f"High amount for Education: {amount:,.2f}")
        elif "crypto" in reason_lower:
            if amount > 10000:
                score += 20.0
                factors.append(f"High amount for Crypto: {amount:,.2f}")

        # Factor B: Beneficiary Verification
        ben_name = details.get('beneficiary_name')
        if ben_name:
            # Optimized Logic: In a real system, we would query a 'VerifiedEntity' model here.
            # For this simulator without that strict model yet, we imply risk if it looks generic/suspicious.
            # (Placeholder for future VerifiedEntity lookup)
            pass

        # Factor C: Customer Profile (Using Django Relations)
        # Assuming alert.customer exists. 
        # Since we removed CustomerRiskProfile in the pure port or need to access raw_data:
        if alert.customer:
            cust_raw = alert.customer.raw_data
            if isinstance(cust_raw, str):
                try: cust_raw = json.loads(cust_raw)
                except: cust_raw = {}
                
            # Check Risk Attributes
            if cust_raw.get('is_pep') or cust_raw.get('pep_flag'):
                score += 25.0
                factors.append("Customer is PEP")
            if cust_raw.get('adverse_media'):
                score += 20.0
                factors.append("Adverse Media found")
            if str(cust_raw.get('risk_rating')).upper() == 'HIGH':
                score += 10.0
                factors.append("High Risk Customer")

        return {"score": max(0.0, score), "factors": factors}

    def _generate_sample_exploits(self, excluded_alerts: List[Dict]) -> List[Dict]:
        """
        Translates raw technical risk data into 'Exploit Stories'.
        """
        # Sort by risk score descending
        sorted_alerts = sorted(excluded_alerts, key=lambda x: x['risk_analysis']['score'], reverse=True)
        
        exploits = []
        for item in sorted_alerts[:3]: # Top 3
            factors = item['risk_analysis']['factors']
            exploits.append({
                "title": f"Exploit: {factors[0] if factors else 'Generic Gap'}",
                "method": f"Excluded by rule '{item['reason']}'. {', '.join(factors)}",
                "volume_risk": "High"
            })
        return exploits

    def _get_risk_level(self, score: float) -> str:
        if score > 60: return "CRITICAL"
        if score > 30: return "DANGEROUS"
        if score > 0: return "CAUTION"
        return "SAFE"
