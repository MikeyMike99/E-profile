# Central SIEM Logger & Master Alert Queue Source Evidence

## 1. Architectural Role & File Location
This document contains source code evidence from `security/central_logger.py`. It details the central telemetry engine that aggregates security events across multi-agent swarms, rotates disk logs, and manages the in-memory Master Alert Queue (MAQ).

---

## 2. Event Model & Severity Enumeration Evidence
Security events follow a strict, standardized schema with cryptographic timestamps:

```python
# security/central_logger.py: Event schema definition
from enum import Enum
import time
import json
import os
from collections import deque

class SecurityLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARN = 30
    CRITICAL = 40

class SecurityEvent:
    def __init__(self, event_type: str, level: SecurityLevel, actor: str, details: dict):
        self.timestamp = time.time()
        self.iso_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self.timestamp))
        self.event_type = event_type
        self.level = level.name
        self.actor = actor
        self.details = details

    def to_dict(self) -> dict:
        return {
            "iso_time": self.iso_time,
            "timestamp": self.timestamp,
            "level": self.level,
            "event_type": self.event_type,
            "actor": self.actor,
            "details": self.details
        }
```

---

## 3. Log Rotation & Master Alert Queue (MAQ) Evidence
The logger enforces file rotation when `devcore_master.jsonl` hits 10 MB and maintains a bounded memory queue:

```python
# security/central_logger.py: Telemetry engine & rotation
LOG_FILE = "./logs/devcore_master.jsonl"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB limit
MAX_BACKUPS = 5

class CentralSIEMLogger:
    def __init__(self):
        os.makedirs("./logs", exist_ok=True)
        # Bounded ring buffer prevents memory starvation
        self.alert_queue = deque(maxlen=1000)

    def _rotate_if_needed(self):
        """Rotates the log file if it exceeds MAX_LOG_SIZE."""
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= MAX_LOG_SIZE:
            for i in range(MAX_BACKUPS - 1, 0, -1):
                s = f"{LOG_FILE}.{i}"
                d = f"{LOG_FILE}.{i+1}"
                if os.path.exists(s):
                    os.rename(s, d)
            os.rename(LOG_FILE, f"{LOG_FILE}.1")

    def record_event(self, event: SecurityEvent):
        """Appends event to JSONL and updates the memory alert queue."""
        data = event.to_dict()
        line = json.dumps(data) + "\n"
        
        self._rotate_if_needed()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)

        # High priority alerts enter the broadcast queue
        if event.level in ["WARN", "CRITICAL"]:
            self.alert_queue.append(data)
```

---

## 4. Why Order Matters in Telemetry Logging
1. **Check Rotation Before File Open**: Checking file size before opening in append mode ensures bloated files are rotated before new bytes are written.
2. **Write Disk Before Memory Notification**: Guaranteeing the event is persisted on disk prevents losing intrusion records if an out-of-memory error crashes the server during memory queue dispatch.
3. **UTC ISO Timestamps**: Using `time.gmtime()` prevents timezone confusion when developers in different regions analyze forensic records.

---

## 5. Beginner Coder Q&A
**Q: Why use `deque(maxlen=1000)` instead of a Python `list`?**  
A: A list grows infinitely until memory is exhausted. A `deque` automatically discards the oldest element once it reaches 1,000 items with O(1) performance.

**Q: What is the benefit of JSONL for security logs?**  
A: If a system crashes mid-write, only the last line is truncated. The previous 100,000 log lines remain valid JSON without corrupting an entire array bracket.

**Q: How does the web UI display these logs?**  
A: The Quart server serves `GET /api/security/alerts`, which streams the latest items from `self.alert_queue` directly into `security_dashboard.html`.
