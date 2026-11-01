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
    def get_model_usage(timeframe: str = "all") -> dict:
        """Aggregate logs/swarmflow.jsonl by model_tier so the telemetry dashboard
        can show per-brain usage (Claude, Gemini/agy, Ollama, local, ...).
        timeframe: '24h', '7d', or 'all'."""
        from datetime import timedelta
        setup_logger()
        now = datetime.now(timezone.utc)
        cutoff = None
        if timeframe == "24h":
            cutoff = now - timedelta(hours=24)
        elif timeframe == "7d":
            cutoff = now - timedelta(days=7)

        models = {}
        total_tokens = 0
        total_requests = 0
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    ts = rec.get("timestamp")
                    if cutoff and ts:
                        try:
                            if datetime.fromisoformat(ts) < cutoff:
                                continue
                        except Exception:
                            pass
                    tier = (rec.get("model_tier") or "unknown").strip() or "unknown"
                    vol = int(rec.get("token_volume") or 0)
                    m = models.setdefault(tier, {
                        "model_tier": tier,
                        "requests": 0,
                        "tokens": 0,
                        "is_claude": "claude" in tier.lower(),
                    })
                    m["requests"] += 1
                    m["tokens"] += vol
                    total_tokens += vol
                    total_requests += 1
        except FileNotFoundError:
            pass

        rows = sorted(models.values(), key=lambda x: -x["tokens"])
        claude_tokens = sum(m["tokens"] for m in rows if m["is_claude"])
        claude_requests = sum(m["requests"] for m in rows if m["is_claude"])
        return {
            "timeframe": timeframe,
            "models": rows,
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "claude_tokens": claude_tokens,
            "claude_requests": claude_requests,
        }

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

