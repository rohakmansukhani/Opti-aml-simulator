from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy.orm import Session
from models import Alert, Customer, Transaction, VerifiedEntity, CustomerRiskProfile
import random
import logging

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Risk Engine 2.0: Advanced Security & Gap Analysis Module.
    
    This engine is responsible for "Red Teaming" proposed rule refinements.
    It analyzes alerts that would be DROPPED by a new rule and calculates a
    'Risk Score' to determine if safe, legitimate alerts are being suppressed.
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

    def __init__(self, db: Session):
        self.db = db

    def analyze_risk_gap(self, refinements: List[Dict], baseline_run_id: str) -> Dict[str, Any]:
        """
        Analyzes the security gap introduced by proposed refinements.

        Args:
            refinements (List[Dict]): A list of refinement rules (e.g., "Exclude Education").
            baseline_run_id (str): The ID of the baseline simulation to compare against.

        Returns:
            Dict containing:
            - risk_score (0-100)
            - risk_level (SAFE, CAUTION, DANGEROUS, CRITICAL)
            - sample_exploits (List of potential exploit vectors)
        """
        
        # 1. Fetch Baseline Alerts
        # We need to know what alerts existed BEFORE the refinement to see what gets dropped.
        baseline_alerts_query = self.db.query(Alert).filter(Alert.run_id == baseline_run_id)
        if baseline_alerts_query.count() == 0:
            return {
                "risk_score": 0, 
                "risk_level": "SAFE", 
                "explanations": ["No baseline alerts to analyze"], 
                "excluded_count": 0, 
                "sample_exploits": []
            }

        baseline_alerts_df = pd.read_sql(baseline_alerts_query.statement, self.db.bind)
        
        excluded_alerts = []
        risk_score_total = 0.0
        
        # 2. Simulate Refinement Impact
        for rule in refinements:
            if rule['type'] == 'event_based':
                excluded_events = rule.get('excluded_events', [])
                
                for _, alert in baseline_alerts_df.iterrows():
                    narrative = alert.get('alert_description', '').lower()
                    
                    # Normalize trigger details
                    details = alert.get('trigger_details', {})
                    if isinstance(details, str):
                        import json
                        try:
                            details = json.loads(details)
                        except:
                            details = {}
                    
                    alert_data = alert.to_dict()
                    alert_data['trigger_details'] = details
                    
                    is_excluded = False
                    exclusion_reason = ""
                    
                    # Check if this alert would be caught by the refinement rule
                    if 'education' in excluded_events and ('tuition' in narrative or 'university' in narrative):
                        is_excluded = True
                        exclusion_reason = "Education Exclusion"
                    
                    if is_excluded:
                        # 3. Calculate Risk of Exclusion
                        # If we exclude this, are we opening a loophole?
                        alert_risk = self._calculate_alert_risk(alert_data, exclusion_reason)
                        risk_score_total += alert_risk['score']
                        excluded_alerts.append({
                            "alert_id": str(alert['alert_id']),
                            "reason": exclusion_reason,
                            "risk_analysis": alert_risk
                        })
                        
        # 4. Normalize Score
        # Cap at 100. Logic: Summing individual risks can go high, we need a bounded score.
        normalized_score = min(risk_score_total, 100.0)
        
        risk_level = "SAFE"
        if normalized_score > 60:
            risk_level = "CRITICAL"
        elif normalized_score > 30:
            risk_level = "DANGEROUS"
        elif normalized_score > 0:
            risk_level = "CAUTION"

        return {
            "risk_score": round(normalized_score, 1),
            "risk_level": risk_level,
            "excluded_count": len(excluded_alerts),
            "sample_exploits": self._generate_sample_exploits(excluded_alerts)
        }
    
    def analyze_excluded_alerts(self, excluded_alerts: List[Dict]) -> Dict[str, Any]:
        """
        Analyzes actual excluded alerts from a simulation run.
        
        Args:
            excluded_alerts (List[Dict]): List of alerts that were excluded
            
        Returns:
            Dict containing:
            - risk_score (0-100)
            - risk_level ('SAFE' | 'CAUTION' | 'DANGEROUS' | 'CRITICAL')
            - sample_exploits (List of potential exploit vectors)
        """
        if not excluded_alerts:
            return {
                "risk_score": 0.0,
                "risk_level": "SAFE",
                "excluded_count": 0,
                "sample_exploits": []
            }
        
        risk_score_total = 0.0
        analyzed_alerts = []
        
        for alert in excluded_alerts:
            exclusion_reason = alert.get('exclusion_reason', 'Unknown')
            alert_risk = self._calculate_alert_risk(alert, exclusion_reason)
            risk_score_total += alert_risk['score']
            
            analyzed_alerts.append({
                "alert_id": str(alert.get('alert_id', '')),
                "reason": exclusion_reason,
                "risk_analysis": alert_risk
            })
        
        # Normalize score (cap at 100)
        normalized_score = min(risk_score_total, 100.0)
        
        # Determine risk level
        risk_level = "SAFE"
        if normalized_score > 60:
            risk_level = "CRITICAL"
        elif normalized_score > 30:
            risk_level = "DANGEROUS"
        elif normalized_score > 0:
            risk_level = "CAUTION"
        
        return {
            "risk_score": round(normalized_score, 1),
            "risk_level": risk_level,
            "excluded_count": len(excluded_alerts),
            "sample_exploits": self._generate_sample_exploits(analyzed_alerts)
        }

    def _calculate_alert_risk(self, alert_data: Dict[str, Any], exclusion_reason: str) -> Dict[str, Any]:
        """
        Scoring Engine for a single excluded alert.
        
        Factors:
        1. Amount: Higher amount = Higher Risk (if excluded).
        2. Beneficiary: Unverified beneficiaries typically indicate fraud.
        3. Customer: PEPs or those with Adverse Media are high risk.
        """
        score = 0.0
        factors = []
        
        # Factor A: Amount Reasonability
        details = alert_data.get('trigger_details', {})
        amount_str = details.get('aggregated_value', details.get('transaction_amount', '0'))
        try:
            amount = float(amount_str)
        except:
            amount = 0.0

        reason_lower = exclusion_reason.lower()
        
        if "education" in reason_lower:
            # Tuition fees > 50k are suspicious
            if amount > 50000:
                score += 15.0
                factors.append(f"High amount for Education: {amount}")
        elif "crypto" in reason_lower:
             # Crypto > 10k is suspicious
            if amount > 10000:
                score += 20.0
                factors.append(f"High amount for Crypto: {amount}")

        # Factor B: Beneficiary Verification
        ben_name = details.get('beneficiary_name')
        if ben_name:
            expected_type = None
            if "education" in reason_lower: expected_type = 'University'
            elif "crypto" in reason_lower: expected_type = 'CryptoExchange'
            
            if expected_type:
                # Check Database for Whitelist
                verified = self.db.query(VerifiedEntity).filter(
                    VerifiedEntity.entity_name.ilike(f"%{ben_name}%"),
                    VerifiedEntity.entity_type == expected_type,
                    VerifiedEntity.is_active == True
                ).first()
                
                if not verified:
                    score += 25.0
                    factors.append(f"Unverified {expected_type} beneficiary: {ben_name}")
                else:
                    score -= 5.0 # Trusted entity reduces risk
            
        # Factor C: Customer Risk Profile
        customer_id = alert_data.get('customer_id')
        if customer_id:
            profile = self.db.query(CustomerRiskProfile).filter(CustomerRiskProfile.customer_id == customer_id).first()
            if profile:
                if profile.is_pep:
                    score += 25.0
                    factors.append("Customer is PEP")
                if profile.has_adverse_media:
                    score += 20.0
                    factors.append("Adverse Media found")
                if profile.high_risk_occupation:
                    score += 10.0
                    factors.append("High Risk Occupation")
                if profile.previous_sar_count > 0:
                    score += (10.0 * profile.previous_sar_count)
                    factors.append(f"{profile.previous_sar_count} Previous SARs")

        return {"score": max(0.0, score), "factors": factors}

    def _generate_sample_exploits(self, excluded_alerts: List[Dict]) -> List[Dict]:
        """
        Translates raw technical risk data into "Exploit Stories" for the UI.
        e.g., "Attacker could structure funds using 'Education' payments."
        """
        # Sort by risk score descending
        sorted_alerts = sorted(excluded_alerts, key=lambda x: x['risk_analysis']['score'], reverse=True)
        
        exploits = []
        for item in sorted_alerts[:3]: # Take Top 3 Riskiest exclusions
            factors = item['risk_analysis']['factors']
            exploits.append({
                "title": f"Exploit: {factors[0] if factors else 'Generic Gap'}",
                "method": f"Excluded by rule '{item['reason']}'. {', '.join(factors)}",
                "volume_risk": "High"
            })
        return exploits
