import pandas as pd
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from models import VerifiedEntity, AlertExclusionLog
from datetime import datetime
import uuid

class EventDetector:
    """Detects legitimate events in transactions with Context Awareness"""
    
    # ... keywords same as before ...
    EDUCATION_KEYWORDS = [
        'university', 'tuition', 'education', 'school', 
        'college', 'student fee', 'semester'
    ]
    LOAN_KEYWORDS = ['loan', 'emi', 'mortgage', 'repayment', 'installment', 'financing']
    FIXED_DEPOSIT_KEYWORDS = ['fixed deposit', 'fd', 'term deposit', 'investment', 'fd maturity']
    SALARY_KEYWORDS = ['salary', 'payroll', 'wages', 'compensation', 'monthly income']

    def __init__(self, db: Session):
        self.db = db

    def is_verified_entity(self, entity_name: str, entity_type: str) -> bool:
        """Check if entity is in verified whitelist"""
        if not entity_name:
            return False
            
        # Basic fuzzy match or direct match
        # In prod: use localized search or vector search
        # Here: simple ILIKE
        entity = self.db.query(VerifiedEntity).filter(
            VerifiedEntity.entity_name.ilike(f"%{entity_name}%"),
            VerifiedEntity.entity_type == entity_type,
            VerifiedEntity.is_active == True
        ).first()
        
        return entity is not None

    def detect_event_context(self, narrative: str, amount: float, beneficiary: str) -> Optional[Dict]:
        """
        Detect event type and validate context (Amount, Beneficiary).
        Returns dict with event_type and verification status.
        """
        if not narrative:
            return None
        
        narrative_lower = str(narrative).lower()
        event_type = None
        
        if any(kw in narrative_lower for kw in self.EDUCATION_KEYWORDS):
            event_type = 'education'
        elif any(kw in narrative_lower for kw in self.LOAN_KEYWORDS):
            event_type = 'loan'
        elif any(kw in narrative_lower for kw in self.FIXED_DEPOSIT_KEYWORDS):
            event_type = 'fixed_deposit'
            
        if not event_type:
            return None

        # Context Checks
        is_verified = False
        amount_reasonable = True # Default true until logic added
        
        if event_type == 'education':
            # Check verified university
            is_verified = self.is_verified_entity(beneficiary, 'University')
            # Amount check: Tuition usually < 50k
            if amount > 50000:
                amount_reasonable = False
        
        if event_type == 'loan':
            is_verified = self.is_verified_entity(beneficiary, 'FinancialInstitution')
            
        return {
            "type": event_type,
            "is_verified": is_verified,
            "amount_reasonable": amount_reasonable
        }

