#!/usr/bin/env python3
"""
DevCore System Network & Threat Intelligence Auditor (audit_system_network.py).

Provides an administrative CLI for system network diagnostics and supply-chain auditing:
- tcpdump: WebSocket socket transport, keep-alive heartbeats, TCP RST flags, and sandbox egress.
- whois: External domain age verification, supply-chain vetting, and IP abuse triage.
"""

import argparse
import json
import os
import sys

DEVCORE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if DEVCORE_ROOT not in sys.path:
    sys.path.insert(0, DEVCORE_ROOT)

from core.network_auditor import DevCoreNetworkAuditor


def format_status(status: str) -> str:
    color_map = {
        "PASS": "\033[92m[PASS]\033[0m",
        "WARN": "\033[93m[WARN]\033[0m",
        "FAIL": "\033[91m[FAIL]\033[0m",
        "ERROR": "\033[91m[ERROR]\033[0m",
        "SKIPPED": "\033[90m[SKIPPED]\033[0m",
    }
    if not sys.stdout.isatty():
        return f"[{status}]"
    return color_map.get(status, f"[{status}]")


def print_scorecard(full_report: dict):
    print("\n=======================================================")
    print("      DEVCORE SYSTEM NETWORK & THREAT AUDIT SCORECARD   ")
    print("=======================================================")
    tools = full_report.get("tools", {})
    print("[*] Tool Availability:")
    for name, meta in tools.items():
        inst = meta.get("installed", False)
        status_tag = format_status("PASS" if inst else "WARN")
        path_info = meta.get("path") or "Not Found"
        ver_info = meta.get("version") or "N/A"
        print(f"    - {name:<10}: {status_tag} {path_info} ({ver_info})")

    audits = full_report.get("audits", {})

    print("\n--- 1. WebSocket Bus Transport Audit (tcpdump) ---")
    ws = audits.get("websocket_transport", {})
    ws_status = ws.get("status", "UNKNOWN")
    print(f"Status: {format_status(ws_status)} Target: {ws.get('target')}")
    if ws.get("live_capture"):
        print(f"Packets Captured: {ws.get('packets_captured')}")
        print(f"TCP Flags: {ws.get('tcp_flags')}")
        print(f"Resets [RST]: {ws.get('resets_detected')}")
    elif ws.get("socket_probe"):
        sp = ws["socket_probe"]
        print(f"Synthetic Socket Probe: Connected={sp.get('connected')}, Latency={sp.get('latency_ms')}ms, HTTP={sp.get('http_status')}")
    for diag in ws.get("diagnostics", []):
        print(f"  > Diagnostic: {diag}")

    print("\n--- 2. Sandbox Egress Security Audit (tcpdump) ---")
    eg = audits.get("sandbox_egress", {})
    eg_status = eg.get("status", "UNKNOWN")
    print(f"Status: {format_status(eg_status)} Interface: {eg.get('interface')}")
    print(f"Unauthorized Egress: {'Detected' if eg.get('unauthorized_egress_detected') else 'None (Clean)'}")
    for diag in eg.get("diagnostics", []):
        print(f"  > Diagnostic: {diag}")

    dom = audits.get("domain_supply_chain")
    if dom:
        print("\n--- 3. Domain Supply-Chain Vetting (whois) ---")
        dom_status = dom.get("status", "UNKNOWN")
        print(f"Status: {format_status(dom_status)} Domain: {dom.get('domain')}")
        print(f"Registrar: {dom.get('registrar') or 'N/A'}")
        print(f"Creation Date: {dom.get('creation_date') or 'N/A'}")
        if dom.get("age_days") is not None:
            print(f"Domain Age: {dom.get('age_days')} days")
        print(f"Abuse Email: {dom.get('abuse_email') or 'N/A'}")
        for diag in dom.get("diagnostics", []):
            print(f"  > Diagnostic: {diag}")

    ip_audit = audits.get("ip_threat_intelligence")
    if ip_audit:
        print("\n--- 4. IP Threat Intelligence Triage (whois) ---")
        ip_status = ip_audit.get("status", "UNKNOWN")
        print(f"Status: {format_status(ip_status)} Target IP: {ip_audit.get('ip')}")
        print(f"Organization: {ip_audit.get('organization') or 'N/A'}")
        print(f"CIDR / NetRange: {ip_audit.get('cidr') or ip_audit.get('netrange') or 'N/A'}")
        print(f"Origin AS: {ip_audit.get('origin_as') or 'N/A'}")
        print(f"Abuse Contact: {ip_audit.get('abuse_email') or 'N/A'}")
        for diag in ip_audit.get("diagnostics", []):
            print(f"  > Diagnostic: {diag}")

    threats = audits.get("log_threat_triage", {})
    if threats.get("logged_ips_discovered", 0) > 0:
        print("\n--- 5. Log Threat Vectors Triage ---")
        print(f"Discovered {threats.get('logged_ips_discovered')} external IP(s) in logs.")
        for item in threats.get("threat_triages", []):
            print(f"  - {item.get('ip')}: {item.get('organization')} (Abuse: {item.get('abuse_email')})")

    print("\n=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="DevCore System Network & Threat Intelligence Auditor")
    parser.add_argument("--all", action="store_true", help="Run all system network and threat intelligence checks")
    parser.add_argument("--websocket", action="store_true", help="Audit WebSocket bus and TCP keep-alives via tcpdump")
    parser.add_argument("--egress", action="store_true", help="Audit sandbox network egress via tcpdump")
    parser.add_argument("--domain", type=str, help="Audit an external domain via whois")
    parser.add_argument("--ip", type=str, help="Audit a remote IP address via whois")
    parser.add_argument("--triage-logs", action="store_true", help="Parse security logs for threat vectors and triage via whois")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    parser.add_argument("--port", type=int, default=5000, help="DevCore Quart port (default: 5000)")

    args = parser.parse_args()
    auditor = DevCoreNetworkAuditor(port=args.port)

    run_any = args.all or args.websocket or args.egress or args.domain or args.ip or args.triage_logs
    if not run_any:
        args.all = True

    if args.all:
        report = auditor.run_full_system_audit(
            target_domain=args.domain or "github.com",
            target_ip=args.ip or "8.8.8.8",
        )
    else:
        report = {
            "timestamp": None,
            "tools": {
                "tcpdump": auditor.tcpdump_meta,
                "whois": auditor.whois_meta,
            },
            "audits": {},
        }
        if args.websocket:
            report["audits"]["websocket_transport"] = auditor.audit_websocket_stream()
        if args.egress:
            report["audits"]["sandbox_egress"] = auditor.audit_sandbox_egress()
        if args.domain:
            report["audits"]["domain_supply_chain"] = auditor.audit_domain_supply_chain(args.domain)
        if args.ip:
            report["audits"]["ip_threat_intelligence"] = auditor.audit_ip_threat_intel(args.ip)
        if args.triage_logs:
            report["audits"]["log_threat_triage"] = auditor.audit_logged_threat_vectors()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_scorecard(report)


if __name__ == "__main__":
    main()
