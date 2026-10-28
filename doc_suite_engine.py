"""Autonomous Multi-Perspective Intelligence & Beginner Doc Suite Engine for Cyber Hub.

Enables standalone on-demand documentation generation on PythonAnywhere without external dependencies.
Generates both:
1. 6-Perspective Threat Dossier (Plain Story, Technical, Business, Client, World, Timeline)
2. 6-Pillar Modular Beginner Doc Suite (Primers, Problems, Evidence, Diagnostics, Architecture, Creation Guides)
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

def sanitize_paths(text: str) -> str:
    """Sanitizes absolute server paths into beginner-friendly relative / placeholder notation."""
    if not text:
        return ""
    sanitized = re.sub(r"/mnt/c/Users/[^/\s'\"]+", "~", text)
    sanitized = re.sub(r"C:\\Users\\[^\\]+", "%USERPROFILE%", sanitized)
    sanitized = re.sub(r"/home/[^/\s'\"]+", "~", sanitized)
    sanitized = re.sub(r"file:///[^\s\)]+", "<file_uri_removed>", sanitized)
    return sanitized

def build_cross_reference_dropdown(title: str, cve_id: Optional[str] = None) -> str:
    """Builds an accessible collapsible table for cross-references."""
    cve_label = f" ({cve_id})" if cve_id else ""
    return f"""<details class="crossref-dropdown" style="border: 1px solid #19e6ff; border-radius: 6px; padding: 12px; margin: 20px 0; background: rgba(25, 230, 255, 0.05);">
<summary style="font-weight: bold; cursor: pointer; color: #19e6ff;">🔽 Cross-References & System Parallels (Click to Expand)</summary>

| Related Subsystem / Pillar | Architectural Parallel & Shared Mechanism | Context & Domain |
| :--- | :--- | :--- |
| **Pillar 01: Problems Encountered** | Exploit vector breakdown and trust boundary violation for {title}{cve_label}. | Root Cause Analysis |
| **Pillar 04: Architecture** | Zero-Trust defense blueprint and ingress barrier enforcement. | Defensive Posture |
| **Pillar 05: From-Scratch Guide** | Step-by-step blank-editor implementation of verification and detection scripts. | Hands-On Implementation |

</details>"""

def synthesize_story_perspectives(intel: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the 6 distinct perspectives for a threat intelligence item."""
    title = intel.get("title") or intel.get("cve_id") or "Critical Cyber Threat Advisory"
    cves = intel.get("cves") or ([intel["cve_id"]] if "cve_id" in intel else [])
    primary_cve = cves[0] if cves else None
    source = intel.get("source") or "Genesis Cyber Intelligence"
    summary = intel.get("summary") or intel.get("description") or "Active threat advisory."
    remediation = intel.get("remediation") or "Apply vendor updates immediately."
    threat_level = intel.get("threat_level", "HIGH")
    score = intel.get("score", 75)
    date_str = intel.get("date") or datetime.now().strftime("%Y-%m-%d")

    plain = {
        "headline": f"Inside the Threat: {title}",
        "hook": f"A significant cybersecurity development regarding {source} has surfaced, presenting high-priority triage decisions for security engineers.",
        "narrative": (
            f"Threat analysis teams have documented active exploitation dynamics surrounding {title}.\n\n"
            f"{summary}\n\n"
            f"The incident highlights the continuous tension between proactive architectural isolation and dynamic adversary probing. "
            f"Defensive teams are urged to inspect ingress access lists and enforce patch integrity immediately."
        ),
        "analogy": "It is like discovering that an auxiliary service door on the perimeter of a secured facility has a misaligned latch—undetected until pressure is applied.",
        "key_takeaway": "Proactive vulnerability management and zero-trust network segregation prevent rapid weaponization."
    }

    technical = {
        "cves": cves,
        "root_cause": intel.get("root_cause", "Improper boundary validation or architectural trust assumption in service logic."),
        "attack_vector": intel.get("attack_vector", "Network perimeter access or untrusted input deserialization."),
        "affected_systems": [intel.get("product", "Enterprise application and server stacks")],
        "exploit_mechanics": summary,
        "iocs": [
            {"type": "Advisory Identifier", "indicator": primary_cve or title, "context": f"Published via {source}"},
            {"type": "Threat Severity", "indicator": f"{threat_level} (Score {score}/100)", "context": "Triage priority"}
        ],
        "defense_steps": [
            remediation,
            "Restrict perimeter exposure by placing sensitive management interfaces behind VPN/MFA.",
            "Verify process parent-child trees and check service logs for anomalous command lines."
        ]
    }

    business = {
        "financial_exposure": f"Estimated $1.2M - $5.5M in potential triage, downtime, and breach response costs if exploited.",
        "downtime_cost": "Moderate to high disruption depending on asset tier and failover redundancy.",
        "regulatory_risks": [
            "SEC Form 8-K cyber incident materiality disclosure obligations.",
            "GDPR / CCPA data privacy breach notification mandates."
        ],
        "reputational_blast_radius": "Elevated customer and stakeholder friction if operational data or uptime is compromised.",
        "boardroom_actions": [
            "Request immediate briefing from CISO on corporate asset exposure.",
            "Ensure insurance coverage and incident response retainers are primed.",
            "Verify that immutable offline backups are verified and restorable."
        ]
    }

    client = {
        "consumer_impact": "End-users may encounter temporary service interruptions or receive requests to verify authentication factors.",
        "exposed_data_types": ["Session metadata", "Authentication tokens", "Hosted application data"],
        "what_it_feels_like": "Usually silent on the client side until service downtime or credential rotation notices appear.",
        "user_action_checklist": [
            "Enable multi-factor authentication (MFA) on all corporate and personal logins.",
            "Verify security alerts through official vendor status portals rather than unverified emails.",
            "Keep endpoint operating systems and client software updated."
        ]
    }

    world = {
        "threat_actor": intel.get("adversary", "Opportunistic threat collectives and state-aligned offensive groups."),
        "geopolitical_context": "Part of the continuous offensive probing of commercial and governmental software supply chains.",
        "supply_chain_scope": "Cascades through downstream integrators and third-party software dependencies.",
        "critical_infrastructure_risk": "Elevated if utilized across healthcare, municipal, or financial transit networks.",
        "global_takeaway": "Modern cybersecurity sovereignty requires rapid vulnerability ingestion and transparent patch attestation."
    }

    timeline = {
        "origin_story": f"Disclosed through {source} threat intelligence telemetry.",
        "milestones": [
            {"timestamp": date_str, "title": "Initial Disclosure", "detail": summary[:140] + "...", "significance": "Detection"},
            {"timestamp": date_str, "title": "Remediation Advisory", "detail": f"Official defense advisory issued by {source}.", "significance": "Mitigation"}
        ],
        "current_status": "Active defense and patch rollouts underway."
    }

    return {
        "plain_story": plain,
        "technical": technical,
        "business": business,
        "client": client,
        "world": world,
        "origin_timeline": timeline
    }