class SmartLayerProcessor:
    """Main smart layer orchestrator 2.0"""
    
    def __init__(self, db: Session):
        self.db = db
        self.event_detector = EventDetector(db)
    
    def _get_trigger_window_transactions(
        self,
        alert: pd.Series,
        transactions: pd.DataFrame,
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """
        Filter transactions to only those within the alert's trigger window.
        Uses alert_date and lookback period to get precise window.
        """
        customer_id = alert['customer_id']
        alert_date = pd.to_datetime(alert.get('alert_date', datetime.utcnow()))
        
        # Calculate trigger window
        window_start = alert_date - pd.Timedelta(days=lookback_days)
        window_end = alert_date
        
        # Filter to customer and date range
        trigger_txns = transactions[
            (transactions['customer_id'] == customer_id) &
            (pd.to_datetime(transactions['transaction_date']) >= window_start) &
            (pd.to_datetime(transactions['transaction_date']) <= window_end)
        ]
        
        return trigger_txns
    
    def _write_exclusion_log(
        self,
        alert_id: str,
        rule_id: str,
        exclusion_reason: str,
        risk_flags: Dict
    ):
        """Write AlertExclusionLog entry when excluding an alert"""
        try:
            log_entry = AlertExclusionLog(
                log_id=str(uuid.uuid4()),
                alert_id=alert_id,
                exclusion_timestamp=datetime.utcnow(),
                rule_id=rule_id,
                exclusion_reason=exclusion_reason,
                risk_flags=risk_flags  # Compact snapshot of risk indicators
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Failed to write exclusion log: {e}")
    
    def apply_refinements(
        self,
        alerts: pd.DataFrame,
        transactions: pd.DataFrame,
        refinement_rules: List[Dict],
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """Apply all refinement rules to alerts with context checks (VECTORIZED)"""
        
        if alerts.empty:
            return alerts
            
        if 'excluded' not in alerts.columns:
            alerts['excluded'] = False
        if 'exclusion_reason' not in alerts.columns:
            alerts['exclusion_reason'] = None
        
        # VECTORIZED APPROACH: Process all alerts at once instead of iterrows
        for rule in refinement_rules:
            rule_id = rule.get('rule_id', 'unknown')
            
            if rule['type'] == 'event_based':
                excluded_events = rule.get('excluded_events', [])
                
                # Build keyword pattern for all excluded events
                event_keywords = {
                    'education': ['tuition', 'university', 'college', 'school'],
                    'crypto': ['crypto', 'bitcoin', 'binance', 'coinbase'],
                    'loan': ['loan', 'mortgage', 'credit'],
                }
                
                # Combine all keywords for excluded events
                all_keywords = []
                for event in excluded_events:
                    all_keywords.extend(event_keywords.get(event, []))
                
                if not all_keywords:
                    continue
                
                # Vectorized: Find all transactions matching keywords
                # Optimization: Pre-compile regex
                import re
                keyword_pattern = '|'.join(map(re.escape, all_keywords)) # Escape to prevent regex injection errors
                compiled_regex = re.compile(keyword_pattern, re.IGNORECASE)
                
                matching_txns = transactions[
                    transactions['transaction_narrative'].str.contains(
                        compiled_regex, 
                        na=False,
                        regex=True
                    )
                ].copy()
                
                if matching_txns.empty:
                    continue
                
                # Vectorized: Get customer IDs with matching transactions
                customers_with_matches = set(matching_txns['customer_id'].unique())
                
                # Vectorized: Mark alerts for these customers (not yet excluded)
                mask = (
                    alerts['customer_id'].isin(customers_with_matches) &
                    (~alerts['excluded'])
                )
                
                # For alerts that match, we need to verify context
                # This part still needs row-level logic but only for matched subset
                matched_alerts = alerts[mask].copy()
                
                for idx in matched_alerts.index:
                    alert = alerts.loc[idx]
                    
                    # Get trigger window transactions
                    trigger_txns = self._get_trigger_window_transactions(
                        alert, 
                        transactions, 
                        lookback_days
                    )
                    
                    should_exclude = False
                    exclusion_reason = None
                    risk_flags = {}
                    
                    # Check transactions in trigger window
                    for _, txn in trigger_txns.iterrows():
                        narrative = txn.get('transaction_narrative')
                        amount = txn.get('transaction_amount', 0)
                        beneficiary = txn.get('beneficiary_name')
                        
                        context = self.event_detector.detect_event_context(narrative, amount, beneficiary)
                        
                        if context and context['type'] in excluded_events:
                            # Build risk flags snapshot
                            risk_flags = {
                                'event_type': context['type'],
                                'is_verified': context['is_verified'],
                                'amount_reasonable': context['amount_reasonable'],
                                'beneficiary': beneficiary,
                                'amount': float(amount)
                            }
                            
                            if context['type'] == 'education':
                                if context['is_verified'] and context['amount_reasonable']:
                                    should_exclude = True
                                    exclusion_reason = f"Verified {context['type']} transaction to {beneficiary}"
                            else:
                                should_exclude = True
                                exclusion_reason = f"Legitimate {context['type']} transaction"
                            
                            if should_exclude:
                                break
                    
                    if should_exclude:
                        alerts.at[idx, 'excluded'] = True
                        alerts.at[idx, 'exclusion_reason'] = exclusion_reason
                        
                        # Write exclusion log
                        alert_id = alert.get('alert_id')
                        if alert_id:
                            self._write_exclusion_log(
                                alert_id=alert_id,
                                rule_id=rule_id,
                                exclusion_reason=exclusion_reason,
                                risk_flags=risk_flags
                            )
        
        return alerts
