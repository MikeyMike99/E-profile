[//]: # (DOC_ID: SIRA-TXT-CH_21 | VERSION: v1.0 | SCOPE: TXT)

# Chapter 21: Introduction to Agentic Firewalls

[//]: # (SECTION_ID: SIRA-TXT-CH_21-SEC-21_1)
## 21.1 The Need for Agentic Bulkheads
[//]: # (SECTION_ID: SIRA-TXT-CH21-SEC-21_1)

In the previous module, we explored Agentic Control Lists (ACLs)—the meticulous, rule-by-rule filters that the Orchestrator uses to verify an AI subagent's identity and intent. If the ACLs act as the armed guards checking identification at the gate, then **Agentic Firewalls** represent the reinforced steel bulkheads that physically divide the compound.

With the persistent threat of Prompt Injections, Semantic DoS attacks, and spoofed UUIDs, how can the DevCore Sandbox be physically designed to protect the `core_engine`? How do we ensure that end-to-end WebSocket communications between the Tier 2 Modders and the LLM remain untampered? 

The Sandbox security infrastructure dictates exactly how these digital boundaries are drawn. Just as there are many sizes of Modder swarms, there are many ways to build a secure engine architecture. However, the Siraugga Engine relies on a highly standardized Zero-Trust topology. This module covers the foundational ways that Agentic Firewalls are deployed to carve out secure zones within the live environment.

---

[//]: # (SECTION_ID: SIRA-TXT-CH_21-SEC-21_2)
## 21.2 Module Objectives & Master Syllabus
[//]: # (SECTION_ID: SIRA-TXT-CH21-SEC-21_2)

This module shifts focus from surgical rule generation (ACLs) to sweeping architectural boundaries. It explains how Agentic Firewalls are implemented to provide overarching Sandbox security.

The following core topics dictate the next phase of the DevCore security engine:

1.  **Securing Swarms with Agentic Firewalls:** Understanding the fundamental difference between an ACL packet filter and a stateful Agentic Firewall, and how they operate together to secure the game state.
2.  **Firewalls in Sandbox Topology (Network Design):** Exploring the architectural design considerations for deploying these bulkheads. Where do we place the firewalls? How do we segregate the untrusted public Modder WebSockets from the highly secure internal orchestration APIs?

A perfectly configured ACL is useless if the attacker can simply walk around the gate. This module teaches you how to build the walls.
