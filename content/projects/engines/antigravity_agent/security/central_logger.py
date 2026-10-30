import logging
import json
import os
import sys
import warnings
from datetime import datetime, timezone

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "devcore_master.jsonl")

class SIEMJsonFormatter(logging.Formatter):
    def format(self, record):
        if record.name.startswith("httpx") or record.name.startswith("httpcore"):
            return ""
            
        event_category = "SYSTEM"
        msg_lower = record.getMessage().lower()
        
        if record.levelname in ["CRITICAL", "FATAL"] or record.exc_info:
            event_category = "FAULT"
        elif "startup" in msg_lower or "initialized" in msg_lower or "boot" in msg_lower:
            event_category = "STARTUP"
        elif "agent" in record.name or "swarm" in record.name or "tool" in msg_lower or "token" in msg_lower:
            event_category = "AGENTIC"
        elif "login" in msg_lower or "token" in msg_lower or "auth" in msg_lower or "role" in msg_lower:
            event_category = "AUTH"
        elif any(
            kw in record.name or kw in msg_lower
            for kw in (
                "security",
                "intrusion",
                "raugus",
                "unauthorized",
                "exfiltration",
                "sensitive",
                "vault",
                "pii",
                "verbatim",
                "violation",
            )
        ):
            event_category = "SECURITY_AUDIT"
        elif record.levelname == "WARNING":
            event_category = "WARNING"
        elif "quart" in record.name or "hypercorn" in record.name or "websocket" in msg_lower:
            event_category = "NETWORK"

            
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "category": event_category,
            "logger": record.name,
            "module": getattr(record, "custom_module", None) or record.module,
            "message": record.getMessage()
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Unhandled system fault (Crash)", exc_info=(exc_type, exc_value, exc_traceback))

def handle_warnings(message, category, filename, lineno, file=None, line=None):
    logging.warning(f"{category.__name__}: {message} ({filename}:{lineno})")

def log_siem_event(level: str, message: str, module_name: str = "raugus_vault", logger_name: str = "security.raugus"):
    """
    Appends a structured SIEM JSON event directly to devcore_master.jsonl
    without attaching stdout/stderr StreamHandlers (safe for PreToolUse hooks and CLI brokers).
    """
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        lvl = getattr(logging, level.upper(), logging.INFO)
        record = logging.LogRecord(
            name=logger_name,
            level=lvl,
            pathname=module_name,
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.custom_module = module_name
        formatted = SIEMJsonFormatter().format(record)
        if formatted:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
    except Exception:
        pass

def init_central_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(SIEMJsonFormatter())
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(SIEMJsonFormatter())
    logger.addHandler(console_handler)

    sys.excepthook = handle_unhandled_exception
    
    warnings.showwarning = handle_warnings

    logging.info("Central SIEM Logger Initialized. Swarm Onion architecture is active.")

if __name__ == "__main__":
    init_central_logging()
    logging.info("Testing central SIEM logger setup.")
