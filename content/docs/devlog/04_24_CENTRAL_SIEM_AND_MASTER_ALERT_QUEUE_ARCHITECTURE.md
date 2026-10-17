[//]: # (DOC_ID: SIRA-DOC-04_24 | VERSION: v1.0 | SCOPE: Siraugga / DevCore Framework)

# Central SIEM & Master Alert Queue Architecture

## 1. Architectural Concept & Core Objective
[//]: # (SECTION_ID: SIRA-DOC-04_24-SEC-1)
In an autonomous development ecosystem where multiple subagents and background workers execute concurrently, maintaining complete visibility over security boundaries is essential. Without centralized telemetry, privilege escalation attempts, path traversal attacks, and quota breaches occur silently.

The Central SIEM (Security Information and Event Management) Architecture establishes a dual-layer telemetry pipeline: an append-only, rotating JSONL disk archive for forensic audits, and an in-memory Master Alert Queue (MAQ) ring buffer that drives live dashboard visualizations and WebSocket broadcasts.

```
+-------------------------------------------------------------+
|              Multi-Agent Telemetry Producers                |
|        (Security Manager, VFS Resolver, Agent Swarms)       |
+-------------------------------------------------------------+
                              |
                     Standard SecurityEvent
                              |
                              v
+-------------------------------------------------------------+
|                 Central SIEM Logger (Singleton)             |
+-------------------------------------------------------------+
          |                                        |
          | Persistent Disk Channel                | In-Memory Queue Channel
          v                                        v
+-----------------------+              +----------------------+
| devcore_master.jsonl  |              | Master Alert Queue   |
| - Rotating at 10 MB   |              | - deque(maxlen=1000) |
| - Retains 5 Backups   |              | - Real-time WS Push  |
+-----------------------+              +----------------------+
                                                   |
                                                   v
                                       +----------------------+
                                       | Executive Dashboard  |
                                       | security_dashboard   |
                                       +----------------------+
```

---

## 2. Event Classification & Priority Routing
[//]: # (SECTION_ID: SIRA-DOC-04_24-SEC-2)
The SIEM defines four standardized security event tiers:
1. **DEBUG (10)**: Low-level file opens, AST node parses, and internal loopback pings. Written to disk only; suppressed from memory queue.
2. **INFO (20)**: User logins, project switches, and successful tool completions. Persisted to disk; batched for dashboard view.
3. **WARN (30)**: Quota rate limits, model fallback shifts, and single failed token attempts. Pushed to MAQ and broadcast to UI banner.
4. **CRITICAL (40)**: Path traversal attempts (`../../`), unauthorized tier writes, and brute-force lockouts. Immediately triggers high-priority screen reader alerts and IP bans.

---

## 3. Storage Bounding and Memory Protection
[//]: # (SECTION_ID: SIRA-DOC-04_24-SEC-3)
To prevent runaway disk bloat:
- **Disk Rotation**: The logger evaluates file size before every append operation. Once `devcore_master.jsonl` hits 10 MB, it shifts through numeric generations (`.1` through `.5`), discarding the oldest generation.
- **Memory Ceiling**: The MAQ relies on `collections.deque(maxlen=1000)`. Adding new alerts automatically drops older ones, guaranteeing server RAM consumption never exceeds a few hundred kilobytes.

---

## 4. Why Order Matters in SIEM Telemetry
[//]: # (SECTION_ID: SIRA-DOC-04_24-SEC-4)
1. **Commit to Disk Before Memory Dispatch**: Writing to the append-only log file before broadcasting to WebSockets ensures that network disconnects never erase forensic incident records.
2. **Rotate File Before Handle Re-Acquisition**: Renaming existing files to `.1` before opening a new file ensures continuous append operations without permission locking.
3. **Record Timestamps at Event Creation**: Using monotonic clock timestamps when the event occurs (rather than when it is written) preserves the true chronological order of distributed swarm actions.

---

## 5. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-DOC-04_24-SEC-5)
**Q: What does SIEM stand for?**  
A: Security Information and Event Management—a central hub that collects and analyzes security records from different parts of a software ecosystem.

**Q: Can a rogue subagent tamper with the SIEM log?**  
A: No! The SIEM log files are located in `logs/`, which is classified as `TIER_ADMIN_LOG`. Non-admin subagents have zero write access to these paths under the RBAC engine.

**Q: How does `security_dashboard.html` update in real time?**  
A: It connects to the Quart WebSocket stream and listens for events with `type: "security_alert"`, dynamically appending new rows to the incident table.
