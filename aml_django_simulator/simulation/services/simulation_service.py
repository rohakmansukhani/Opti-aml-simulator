import uuid
from typing import List, Optional
from django.db import transaction
from django.utils import timezone
from simulation.models import SimulationRun, Alert, AlertTransaction, ScenarioConfig, Transaction
from simulation.engines.universal_engine import UniversalScenarioEngine
import logging

logger = logging.getLogger(__name__)

class SimulationService:
    """
    Manages the lifecycle of AML simulation execution (Django Native).
    """

    def __init__(self):
        self.engine = UniversalScenarioEngine()

    def create_run(self, run_type: str, scenarios: List[str], user_id: str = None, upload_id: str = None) -> SimulationRun:
        run = SimulationRun.objects.create(
            run_id=str(uuid.uuid4()),
            user_id=user_id,
            upload_id=upload_id,
            run_type=run_type,
            scenarios_run=scenarios or [],
            status="pending",
            created_at=timezone.now()
        )
        return run

    def execute_run(self, run_id: str, user_id: str):
        """
        Execute complete simulation run.
        """
        run = SimulationRun.objects.get(run_id=run_id)
        run.status = "running"
        run.save()

        try:
            all_alerts = []
            
            for scenario_id in run.scenarios_run:
                # Execute engine
                alerts = self.engine.execute(scenario_id, run_id, user_id)
                all_alerts.extend(alerts)

            # Persist Alerts
            self._save_results(run, all_alerts)

            # Complete
            run.status = "completed"
            run.total_alerts = len(all_alerts)
            run.completed_at = timezone.now()
            run.progress_percentage = 100
            run.save()

        except Exception as e:
            logger.error(f"Run {run_id} failed: {e}", exc_info=True)
            run.status = "failed"
            run.metadata_info = {"error": str(e)}
            run.save()

    @transaction.atomic
    def _save_results(self, run: SimulationRun, alerts_data: List[dict]):
        """Save alerts and link transactions"""
        alert_objs = []
        txn_links = []
        
        for data in alerts_data:
            # Merge alert_metadata and enrichment_data into trigger_details
            trigger_details = data.get('trigger_details', {})
            if data.get('alert_metadata'):
                trigger_details['alert_metadata'] = data['alert_metadata']
            if data.get('enrichment_data'):
                trigger_details['enrichment_data'] = data['enrichment_data']

            alert = Alert(
                alert_id=data['alert_id'],
                customer_id=data['customer_id'],
                scenario_id=data['scenario_id'],
                scenario_name=data['scenario_name'],
                simulation_run=run,
                alert_date=data['alert_date'],
                risk_score=data['risk_score'],
                risk_classification=data.get('risk_classification', 'MEDIUM'),
                trigger_details=trigger_details,
                trigger_reason=data.get('trigger_reason'),
                excluded=data.get('excluded', False),
                exclusion_reason=data.get('exclusion_reason')
            )
            alert_objs.append(alert)
            
        Alert.objects.bulk_create(alert_objs)

        # Link transactions for traceability
        alert_txn_objs = []
        for data in alerts_data:
            try:
                alert_instance = Alert.objects.get(alert_id=data['alert_id'])
                for txn_id in data.get('involved_transactions', []):
                    try:
                        txn_instance = Transaction.objects.get(transaction_id=txn_id)
                        alert_txn_objs.append(AlertTransaction(
                            alert=alert_instance,
                            transaction=txn_instance,
                            upload=run.upload
                        ))
                    except Transaction.DoesNotExist:
                        continue
            except Alert.DoesNotExist:
                continue
        
        if alert_txn_objs:
            AlertTransaction.objects.bulk_create(alert_txn_objs)