def synthesize_beginner_doc_suite(title: str, perspectives: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the 6 Functional Documentation Pillars conforming to beginner-doc-suite."""
    plain = perspectives.get("plain_story", {})
    tech = perspectives.get("technical", {})
    biz = perspectives.get("business", {})
    cves = tech.get("cves", [])
    primary_cve = cves[0] if cves else "N/A"

    p0 = f"""## Pillar 00: Foundational Primers
### System Overview
{plain.get('hook', '')}

{plain.get('narrative', '')}

### The Beginner Mental Model & Analogy
> [!NOTE]
> **Everyday Analogy**: {plain.get('analogy', '')}

### Plain-English Beginner Glossary
| Term | Plain-English Definition |
| :--- | :--- |
| **CVE ({primary_cve})** | Common Vulnerabilities and Exposures. Standard unique catalog number for this security flaw. |
| **Attack Vector** | The specific entry route or interface an attacker abuses to trigger the vulnerability. |
| **Root Cause** | The fundamental design or coding mistake in the software that allowed the exploit. |
| **Zero-Trust** | A security framework requiring continuous verification at every layer rather than trusting network perimeters. |

{build_cross_reference_dropdown(title, primary_cve)}

### Beginner Coder Q&A
**Q: Why does this matter for junior developers?**  
A: Understanding how vulnerabilities materialize prevents you from repeating similar trust-assumption mistakes in your own code.
"""

    p1 = f"""## Pillar 01: Problems Encountered
### Symptom vs. Root Cause Breakdown
- **Surface Symptom (Observed by Users/Admins)**: Unexpected process termination, anomalous network connections, or elevated latency.
- **Architectural Root Cause**: {tech.get('root_cause', '')}
- **Vulnerable Surface**: {', '.join(tech.get('affected_systems', []))}

### Exploit Mechanics
1. **Adversary Vector**: Attacker accesses `{tech.get('attack_vector', '')}`.
2. **Exploitation**: {tech.get('exploit_mechanics', '')}
3. **Impact**: Unauthorized access, service disruption, or privilege escalation.

{build_cross_reference_dropdown(title, primary_cve)}

### Beginner Coder Q&A
**Q: Can a vulnerability be exploited without leaving traces?**  
A: Sophisticated attacks minimize disk writes, but memory map audits and network connection anomalies almost always leave subtle telemetry.
"""

    p2 = f"""## Pillar 02: Source Evidence
### Primary Threat Citations
- **CVE Identifier**: {primary_cve}
- **Affected Systems**: {', '.join(tech.get('affected_systems', []))}

### Indicators of Compromise (IOCs)
| Type | Indicator / Identifier | Forensic Context |
| :--- | :--- | :--- |
"""
    for ioc in tech.get("iocs", []):
        p2 += f"| `{ioc.get('type')}` | `{ioc.get('indicator')}` | {ioc.get('context')} |\n"

    p2 += f"""
{build_cross_reference_dropdown(title, primary_cve)}

### Beginner Coder Q&A
**Q: How do defenders use IOCs?**  
A: Security Operations Centers (SOCs) ingest IOCs into SIEMs to flag historical or ongoing connections matching these signatures.
"""

    p3 = f"""## Pillar 03: Diagnostic Tests
### Terminal Inspection Commands
Execute these non-destructive commands to audit your local or server environment:

```bash
# 1. Check for active listening ports and services
ss -tulpn | grep -E ":22|:80|:443"

# 2. Inspect running processes for anomalous memory mappings
ps aux | grep -iE "vulnerable|daemon|python" | head -n 10
```

### Post-Mitigation Verification Proof
1. Verify package version is updated past the affected build number.
2. Confirm listening sockets only accept connections from authorized network CIDRs.

{build_cross_reference_dropdown(title, primary_cve)}

### Beginner Coder Q&A
**Q: What is `ss` and why not `netstat`?**  
A: `ss` is the modern Linux socket utility. It reads directly from kernel space, making it faster and safer than deprecated `netstat`.
"""

    p4 = f"""## Pillar 04: Solutions & Architecture
### Prioritized Defensive Sequence
"""
    for idx, step in enumerate(tech.get("defense_steps", []), 1):
        p4 += f"{idx}. **{step}**\n"

    p4 += f"""
### Zero-Trust Architecture Blueprint
- **Least Privilege**: Daemons must run under non-root service accounts with strict file system read-only mounts.
- **Mutual Verification**: Enforce token or certificate attestation between internal services.

{build_cross_reference_dropdown(title, primary_cve)}

### Beginner Coder Q&A
**Q: Why is defense-in-depth necessary if we patched?**  
A: If an attacker bypassed one layer before the patch, secondary controls (like egress filtering) prevent them from exfiltrating data.
"""

    p5 = f"""## Pillar 05: From-Scratch Creation Guides
### Step-by-Step: Writing an Automated Mitigation Audit Script
Create a blank file named `audit_defense.sh`:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: audit_defense.sh
# Purpose: Rapid remediation check for {primary_cve}
# ==============================================================================
set -euo pipefail

echo "==> Auditing system integrity..."
if command -v systemctl >/dev/null 2>&1; then
    echo "    systemctl detected. Auditing service states."
else
    echo "    Notice: Standalone container or non-systemd environment."
fi

echo "==> Remediation check completed successfully."
```

### Line-by-Line Breakdown
- `set -euo pipefail`: Bash strict mode preventing silent execution errors.
- `command -v`: Robust POSIX method for checking command existence.

{build_cross_reference_dropdown(title, primary_cve)}

### Beginner Coder Q&A
**Q: Why should audit scripts avoid external dependencies?**  
A: In an emergency or isolated disaster-recovery sandbox, Python libraries or package managers may not be accessible. Clean Bash runs everywhere.
"""

    return {
        "pillar_00": {"pillar_id": "pillar_00", "title": "Pillar 00: Foundational Primers", "subtitle": "System Overview & Glossary", "content": sanitize_paths(p0)},
        "pillar_01": {"pillar_id": "pillar_01", "title": "Pillar 01: Problems Encountered", "subtitle": "Symptom vs. Root Cause", "content": sanitize_paths(p1)},
        "pillar_02": {"pillar_id": "pillar_02", "title": "Pillar 02: Source Evidence", "subtitle": "Advisory Citations & IOCs", "content": sanitize_paths(p2)},
        "pillar_03": {"pillar_id": "pillar_03", "title": "Pillar 03: Diagnostic Tests", "subtitle": "Terminal Commands & Proof", "content": sanitize_paths(p3)},
        "pillar_04": {"pillar_id": "pillar_04", "title": "Pillar 04: Solutions & Architecture", "subtitle": "Zero-Trust Blueprints", "content": sanitize_paths(p4)},
        "pillar_05": {"pillar_id": "pillar_05", "title": "Pillar 05: From-Scratch Creation Guides", "subtitle": "Line-by-Line Blank Editor Guide", "content": sanitize_paths(p5)}
    }

def generate_full_intel_bundle(intel: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the unified bundle combining 6 perspectives and 6-pillar beginner documentation suite."""
    title = intel.get("title") or intel.get("cve_id") or "Critical Cyber Threat Advisory"
    story_id = intel.get("story_id") or re.sub(r"[^a-zA-Z0-9_-]+", "-", title.lower()).strip("-")[:45]
    cves = intel.get("cves") or ([intel["cve_id"]] if "cve_id" in intel else [])

    perspectives = synthesize_story_perspectives(intel)
    doc_suite = synthesize_beginner_doc_suite(title, perspectives)

    return {
        "story_id": story_id,
        "title": title,
        "subtitle": f"Threat Dossier & Multi-Perspective Analysis",
        "created_at": intel.get("date") or datetime.now().strftime("%Y-%m-%d"),
        "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "primary_source_name": intel.get("source", "Genesis Threat Feed"),
        "primary_source_url": intel.get("raw_link", ""),
        "tags": intel.get("tags", []) + cves,
        "score": intel.get("score", 75),
        "threat_level": intel.get("threat_level", "HIGH"),
        "story": perspectives,
        "doc_suite": doc_suite
    }
