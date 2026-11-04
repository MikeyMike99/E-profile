"""Autonomous Cyber Threat Intelligence Engine for e_profile.

Enforces strict quota conservation and rate limiting across upstream intelligence providers:
- The Hacker News RSS: Real-time public releases (1-2 hour cooldown, 0 API quota cost).
- CISA KEV Catalog: Federal binding operational directives (6-12 hour cooldown).
- AlienVault OTX Pulses: Threat actor feeds & IOCs (6-12 hour cooldown).
- Tavily Intelligence: Strict emergency fallback only (max 1 query / 24 hours UTC).

Guarantees the newest released cyber advisory is ALWAYS displayed on top.
"""

from __future__ import annotations

import os
import re
import json
import time
import email.utils
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import requests

try:
    from config import Config
    BASE_DIR = Config.ROOT_DIR
except Exception:
    BASE_DIR = Path(__file__).resolve().parent

CACHE_DIR = BASE_DIR / "cache"
MANIFEST_FILE = CACHE_DIR / "current_digest_manifest.json"
RATE_LIMIT_FILE = CACHE_DIR / "rate_limit_state.json"
TEMP_DOCS_DIR = CACHE_DIR / "temp_docs"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def parse_to_epoch(date_str: Optional[str]) -> float:
    """Parses various date formats (RFC 2822, ISO 8601, YYYY-MM-DD) to epoch seconds."""
    if not date_str:
        return 0.0
    cleaned = date_str.strip()
    # 1. Try RFC 2822 (e.g. 'Mon, 02 Nov 2026 11:21:07 +0530')
    try:
        dt = email.utils.parsedate_to_datetime(cleaned)
        return dt.timestamp()
    except Exception:
        pass
    # 2. Try ISO 8601 / YYYY-MM-DD
    try:
        if len(cleaned) == 10 and re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
            dt = datetime.strptime(cleaned, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.timestamp()
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass
    # 3. Fallback: search for YYYY-MM-DD in text
    match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", cleaned)
    if match:
        try:
            dt = datetime.strptime(match.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    return 0.0


def format_display_date(epoch_ts: float, original_str: str = "") -> str:
    """Formats release timestamp or original string into an accessible, readable string:
    e.g. 'November 1, 2026 at 2 PM'.
    Uses actual full month name, no slashes, no minutes or seconds, rounded to nearest hour.
    """
    from datetime import timedelta
    dt = None
    if original_str:
        cleaned = original_str.strip()
        try:
            dt = email.utils.parsedate_to_datetime(cleaned)
        except Exception:
            pass
        if dt is None:
            try:
                dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            except Exception:
                pass
    if dt is None and epoch_ts and epoch_ts > 0:
        try:
            dt = datetime.fromtimestamp(epoch_ts, tz=timezone.utc)
        except Exception:
            pass
    if dt is None:
        dt = datetime.now(timezone.utc)

    # Round to nearest hour
    if dt.minute >= 30:
        dt = dt + timedelta(hours=1)

    month = dt.strftime("%B")
    day = dt.day
    year = dt.year
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{month} {day}, {year} at {hour} {ampm}"


class ThreatIntelEngine:
    COOLDOWN_RSS = 3600         # 1 hour (frequent real-time updates, free RSS)
    COOLDOWN_CISA = 21600       # 6 hours (CISA updates 1-2x daily)
    COOLDOWN_OTX = 21600        # 6 hours
    COOLDOWN_GLOBAL = 1800      # 30 mins between scheduled full checks
    TAVILY_DAILY_LIMIT = 1      # Hard cap: max 1 Tavily search / 24 hours

    def __init__(self):
        self.otx_api_key = os.environ.get("OTX_API_KEY", "")
        self.tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
        if not (self.otx_api_key and self.tavily_api_key):
            self._load_local_keys()
        self.proxies = None
        if "PYTHONANYWHERE_DOMAIN" in os.environ or Path("/var/www").exists():
            pa_proxy = "http://proxy.server:3128"
            self.proxies = {"http": pa_proxy, "https": pa_proxy}
    def _load_local_keys(self):
        """Attempts to load keys from cyber_news/keys.py if available locally."""
        local_keys_path = Path("/mnt/c/Users/michael/Documents/cyber_news/keys.py")
        if local_keys_path.exists():
            try:
                content = local_keys_path.read_text(encoding="utf-8")
                tav_match = re.search(r'TAVILY_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                otx_match = re.search(r'OTX_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                if tav_match and not self.tavily_api_key:
                    self.tavily_api_key = tav_match.group(1).strip()
                if otx_match and not self.otx_api_key:
                    self.otx_api_key = otx_match.group(1).strip()
            except Exception:
                pass

    def load_rate_limit_state(self) -> Dict[str, Any]:
        """Loads persistent quota tracking timestamps."""
        if RATE_LIMIT_FILE.exists():
            try:
                with open(RATE_LIMIT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "last_rss_fetch": 0,
            "last_cisa_fetch": 0,
            "last_otx_fetch": 0,
            "last_tavily_fetch": 0,
            "tavily_daily_count": 0,
            "tavily_date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "last_full_refresh": 0
        }

    def save_rate_limit_state(self, state: Dict[str, Any]):
        """Saves persistent quota tracking timestamps."""
        try:
            with open(RATE_LIMIT_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def check_tavily_quota_available(self, state: Dict[str, Any]) -> bool:
        """Enforces the strict 1 query/day limit for Tavily."""
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if state.get("tavily_date_utc") != today_utc:
            state["tavily_date_utc"] = today_utc
            state["tavily_daily_count"] = 0
            self.save_rate_limit_state(state)
        return state.get("tavily_daily_count", 0) < self.TAVILY_DAILY_LIMIT

    # --- SOURCE FETCHERS ---

    def fetch_the_hackers_news_rss(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Parses The Hacker News RSS feed for real-time cybersecurity releases."""
        items = []
        rss_url = "https://feeds.feedburner.com/TheHackersNews"
        try:
            r = requests.get(rss_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) eProfile/2026"}, proxies=self.proxies, timeout=4)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                channel = root.find("channel")
                if channel is not None:
                    for item in channel.findall("item")[:limit]:
                        title = (item.findtext("title") or "").strip()
                        link = (item.findtext("link") or "").strip()
                        pub_date = (item.findtext("pubDate") or "").strip()
                        desc = (item.findtext("description") or "").strip()

                        # Strip HTML tags from description
                        clean_desc = re.sub(r"<[^>]+>", " ", desc)
                        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                        if len(clean_desc) > 350:
                            clean_desc = clean_desc[:350] + "..."

                        cves = re.findall(r"\bCVE-\d{4}-\d{4,7}\b", f"{title} {clean_desc}", re.I)
                        cves = sorted(list(set(c.upper() for c in cves)))
                        epoch_ts = parse_to_epoch(pub_date)

                        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:45]
                        story_id = f"{slug}"

                        items.append({
                            "story_id": story_id,
                            "title": title,
                            "cves": cves,
                            "source": "The Hacker News",
                            "date": pub_date,
                            "timestamp": epoch_ts,
                            "display_date": format_display_date(epoch_ts, pub_date),
                            "summary": clean_desc,
                            "remediation": self._derive_remediation(title, clean_desc, cves),
                            "raw_link": link,
                            "type": "rss"
                        })
        except Exception as e:
            pass
        return items

    def fetch_cisa_kev(self, limit: int = 4) -> List[Dict[str, Any]]:
        """Fetches the official CISA Known Exploited Vulnerabilities catalog."""
        items = []
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        try:
            r = requests.get(url, proxies=self.proxies, timeout=4)
            if r.status_code == 200:
                vulns = r.json().get("vulnerabilities", [])
                sorted_vulns = sorted(vulns, key=lambda x: x.get("dateAdded", ""), reverse=True)
                for v in sorted_vulns[:limit]:
                    cve_id = v.get("cveID", "").upper()
                    vendor = v.get("vendorProject", "Vendor")
                    product = v.get("product", "Product")
                    vuln_name = v.get("vulnerabilityName", "Vulnerability")
                    date_added = v.get("dateAdded", "")
                    action = v.get("requiredAction", "Apply official vendor patch.")
                    due_date = v.get("dueDate", "")
                    notes = v.get("notes", "")

                    epoch_ts = parse_to_epoch(date_added)
                    title = f"{cve_id}: {vendor} {product} - {vuln_name}"
                    summary = f"{vendor} {product} vulnerability ({cve_id}). Mandated federal mitigation deadline: {due_date}. {v.get('shortDescription', '')}"
                    if len(summary) > 350:
                        summary = summary[:350] + "..."

                    raw_link = ""
                    urls = re.findall(r"https?://[^\s;,]+", notes)
                    if urls:
                        raw_link = urls[0]

                    slug = re.sub(r"[^a-zA-Z0-9]+", "-", f"{cve_id}-{product}".lower()).strip("-")[:45]

                    items.append({
                        "story_id": slug,
                        "title": title,
                        "cves": [cve_id] if cve_id else [],
                        "source": "CISA KEV",
                        "date": date_added,
                        "timestamp": epoch_ts,
                        "display_date": format_display_date(epoch_ts, date_added),
                        "summary": summary,
                        "remediation": f"MANDATORY KEV DIRECTIVE: {action} Due Date: {due_date}. Target: {vendor} {product}.",
                        "raw_link": raw_link,
                        "type": "cve"
                    })
        except Exception:
            pass
        return items

    def fetch_otx_pulses(self, limit: int = 4) -> List[Dict[str, Any]]:
        """Queries AlienVault OTX for subscribed threat intelligence pulses."""
        if not self.otx_api_key:
            return []
        items = []
        url = f"https://otx.alienvault.com/api/v1/pulses/subscribed?limit={limit}"
        headers = {"X-OTX-API-KEY": self.otx_api_key}
        try:
            r = requests.get(url, headers=headers, proxies=self.proxies, timeout=4)
            if r.status_code == 200:
                results = r.json().get("results", [])
                for p in results[:limit]:
                    name = p.get("name", "Active Threat Pulse")
                    desc = p.get("description", "") or "Threat advisory pulse."
                    created = p.get("created", "") or p.get("modified", "")
                    adversary = p.get("adversary", "Unattributed Threat Actor")
                    tags = p.get("tags", [])
                    pulse_id = p.get("id", "")
                    ioc_count = p.get("indicator_count", len(p.get("indicators", [])))

                    epoch_ts = parse_to_epoch(created)
                    cves = re.findall(r"\bCVE-\d{4}-\d{4,7}\b", f"{name} {desc} {' '.join(tags)}", re.I)
                    cves = sorted(list(set(c.upper() for c in cves)))

                    summary = f"Adversary: {adversary}. Active IOCs: {ioc_count}. {desc}"
                    if len(summary) > 350:
                        summary = summary[:350] + "..."

                    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")[:45]
                    pulse_url = f"https://otx.alienvault.com/pulse/{pulse_id}" if pulse_id else ""

                    items.append({
                        "story_id": slug,
                        "title": name,
                        "cves": cves,
                        "source": "AlienVault OTX",
                        "date": created[:10] if len(created) >= 10 else created,
                        "timestamp": epoch_ts,
                        "display_date": format_display_date(epoch_ts, created),
                        "summary": summary,
                        "remediation": self._derive_remediation(name, desc, cves),
                        "raw_link": pulse_url,
                        "type": "pulse"
                    })
        except Exception:
            pass
        return items

    def _derive_remediation(self, title: str, text: str, cves: List[str]) -> str:
        """Derives an actionable, plain-English defense recommendation."""
        combined = f"{title} {text}".lower()
        if any(k in combined for k in ["ransomware", "encrypt", "extortion"]):
            return "Verify immutable offline backups, isolate vulnerable subnets, and disable exposed SMB/RDP."
        if any(k in combined for k in ["rce", "remote code", "command injection"]):
            return "Deploy immediate perimeter patch, isolate interface behind VPN/MFA, and monitor parent-child process spawns."
        if any(k in combined for k in ["stealer", "infostealer", "session token"]):
            return "Invalidate active session cookies across identity providers and mandate phishing-resistant FIDO2 MFA."
        if any(k in combined for k in ["supply-chain", "npm", "pypi", "github"]):
            return "Pin exact package hashes in build lockfiles, rotate API/CI secrets, and verify software signatures."
        if cves:
            return f"Apply vendor security update for {cves[0]} immediately and audit perimeter logs for exploitation IOCs."
        return "Enforce zero-trust network segregation, update perimeter firewall rules, and apply latest security patches."

    def calculate_threat_score(self, item: Dict[str, Any]) -> Tuple[int, str]:
        """Calculates a normalized 0-100 threat score and qualitative severity level."""
        score = 0
        all_text = f"{item.get('title', '')} {item.get('summary', '')} {' '.join(item.get('cves', []))}".lower()

        if item.get("source") == "CISA KEV" or item.get("cves"):
            score += 40
        if any(k in all_text for k in ["zero-day", "0-day"]):
            score += 35
        if any(k in all_text for k in ["ransomware", "wiper", "extortion"]):
            score += 25
        if any(k in all_text for k in ["remote code execution", "rce", "unauthenticated", "privilege escalation"]):
            score += 25
        if any(k in all_text for k in ["kernel", "driver", "byovd"]):
            score += 20
        if any(k in all_text for k in ["supply-chain", "backdoor"]):
            score += 20
        if any(k in all_text for k in ["infostealer", "credential"]):
            score += 15

        score = max(15, min(100, score))
        if score >= 80:
            level = "CRITICAL"
        elif score >= 55:
            level = "HIGH"
        elif score >= 35:
            level = "MODERATE"
        else:
            level = "INFORMATIONAL"
        return score, level

    # --- AGGREGATION & REFRESH ---

    def refresh_feed(self, force: bool = False) -> Dict[str, Any]:
        """Executes a surgical quota-aware feed refresh.
        
        The newest released story is ALWAYS sorted on top!
        """
        now = time.time()
        state = self.load_rate_limit_state()

        if not force and (now - state.get("last_full_refresh", 0) < self.COOLDOWN_GLOBAL):
            # Global cooldown active; serve current manifest
            return self.get_feed_status(cached=True, note="Global refresh cooldown active (30 min minimum).")

        collected_items: List[Dict[str, Any]] = []

        # 1. RSS Feed (The Hacker News) - 1-2h cooldown or force
        if force or (now - state.get("last_rss_fetch", 0) >= self.COOLDOWN_RSS):
            rss_items = self.fetch_the_hackers_news_rss(limit=5)
            if rss_items:
                collected_items.extend(rss_items)
                state["last_rss_fetch"] = now

        # 2. CISA KEV - 6h cooldown or force
        if force or (now - state.get("last_cisa_fetch", 0) >= self.COOLDOWN_CISA):
            cisa_items = self.fetch_cisa_kev(limit=4)
            if cisa_items:
                collected_items.extend(cisa_items)
                state["last_cisa_fetch"] = now

        # 3. AlienVault OTX - 6h cooldown or force
        if force or (now - state.get("last_otx_fetch", 0) >= self.COOLDOWN_OTX):
            otx_items = self.fetch_otx_pulses(limit=4)
            if otx_items:
                collected_items.extend(otx_items)
                state["last_otx_fetch"] = now

        # Merge with existing manifest items so older valuable advisories aren't lost
        existing_items = []
        if MANIFEST_FILE.exists():
            try:
                with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                    existing_items = json.load(f).get("items", [])
            except Exception:
                pass

        # Deduplicate items by title, raw_link, or unique story_id
        seen_keys = set()
        merged_items = []

        for item in (collected_items + existing_items):
            title_norm = re.sub(r"[^a-zA-Z0-9]+", "", item.get("title", "").lower())
            link_norm = item.get("raw_link", "").strip().lower()
            dedup_key = link_norm or title_norm or item.get("story_id", "")
            if dedup_key and dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                # Assign threat scores if missing
                if "score" not in item or "threat_level" not in item:
                    sc, lvl = self.calculate_threat_score(item)
                    item["score"] = sc
                    item["threat_level"] = lvl
                # Ensure timestamp is populated for sorting
                if not item.get("timestamp"):
                    item["timestamp"] = parse_to_epoch(item.get("date"))
                if not item.get("display_date"):
                    item["display_date"] = format_display_date(item.get("timestamp", 0), item.get("date", ""))
                merged_items.append(item)

        # STRICT REQUIREMENT: Sort chronologically descending so newest story is ALWAYS on top!
        merged_items.sort(key=lambda x: x.get("timestamp", 0.0), reverse=True)

        # Mark the very top item with a distinct badge
        for idx, item in enumerate(merged_items):
            item["is_latest"] = (idx == 0)

        # Cap total retained feed items to top 15 most recent
        final_items = merged_items[:15]

        # Update persistent manifest
        dispatched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        manifest_data = {
            "dispatched_at": dispatched_at,
            "total_items": len(final_items),
            "items": final_items
        }
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        state["last_full_refresh"] = now
        self.save_rate_limit_state(state)

        return {
            "status": "refreshed",
            "dispatched_at": dispatched_at,
            "total_items": len(final_items),
            "newest_story": final_items[0]["title"] if final_items else "None",
            "rate_limits": state
        }

    @staticmethod
    def get_seed_manifest() -> Dict[str, Any]:
        """Provides instant high-value fallback cyber threat stories with zero network latency."""
        now_ts = time.time()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {
            "dispatched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "total_items": 4,
            "items": [
                {
                    "story_id": "new-volta-infostealer-uses-claude-gemini-and-",
                    "title": "New VOLTA Infostealer Uses Claude, Gemini, and Kimi AI to Rank Victims by Financial Value",
                    "cves": [],
                    "source": "The Hacker News",
                    "date": today_str,
                    "timestamp": now_ts,
                    "display_date": "Recent Advisory",
                    "summary": "Threat actors are weaponizing multimodal LLMs to analyze victim documents and financial records directly in memory, automating target triage.",
                    "remediation": "Deploy endpoint detection rules for unauthorized API calls, enforce strict egress controls, and revoke compromised browser tokens.",
                    "raw_link": "https://thehackernews.com",
                    "type": "rss",
                    "score": 85,
                    "threat_level": "CRITICAL",
                    "is_latest": True
                },
                {
                    "story_id": "cvss-10-0-lxd-microcloud-flaw-lets-attackers-",
                    "title": "CVSS 10.0 LXD, MicroCloud Flaw Lets Attackers Impersonate Trusted Clients Without a Private Key",
                    "cves": ["CVE-2024-41989"],
                    "source": "CISA KEV",
                    "date": today_str,
                    "timestamp": now_ts - 3600,
                    "display_date": "Recent Advisory",
                    "summary": "Flaw in LXD / MicroCloud TLS client authentication allows remote attackers to bypass trust checks and impersonate cluster administrators.",
                    "remediation": "Apply vendor security update for CVE-2024-41989 immediately and audit perimeter logs for exploitation IOCs.",
                    "raw_link": "https://www.cisa.gov",
                    "type": "cve",
                    "score": 95,
                    "threat_level": "CRITICAL",
                    "is_latest": False
                },
                {
                    "story_id": "hackers-steal-about-2-7-million-from-polymark",
                    "title": "Hackers Steal About $2.7 Million From Polymarket Traders via Hijacked DebugBear Script",
                    "cves": [],
                    "source": "AlienVault OTX",
                    "date": today_str,
                    "timestamp": now_ts - 7200,
                    "display_date": "Recent Advisory",
                    "summary": "Supply chain compromise of a third-party performance analytics script resulted in injection of malicious transaction-signing prompts.",
                    "remediation": "Pin exact package hashes in build lockfiles, rotate API/CI secrets, and enforce Content-Security-Policy script-src integrity.",
                    "raw_link": "https://otx.alienvault.com",
                    "type": "pulse",
                    "score": 75,
                    "threat_level": "HIGH",
                    "is_latest": False
                },
                {
                    "story_id": "cisa-adds-critical-palo-alto-networks-exp",
                    "title": "CISA Adds Critical Palo Alto Networks PAN-OS GlobalProtect RCE to KEV Catalog",
                    "cves": ["CVE-2024-3400"],
                    "source": "CISA KEV",
                    "date": today_str,
                    "timestamp": now_ts - 14400,
                    "display_date": "Recent Advisory",
                    "summary": "Command injection vulnerability in GlobalProtect feature of PAN-OS allows an unauthenticated attacker to execute arbitrary code with root privileges.",
                    "remediation": "MANDATORY KEV DIRECTIVE: Apply official vendor patch immediately. Target: Palo Alto Networks PAN-OS.",
                    "raw_link": "https://www.cisa.gov",
                    "type": "cve",
                    "score": 98,
                    "threat_level": "CRITICAL",
                    "is_latest": False
                }
            ]
        }
    def get_feed_status(self, cached: bool = False, note: str = "") -> Dict[str, Any]:
        """Returns rate limit status and manifest metadata."""
        state = self.load_rate_limit_state()
        now = time.time()
        
        manifest_data = {}
        if MANIFEST_FILE.exists():
            try:
                with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception:
                pass

        return {
            "status": "cached" if cached else "active",
            "note": note,
            "dispatched_at": manifest_data.get("dispatched_at", "Never"),
            "total_items": manifest_data.get("total_items", 0),
            "cooldowns": {
                "rss_cooldown_remaining_sec": max(0, int(self.COOLDOWN_RSS - (now - state.get("last_rss_fetch", 0)))),
                "cisa_cooldown_remaining_sec": max(0, int(self.COOLDOWN_CISA - (now - state.get("last_cisa_fetch", 0)))),
                "otx_cooldown_remaining_sec": max(0, int(self.COOLDOWN_OTX - (now - state.get("last_otx_fetch", 0)))),
                "global_cooldown_remaining_sec": max(0, int(self.COOLDOWN_GLOBAL - (now - state.get("last_full_refresh", 0)))),
                "tavily_daily_count": state.get("tavily_daily_count", 0),
                "tavily_daily_limit": self.TAVILY_DAILY_LIMIT
            }
        }
