from typing import List, Dict, Optional, Set
from django.db import transaction
from django.db.models import Q
from simulation.models import AlertExclusionLog, Transaction, VerifiedEntity
from django.utils import timezone
import uuid
import logging
import re

logger = logging.getLogger(__name__)

class EventDetector:
    """Detects legitimate events in transactions with matching logic (Django Native)"""
    
    EDUCATION_KEYWORDS = [
        'university', 'tuition', 'education', 'school', 
        'college', 'student fee', 'semester'
    ]
    LOAN_KEYWORDS = ['loan', 'emi', 'mortgage', 'repayment', 'installment', 'financing']
    FIXED_DEPOSIT_KEYWORDS = ['fixed deposit', 'fd', 'term deposit', 'investment', 'fd maturity']
    
    def is_verified_entity(self, entity_name: str, entity_type: str) -> bool:
        """Check if entity is in verified whitelist using ORM"""
        if not entity_name:
            return False
        
        return VerifiedEntity.objects.filter(
            entity_name__icontains=entity_name,
            entity_type=entity_type,
            is_active=True
        ).exists()

    def detect_event_context(self, narrative: str, amount: float, beneficiary: str) -> Optional[Dict]:
        """Detect event type and validate context."""
        if not narrative:
            return None
        
        narrative_lower = narrative.lower()
        event_type = None
        
        if any(kw in narrative_lower for kw in self.EDUCATION_KEYWORDS):
            event_type = 'education'
        elif any(kw in narrative_lower for kw in self.LOAN_KEYWORDS):
            event_type = 'loan'
        elif any(kw in narrative_lower for kw in self.FIXED_DEPOSIT_KEYWORDS):
            event_type = 'fixed_deposit'
            
        if not event_type:
            return None

        is_verified = False
        amount_reasonable = True
        
        if event_type == 'education':
            is_verified = self.is_verified_entity(beneficiary, 'University')
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
    """Main smart layer orchestrator (Django Native)"""
    
    def __init__(self):
        self.event_detector = EventDetector()
    
    def apply_refinements(self, alerts: List[Dict], user_id: str, refinement_rules: List[Dict]) -> List[Dict]:
        """
        Apply refinement rules to alerts list.
        Iterates through alerts, checks linked transactions via ORM, and marks exclusions.
        """
        if not alerts:
            return []

        for rule in refinement_rules:
            if rule.get('type') != 'event_based':
                continue

            excluded_events = rule.get('excluded_events', [])
            if not excluded_events:
                continue

            for alert in alerts:
                if alert.get('excluded'):
                    continue

                # Fetch trigger transactions from DB for this alert context
                # Assuming alert dict has identifying info or we use passed context
                # For pure ORM approach, we query transactions for the customer around the alert time
                
                customer_id = alert['customer_id']
                alert_date = alert['alert_date']
                
                # Lookback 30 days
                start_date = alert_date - timezone.timedelta(days=30)
                
                # Fetch potential matching transactions
                # Optimization: Filter by keywords in DB query if possible, or fetch small window
                txns = Transaction.objects.filter(
                    customer_id=customer_id,
                    created_at__range=(start_date, alert_date)
                )

                should_exclude = False
                exclusion_reason = None
                risk_flags = {}

                for txn in txns:
                    # Parse Data
                    narrative = txn.raw_data_dict.get('transaction_narrative', '')
                    amount = float(txn.raw_data_dict.get('transaction_amount', 0))
                    beneficiary = txn.raw_data_dict.get('beneficiary_name', '')

                    context = self.event_detector.detect_event_context(narrative, amount, beneficiary)
                    
                    if context and context['type'] in excluded_events:
                        risk_flags = {
                            'event_type': context['type'],
                            'amount': amount,
                            'beneficiary': beneficiary
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
                    alert['excluded'] = True
                    alert['exclusion_reason'] = exclusion_reason
                    
                    # Log exclusion
                    self._write_exclusion_log(
                        alert_id=alert.get('alert_id'),
                        rule_id=rule.get('rule_id'),
                        exclusion_reason=exclusion_reason,
                        risk_flags=risk_flags
                    )
        
        return alerts

    def _write_exclusion_log(self, alert_id, rule_id, exclusion_reason, risk_flags):
        try:
            AlertExclusionLog.objects.create(
                log_id=str(uuid.uuid4()),
                alert_id=alert_id,
                rule_id=rule_id,
                exclusion_reason=exclusion_reason,
                risk_flags=risk_flags,
                exclusion_timestamp=timezone.now()
            )
        except Exception as e:
            logger.error(f"Failed to write exclusion log: {e}")
