# SIEM Log Exhaustion & Alert Queue Flooding Traps

## 1. The Problem: The Swarm Telemetry Flood
As Siraugga evolved to orchestrate multi-agent swarms, the volume of security events exploded. Subagents running file inspections, AST static analysis, and prompt validation emitted thousands of audit records per minute into `security/central_logger.py`.

Without strict volume controls, this firehose of data created two catastrophic failure modes:
1. **Disk Exhaustion**: Unbounded append operations to `logs/devcore_master.jsonl` consumed gigabytes of storage over prolonged sessions, eventually causing disk write errors.
2. **Alert Queue Flooding**: The in-memory Master Alert Queue (MAQ) ballooned, starving the server of RAM and freezing the WebSocket event loop.

```
+-------------------------------------------------------------+
|               Multi-Agent Swarm (10+ Subagents)             |
|          Emits: 200+ security audit events / sec            |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                     Central SIEM Logger                     |
|           Unchecked Append to devcore_master.jsonl          |
+-------------------------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
      Unbounded Disk Bloat           In-Memory Queue Lockup
     File Reaches Multiple GBs       MAQ Memory Exhaustion (OOM)
```

---

## 2. UI Asphyxiation
When the web portal attempted to render the executive dashboard (`sandbox/templates/security_dashboard.html`), it tried to parse the entire unindexed JSONL log file over WebSocket. The browser froze, the DOM crashed, and screen readers became completely unresponsive.

---

## 3. The Solution: Fixed Deque Ring Buffers & Size Rotation
To restore stability without sacrificing forensic compliance, Siraugga re-engineered the SIEM logging pipeline:
1. **Bounded Deque Ring Buffer**: The Master Alert Queue in memory was converted to a fixed-size `collections.deque(maxlen=500)`, automatically discarding older low-priority alerts while keeping recent security events.
2. **Log File Rotation**: When `devcore_master.jsonl` exceeds 10 MB, it is automatically rotated to `devcore_master.1.jsonl` and compressed, preserving only the last 5 rotations.
3. **Severity Tiering**: Only `WARN` and `CRITICAL` alerts trigger immediate WebSocket broadcasts, while routine `INFO` events are batched and written to disk asynchronously.

---

## 4. Why Order Matters in Security Telemetry
1. **Drop Low-Priority Telemetry Before High-Priority**: If the alert queue fills during an active attack, the system must drop `INFO` pings before dropping `CRITICAL` privilege violation alerts.
2. **Flush Memory Buffer Before Log Rotation**: The logger must write all pending memory chunks to the current file before rotating handles to avoid losing forensic records.
3. **Atomic File Renaming**: Renaming log files using atomic filesystem operations prevents concurrent subagent writes from failing with file lock errors.

---

## 5. Beginner Coder Q&A
**Q: What is a JSONL file?**  
A: JSON Lines (`.jsonl`) is a format where each line of a text file is a complete, valid JSON object, making it easy to stream and append events without parsing a giant array.

**Q: What is a Ring Buffer (`deque`)?**  
A: A double-ended queue with a maximum size. When full, adding a new item automatically pushes out the oldest item from the opposite end.

**Q: Does rotating logs delete old evidence?**  
A: No. Rotated logs are archived into compressed `.gz` files for compliance, protecting disk space without losing audit trails.
