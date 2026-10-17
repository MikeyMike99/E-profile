# Chapter 24: Introduction to Zone-Based Sandbox Policies

## 24.1 The Evolution of Sandbox Boundaries

In the earliest iterations of the DevCore Engine, Tier 5 Admins relied heavily on **Classic Agentic Bulkheads**. These classic firewalls were strictly directory-based. An Admin had to manually write an access policy for the `/game_demo/npc/` directory, and then write a completely separate policy for the `/game_demo/items/` directory.

This architecture functioned perfectly for small, isolated test environments. However, as Modders began spawning massive AI swarms that dynamically created hundreds of temporary file directories in real-time, the classic bulkhead design collapsed. It was impossible to manually write security rules for directories that were being generated and deleted by subagents every second.

To secure massive swarms, DevCore introduced an evolutionary architectural step: **Zone-Based Sandbox Policies (ZSP)**.

## 24.2 The Zone-Based Paradigm

Zone-Based Sandbox Policies abstract security away from the physical directory path. Instead of assigning a firewall rule to a specific folder, an Admin assigns multiple directories to a single **Zone**. 

Security policies are then defined strictly based on the *relationship between the zones*, not the individual file paths that are communicating. 

For example, an Admin can create an `Asset_Zone` and assign fifty different 3D-modeling directories to it. By default, all traffic between directories within the `Asset_Zone` flows completely unrestricted. If a subagent in the `Asset_Zone` needs to send a JSON payload to a subagent in the `Script_Zone`, the Orchestrator checks the single policy governing the relationship between those two zones, regardless of which specific folders the agents are standing in.

By defining security requirements by the *nature* of the zone rather than the physical file path, Tier 5 Admins can secure an infinitely expanding Swarm environment.

---

## 24.3 Module Objectives & Master Syllabus

This module teaches the architecture and command-line implementation of advanced Swarm zoning.

The following core topics dictate this phase of DevCore security:

1.  **ZSP Overview:** Explaining how Zone-Based Sandbox Policies are deployed to secure massive, dynamically shifting network environments.
2.  **ZSP Operation:** Explaining the mechanical operation of how the Orchestrator routes JSON traffic across different Zone boundaries, including the critical "Self Zone" (`App Router Module`).
3.  **Configure a ZSP:** Learning to implement a Zone-Based Sandbox Policy using the native `agy` CLI.
