import os
import glob
import json
import time
import datetime

class TokenTelemetryEngine:
    def __init__(self, brain_dir=None):
        self._brain_dir = brain_dir or os.path.expanduser("~/.gemini/antigravity-cli/brain")
        self._tz = datetime.timezone(datetime.timedelta(hours=2))
        self._file_cursors = {}
        self._steps = []
        self._sessions = {}
        self._last_refresh = 0.0
        self._swarmflow_path = os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "swarmflow.jsonl")
        )
        self._cached_telemetry = None
        self._cached_time = 0.0
        self._cache_ttl = 3.0

    def record_live_step(self, conv_id: str, step_data: dict):
        try:
            inp = int(step_data.get("input_tokens") or 0)
            cache = int(step_data.get("cache_read_tokens") or 0)
            out = int(step_data.get("output_tokens") or 0)
            if inp <= 0 and cache <= 0 and out <= 0:
                return

            ts_str = step_data.get("created_at")
            if ts_str:
                try:
                    dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(self._tz)
                except Exception:
                    dt = datetime.datetime.now(self._tz)
            else:
                dt = datetime.datetime.now(self._tz)

            self._cached_telemetry = None
            total = inp + cache + out
            step = {
                "ts": dt.timestamp(),
                "dt": dt,
                "conv_id": conv_id,
                "inp": inp,
                "cache": cache,
                "out": out,
                "total": total,
            }
            self._steps.append(step)

            sess = self._sessions.setdefault(conv_id, {
                "conv_id": conv_id,
                "first_seen": dt,
                "last_active": dt,
                "steps": 0,
                "inp": 0,
                "cache": 0,
                "out": 0,
                "total": 0,
            })
            sess["last_active"] = max(sess["last_active"], dt)
            sess["steps"] += 1
            sess["inp"] += inp
            sess["cache"] += cache
            sess["out"] += out
            sess["total"] += total
        except Exception:
            pass

    def refresh(self, force=False):
        now = time.time()
        if not force and (now - self._last_refresh) < 30.0:
            return

        pattern = os.path.join(self._brain_dir, "*", ".system_generated", "logs", "transcript.jsonl")
        files = glob.glob(pattern)

        for fpath in files:
            try:
                st = os.stat(fpath)
                mtime, size = st.st_mtime, st.st_size
                prev = self._file_cursors.get(fpath)
                if prev and prev[0] == mtime and prev[1] == size:
                    continue

                parts = fpath.replace("\\", "/").split("/")
                conv_id = parts[-4] if len(parts) >= 4 else "unknown"

                offset = 0
                if prev and size >= prev[1]:
                    offset = prev[2]

                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    if offset > 0:
                        fp.seek(offset)
                    for line in fp:
                        if '"input_tokens"' not in line:
                            continue
                        try:
                            d = json.loads(line)
                            inp = int(d.get("input_tokens") or 0)
                            cache = int(d.get("cache_read_tokens") or 0)
                            out = int(d.get("output_tokens") or 0)
                            if inp or cache or out:
                                ts_str = d.get("created_at", "")
                                if ts_str:
                                    dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(self._tz)
                                else:
                                    dt = datetime.datetime.now(self._tz)

                                total = inp + cache + out
                                step = {
                                    "ts": dt.timestamp(),
                                    "dt": dt,
                                    "conv_id": conv_id,
                                    "inp": inp,
                                    "cache": cache,
                                    "out": out,
                                    "total": total,
                                }
                                self._steps.append(step)

                                sess = self._sessions.setdefault(conv_id, {
                                    "conv_id": conv_id,
                                    "first_seen": dt,
                                    "last_active": dt,
                                    "steps": 0,
                                    "inp": 0,
                                    "cache": 0,
                                    "out": 0,
                                    "total": 0,
                                })
                                sess["last_active"] = max(sess["last_active"], dt)
                                sess["steps"] += 1
                                sess["inp"] += inp
                                sess["cache"] += cache
                                sess["out"] += out
                                sess["total"] += total
                        except Exception:
                            continue
                    new_offset = fp.tell()
                    self._file_cursors[fpath] = (mtime, size, new_offset)
            except Exception:
                continue

        self._last_refresh = now

    def _calc_cache_hit(self, cache: int, inp: int) -> float:
        denom = cache + inp
        return round((cache / denom * 100.0), 2) if denom > 0 else 0.0

    def get_telemetry_data(self, requested_timeframe: str = "all", force_refresh: bool = False) -> dict:
        now = time.time()
        if not force_refresh and self._cached_telemetry is not None and (now - self._cached_time) < self._cache_ttl:
            return self._cached_telemetry
        self.refresh(force=force_refresh)
        now_dt = datetime.datetime.now(self._tz)
        now_ts = now_dt.timestamp()

        minute_buckets = {}
        curr_min = now_dt.replace(second=0, microsecond=0)
        for i in range(60):
            slot_dt = curr_min - datetime.timedelta(minutes=59 - i)
            key = slot_dt.strftime("%H:%M")
            minute_buckets[key] = {
                "key": key,
                "label": key,
                "full_label": slot_dt.strftime("%Y-%m-%d %H:%M"),
                "requests": 0,
                "input_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_hit_rate": 0.0,
                "avg_per_request": 0,
            }

        hourly_buckets = {}
        curr_hour = now_dt.replace(minute=0, second=0, microsecond=0)
        for i in range(24):
            slot_dt = curr_hour - datetime.timedelta(hours=23 - i)
            key = slot_dt.strftime("%Y-%m-%d %H:00")
            hourly_buckets[key] = {
                "key": key,
                "label": slot_dt.strftime("%H:00"),
                "full_label": key,
                "requests": 0,
                "input_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_hit_rate": 0.0,
                "avg_per_request": 0,
            }

        daily_buckets = {}
        curr_day = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(30):
            slot_dt = curr_day - datetime.timedelta(days=29 - i)
            key = slot_dt.strftime("%Y-%m-%d")
            daily_buckets[key] = {
                "key": key,
                "label": slot_dt.strftime("%b %d"),
                "full_label": key,
                "requests": 0,
                "input_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_hit_rate": 0.0,
                "avg_per_request": 0,
            }

        monthly_buckets = {}
        y, m = now_dt.year, now_dt.month
        month_keys = []
        for _ in range(12):
            month_keys.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        for key in reversed(month_keys):
            m_dt = datetime.datetime.strptime(key, "%Y-%m").replace(tzinfo=self._tz)
            monthly_buckets[key] = {
                "key": key,
                "label": m_dt.strftime("%b %Y"),
                "full_label": key,
                "requests": 0,
                "input_tokens": 0,
                "cache_read_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_hit_rate": 0.0,
                "avg_per_request": 0,
            }

        yearly_buckets = {}
        current_year = str(now_dt.year)
        yearly_buckets[current_year] = {
            "key": current_year,
            "label": current_year,
            "full_label": current_year,
            "requests": 0,
            "input_tokens": 0,
            "cache_read_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cache_hit_rate": 0.0,
            "avg_per_request": 0,
        }

        minute_burn = 0
        hour_tokens = 0
        total_24h_tokens = 0
        total_24h_cache = 0
        total_24h_inp = 0
        total_24h_requests = 0

        total_lifetime_tokens = 0
        total_lifetime_cache = 0
        total_lifetime_inp = 0
        total_lifetime_requests = 0

        for step in self._steps:
            dt = step["dt"]
            inp = step["inp"]
            cache = step["cache"]
            out = step["out"]
            tot = step["total"]
            age_sec = now_ts - step["ts"]

            total_lifetime_tokens += tot
            total_lifetime_cache += cache
            total_lifetime_inp += inp
            total_lifetime_requests += 1

            if age_sec <= 60:
                minute_burn += tot

            if (now_dt - dt).total_seconds() <= 3600 and dt.hour == now_dt.hour and dt.date() == now_dt.date():
                hour_tokens += tot

            if age_sec <= 86400:
                total_24h_tokens += tot
                total_24h_cache += cache
                total_24h_inp += inp
                total_24h_requests += 1

            if age_sec <= 3600:
                m_key = dt.strftime("%H:%M")
                if m_key in minute_buckets:
                    b = minute_buckets[m_key]
                    b["requests"] += 1
                    b["input_tokens"] += inp
                    b["cache_read_tokens"] += cache
                    b["output_tokens"] += out
                    b["total_tokens"] += tot

            if age_sec <= 86400:
                h_key = dt.strftime("%Y-%m-%d %H:00")
                if h_key in hourly_buckets:
                    b = hourly_buckets[h_key]
                    b["requests"] += 1
                    b["input_tokens"] += inp
                    b["cache_read_tokens"] += cache
                    b["output_tokens"] += out
                    b["total_tokens"] += tot

            d_key = dt.strftime("%Y-%m-%d")
            if d_key in daily_buckets:
                b = daily_buckets[d_key]
                b["requests"] += 1
                b["input_tokens"] += inp
                b["cache_read_tokens"] += cache
                b["output_tokens"] += out
                b["total_tokens"] += tot

            mo_key = dt.strftime("%Y-%m")
            if mo_key in monthly_buckets:
                b = monthly_buckets[mo_key]
                b["requests"] += 1
                b["input_tokens"] += inp
                b["cache_read_tokens"] += cache
                b["output_tokens"] += out
                b["total_tokens"] += tot

            y_key = str(dt.year)
            if y_key not in yearly_buckets:
                yearly_buckets[y_key] = {
                    "key": y_key,
                    "label": y_key,
                    "full_label": y_key,
                    "requests": 0,
                    "input_tokens": 0,
                    "cache_read_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cache_hit_rate": 0.0,
                    "avg_per_request": 0,
                }
            yb = yearly_buckets[y_key]
            yb["requests"] += 1
            yb["input_tokens"] += inp
            yb["cache_read_tokens"] += cache
            yb["output_tokens"] += out
            yb["total_tokens"] += tot

        local_lifetime_tokens = 0
        local_24h_tokens = 0
        local_24h_requests = 0

        if os.path.exists(self._swarmflow_path):
            try:
                with open(self._swarmflow_path, "r", encoding="utf-8", errors="ignore") as sfp:
                    for sline in sfp:
                        if not sline.strip():
                            continue
                        try:
                            sdata = json.loads(sline)
                            tier = sdata.get("model_tier", "")
                            p_agent = sdata.get("parent_agent_id", "")
                            if "Local CPU" in tier or "Local Qwen" in tier or p_agent == "Qwen2.5-1.5B-CPU":
                                vol = int(sdata.get("token_volume") or 0)
                                local_lifetime_tokens += vol
                                ts_str = sdata.get("timestamp", "")
                                if ts_str:
                                    try:
                                        s_dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(self._tz)
                                        age_s = now_ts - s_dt.timestamp()
                                        if age_s <= 86400:
                                            local_24h_tokens += vol
                                            local_24h_requests += 1
                                    except Exception:
                                        pass
                        except Exception:
                            continue
            except Exception:
                pass

        def finalize_bucket_list(bucket_dict, sort_keys=None):
            items = []
            keys = sort_keys if sort_keys is not None else sorted(bucket_dict.keys())
            for k in keys:
                b = bucket_dict[k]
                b["cache_hit_rate"] = self._calc_cache_hit(b["cache_read_tokens"], b["input_tokens"])
                b["avg_per_request"] = round(b["total_tokens"] / b["requests"]) if b["requests"] > 0 else 0
                items.append(b)
            return items

        minute_series = finalize_bucket_list(minute_buckets, list(minute_buckets.keys()))
        hourly_series = finalize_bucket_list(hourly_buckets, list(hourly_buckets.keys()))
        daily_series = finalize_bucket_list(daily_buckets, list(daily_buckets.keys()))
        monthly_series = finalize_bucket_list(monthly_buckets, list(monthly_buckets.keys()))
        yearly_series = finalize_bucket_list(yearly_buckets, sorted(yearly_buckets.keys()))

        sessions_list = []
        for s in self._sessions.values():
            sessions_list.append({
                "conv_id": s["conv_id"],
                "last_active": s["last_active"].strftime("%Y-%m-%d %H:%M:%S"),
                "last_active_ts": s["last_active"].timestamp(),
                "steps": s["steps"],
                "input_tokens": s["inp"],
                "cache_read_tokens": s["cache"],
                "output_tokens": s["out"],
                "total_tokens": s["total"],
                "cache_hit_rate": self._calc_cache_hit(s["cache"], s["inp"]),
            })
        sessions_list.sort(key=lambda x: x["last_active_ts"], reverse=True)

        combined_total = total_lifetime_tokens + local_lifetime_tokens
        local_offload_pct = round((local_lifetime_tokens / combined_total * 100.0), 1) if combined_total > 0 else 0.0
        saved_usd = round((local_lifetime_tokens / 1_000_000.0) * 3.50, 4)

        kpis = {
            "minute_burn_rate": minute_burn,
            "current_hour_tokens": hour_tokens,
            "last_24h_tokens": total_24h_tokens,
            "last_24h_requests": total_24h_requests,
            "last_24h_cache_hit_rate": self._calc_cache_hit(total_24h_cache, total_24h_inp),
            "last_24h_avg_per_request": round(total_24h_tokens / total_24h_requests) if total_24h_requests > 0 else 0,
            "lifetime_tokens": total_lifetime_tokens,
            "lifetime_requests": total_lifetime_requests,
            "lifetime_cache_hit_rate": self._calc_cache_hit(total_lifetime_cache, total_lifetime_inp),
            "local_tokens_offloaded": local_lifetime_tokens,
            "local_24h_tokens": local_24h_tokens,
            "local_24h_requests": local_24h_requests,
            "estimated_cost_saved_usd": saved_usd,
            "local_offload_percent": local_offload_pct,
            "as_of": now_dt.strftime("%Y-%m-%d %H:%M:%S SAST"),
        }

        result = {
            "success": True,
            "kpis": kpis,
            "series": {
                "minute": minute_series,
                "hourly": hourly_series,
                "daily": daily_series,
                "monthly": monthly_series,
                "yearly": yearly_series,
            },
            "recent_sessions": sessions_list[:25],
        }
        self._cached_telemetry = result
        self._cached_time = time.time()
        return result

_ENGINE_INSTANCE = None

def get_telemetry_engine() -> TokenTelemetryEngine:
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = TokenTelemetryEngine()
    return _ENGINE_INSTANCE
