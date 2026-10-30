import os
import json
import logging
from datetime import datetime, timezone

_LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"))
LOG_FILE = os.path.join(_LOGS_DIR, "swarmflow.jsonl")
ALERT_FILE = os.path.join(_LOGS_DIR, "master_alert_queue.jsonl")

def setup_logger():
    os.makedirs(_LOGS_DIR, exist_ok=True)

class SwarmFlowLogger:
    """
    Implements Swarm Telemetry and Metadata Logging (SwarmFlow) 
    using the Agentic 5-Tuples defined in Module 3.
    """
    @staticmethod
    def log_tuple(modder_id: str, agent_id: str, target_namespace: str, model_tier: str, token_volume: int):
        setup_logger()
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        record = {
            "timestamp": timestamp,
            "modder_id": modder_id,
            "parent_agent_id": agent_id,
            "target_namespace": target_namespace,
            "model_tier": model_tier,
            "token_volume": token_volume
        }
        
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logging.error(f"[SwarmFlow] Failed to log telemetry: {e}")

    @staticmethod
    def log_intrusion_alert(modder_id: str, agent_id: str, target_namespace: str, reason: str):
        """
        Logs critical NGPF/Raugus Firewall alerts to the Master Alert Queue (MAQ) stream.
        """
        setup_logger()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        record = {
            "timestamp": timestamp,
            "alert_type": "NGPF_INTRUSION",
            "modder_id": modder_id,
            "parent_agent_id": agent_id,
            "target_namespace": target_namespace,
            "reason": reason
        }
        
        try:
            with open(ALERT_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

