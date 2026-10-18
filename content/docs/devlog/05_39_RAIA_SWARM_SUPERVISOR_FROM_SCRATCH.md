[//]: # (DOC_ID: SIRA-ARCH-05_39 | VERSION: v1.0 | SCOPE: ARCH)

# Pillar 05.39: From-Scratch Creation Guide: RAIA Swarm Supervisor & Loop Suppressor

[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-1)
## Overview & Beginner Context
[//]: # (SECTION_ID: SIRA-DOC-05_39-SEC-1)
This guide teaches you how to write an autonomous multi-agent supervisor in Python from scratch. It implements the **Semantic Tree Protocol (STP)** to prevent conversational loops and manages an N+1 standby array of worker agents (**RAIA**).

---

[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-1)
## 1. Line-by-Line Construction
[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-2)

### Block 1: The STP Loop Detector (Lines 1–30)
[//]: # (SECTION_ID: SIRA-DOC-05_39-SEC-2)
```python
import hashlib
import time

class STPController:
    """Semantic Tree Protocol: Intercepts and breaks inter-agent loops."""
    def __init__(self, max_hops=4):
        self.max_hops = max_hops
        self.seen_hashes = set()
        self.hop_counter = 0

    def evaluate_message(self, sender: str, recipient: str, text: str) -> bool:
        """Returns True if message is allowed; False if loop detected."""
        self.hop_counter += 1
        if self.hop_counter > self.max_hops:
            print(f"[STP]: Maximum hop count ({self.max_hops}) exceeded. Muting.")
            return False

        # Compute semantic hash of the message content
        norm_text = " ".join(text.lower().strip().split())
        sig = hashlib.sha256(f"{sender}->{recipient}:{norm_text}".encode()).hexdigest()
        
        if sig in self.seen_hashes:
            print(f"[STP]: Repetitive conversational loop detected from {sender}! Port MUTED.")
            return False
            
        self.seen_hashes.add(sig)
        return True
```
- Tracks hop counts and message signatures to forcefully mute repeating loops.

[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-3)
### Block 2: The RAIA Failover Supervisor (Lines 31–60)
[//]: # (SECTION_ID: SIRA-DOC-05_39-SEC-3)
```python
class RAIASupervisor:
    """Manages hot standby agent replicas for N+1 high availability."""
    def __init__(self):
        self.primary_worker = {"id": "worker_1", "alive": True}
        self.standby_worker = {"id": "worker_standby", "alive": True}

    def check_health_and_failover(self, is_primary_responsive: bool) -> str:
        if is_primary_responsive:
            return self.primary_worker["id"]
            
        print("[RAIA]: Primary worker crashed! Failing over to standby replica...")
        self.primary_worker["alive"] = False
        return self.standby_worker["id"]
```
- Switches execution to the standby worker in milliseconds if the primary fails.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-2)
## 2. 10-Second Verification Checklist
[//]: # (SECTION_ID: SIRA-DOC-05_39-SEC-2)
1. Send repetitive messages between agents -> STP stops execution on the 2nd duplicate.
2. Simulate worker failure -> Supervisor promotes standby worker.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-3)
## 3. Beginner Coder Q&A
[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-4)

### What is a "Hop Count"?
[//]: # (SECTION_ID: SIRA-DOC-05_39-SEC-4)
A hop count measures how many times a message has traveled from one agent to another. Capping hops at 4 ensures that agents cannot message each other back and forth forever.

---

[//]: # (SECTION_ID: SIRA-ARCH-05_39-SEC-4)
## 4. Cross-Reference Navigation
[//]: # (SECTION_ID: SIRA-DOC-05_39-SEC-4)
- **Problem Breakdown**: [`01_PROBLEMS_ENCOUNTERED/01_40_SWARM_COLLAPSE_AND_CONVERSATIONAL_LOOP_TRAPS.md`](/docs/devlog/01_40_SWARM_COLLAPSE_AND_CONVERSATIONAL_LOOP_TRAPS)
- **Source Code Evidence**: [`02_SOURCE_EVIDENCE/02_36_RAIA_AND_SEMANTIC_TREE_PROTOCOL_EVIDENCE.md`](/docs/devlog/02_36_RAIA_AND_SEMANTIC_TREE_PROTOCOL_EVIDENCE)
- **Diagnostic Test Logs**: [`03_DIAGNOSTIC_TESTS/03_33_SWARM_FAILOVER_AND_LOOP_PREVENTION_LOGS.md`](/docs/devlog/03_33_SWARM_FAILOVER_AND_LOOP_PREVENTION_LOGS)
- **Architectural Blueprint**: [`04_SOLUTIONS_AND_ARCHITECTURE/04_36_HIGH_AVAILABILITY_SWARM_RESILIENCY_ARCHITECTURE.md`](/docs/devlog/04_36_HIGH_AVAILABILITY_SWARM_RESILIENCY_ARCHITECTURE)
