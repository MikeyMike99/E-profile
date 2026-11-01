import json
import mimetypes
import os
import socket
import time
import uuid

class SecurityManager:
    """
    Role-Based Access Control (RBAC) and Path Sandboxing for In-Game Development.
    
    Roles:
      - 'admin': Full access to all projects, core engine scripts, and system logs.
      - 'gamedev': Restricted to assigned game project folders. Cannot view core scripts, logs, or parent paths.
      - 'modder': Read-only access to safe workspace files inside assigned projects.
      
    Tiers:
      - SAFE_WORKSPACE: Game scripts, configs, JSON states, Lua scripts (Read/Write for devs)
      - CORE_ENGINE: Orchestration, server, and security scripts (Admin only)
      - ADMIN_LOG: System and daemon execution logs (Admin only)
      - FORBIDDEN: System files, venv, git, env vars, traversal attempts (Hard blocked)
    """

    ROLE_ADMIN = "admin"
    ROLE_GAMEDEV = "gamedev"
    ROLE_MODDER = "modder"

    TIER_SAFE_WORKSPACE = "safe_workspace"
    TIER_CORE_ENGINE = "core_engine"
    TIER_ADMIN_LOG = "admin_log"
    TIER_FORBIDDEN = "forbidden"

    FILES_CACHE_TTL_SECONDS = 15.0

    @staticmethod
    def check_master_signature() -> bool:
        """
        Cryptographically verifies if this application is running on Michael's physical machine.
        Reads the local .devcore_master.key and compares its SHA-256 hash to the expected value.
        This prevents reverse-engineers from finding the raw key in the compiled executable.
        """
        import hashlib
        key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".devcore_master.key"))
        
        if not os.path.exists(key_path):
            return False
            
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                raw_key = f.read().strip()
                
            EXPECTED_HASH = "80fbad65507294b850a67db5e7f915f40390c8d10dbfca1a3e08a624523904d6"
            actual_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
            
            return actual_hash == EXPECTED_HASH
        except Exception as e:
            print(f"[Security] Failed to verify master signature: {e}")
            return False

    CORE_FILES = {
        "server.py", "agent_manager.py", "project_manager.py",
        "session_manager.py", "security_manager.py", "apply_upgrade.sh",
        "server_new.py", "test.js", "test_ws.py"
    }

    CORE_DIRECTORIES = {
        "core", "security", "sandbox", "plugins", "docs", 
        "archives", "backups", "scripts"
    }

    ALLOWED_EXTENSIONS = {
        ".py", ".json", ".lua", ".js", ".ts", ".md", ".txt",
        ".yaml", ".yml", ".xml", ".csv", ".ini", ".cfg", ".log", ".html", ".css"
    }

    FORBIDDEN_NAMES = {"venv", "__pycache__", ".git", ".env", ".system_generated"}

    PACKAGE_ARTIFACT_DIRS = {
        "Cryptodome", "pyzipper", "node_modules", "site-packages",
        "Zip-Files", "Offline_Crack_Lab", "Online_Brute_Lab"
    }

    # Low-privilege fixture logins for local testing only. Disabled unless
    # DEVCORE_ENABLE_TEST_USERS=1, since their passwords are public. There is
    # deliberately no admin test user: admin access comes from an access key or
    # the host-owner login (master key + loopback request).
    TEST_USERS = {
        "dev": {
            "password": "dev",
            "role": ROLE_GAMEDEV,
            "name": "Game Developer",
            "allowed_projects": ["game_demo", "npc_quest"]
        },
        "dev_tester": {
            "password": "dev",
            "role": ROLE_GAMEDEV,
            "name": "Game Developer",
            "allowed_projects": ["game_demo", "npc_quest"]
        },
        "mod": {
            "password": "mod",
            "role": ROLE_MODDER,
            "name": "Community Modder",
            "allowed_projects": ["game_demo"]
        },
        "modder": {
            "password": "mod",
            "role": ROLE_MODDER,
            "name": "Community Modder",
            "allowed_projects": ["game_demo"]
        }
    }

    OWNER_KEY_ID = "owner"
    OWNER_USER = {
        "username": "Michael (Admin)",
        "role": "super_admin",
        "name": "Michael (Admin)",
        "allowed_projects": ["*"],
        "token_scope": "root",
        "key_id": "owner",
    }
    SESSION_TTL_SECONDS = {"admin": 7 * 86400, "user": 7 * 86400, "demo": 86400}

    _LOOPBACK_PREFIXES = ("127.", "::1", "::ffff:127.")
    _FORWARD_HEADERS = ("X-Forwarded-For", "Forwarded", "X-Real-IP", "CF-Connecting-IP", "True-Client-IP")
    _host_ip_cache = None  # (set_of_ips, expires_at)

    @classmethod
    def _host_local_ips(cls) -> set:
        """This machine's own IP addresses. A request whose source address is one
        of these is coming *from this host* even when it was aimed at the LAN IP
        (e.g. http://172.29.x.x:5000) rather than loopback. Cached for 60s because
        resolution touches the network stack. A different machine on the LAN has a
        different source IP and is still rejected."""
        now = time.time()
        if cls._host_ip_cache and cls._host_ip_cache[1] > now:
            return cls._host_ip_cache[0]
        ips = set()
        try:
            hostname = socket.gethostname()
            for fam in (socket.AF_INET, socket.AF_INET6):
                try:
                    for info in socket.getaddrinfo(hostname, None, fam):
                        ip = info[4][0].split("%")[0]  # strip IPv6 zone id
                        if ip:
                            ips.add(ip)
                except Exception:
                    pass
        except Exception:
            pass
        cls._host_ip_cache = (ips, now + 60.0)
        return ips

    @staticmethod
    def _is_wsl() -> bool:
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
            return True
        try:
            with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                return "microsoft" in f.read().lower()
        except Exception:
            return False

    @classmethod
    def _wsl_host_gateway_ips(cls) -> set:
        """When the server runs inside WSL, the Windows host (the owner's actual
        machine) reaches it through the WSL NAT and always arrives as the default
        gateway address. Trusting that gateway lets owner auto-login work from the
        Windows browser without a hardcoded, reboot-fragile IP. Empty off WSL, so
        a real LAN gateway/router is never implicitly trusted."""
        if not cls._is_wsl():
            return set()
        gws = set()
        try:
            # /proc/net/route: default route has Destination 00000000; Gateway is
            # a little-endian hex IPv4.
            with open("/proc/net/route", "r", encoding="utf-8") as f:
                next(f, None)  # header
                for line in f:
                    parts = line.split()
                    if len(parts) > 2 and parts[1] == "00000000":
                        g = int(parts[2], 16)
                        gws.add("%d.%d.%d.%d" % (g & 0xff, (g >> 8) & 0xff, (g >> 16) & 0xff, (g >> 24) & 0xff))
        except Exception:
            pass
        return gws

    @classmethod
    def is_trusted_local_request(cls, remote_addr, headers=None) -> bool:
        """True only for a direct connection from this machine, with no proxy
        forwarding headers. The master key proves the *server* is the owner's
        machine; this proves the *client* is too. Both of the host's own entry
        points count: loopback (127.x / ::1 / localhost) AND the machine's own
        LAN IP addresses. Extra trusted addresses can be listed in
        DEVCORE_TRUSTED_HOST_IPS (comma-separated)."""
        addr = str(remote_addr or "").strip()
        if not addr:
            return False
        if headers is not None:
            for h in cls._FORWARD_HEADERS:
                try:
                    if headers.get(h):
                        return False
                except Exception:
                    return False
        if addr == "localhost" or addr.startswith(cls._LOOPBACK_PREFIXES):
            return True
        extra = {a.strip() for a in os.environ.get("DEVCORE_TRUSTED_HOST_IPS", "").split(",") if a.strip()}
        if addr in extra:
            return True
        # Normalise an IPv4-mapped IPv6 source (::ffff:172.29.x.x) to its v4 form.
        bare = addr[7:] if addr.startswith("::ffff:") else addr
        host_ips = cls._host_local_ips() | cls._wsl_host_gateway_ips()
        return addr in host_ips or bare in host_ips

    def is_host_owner_request(self, remote_addr, headers=None) -> bool:
        """Master key present on the server AND the request comes from this machine."""
        return self.is_trusted_local_request(remote_addr, headers) and self.check_master_signature()

    def create_session(self, user: dict, kind: str = "user") -> dict:
        """Issue a fresh random bearer token for `user`. Only the SHA-256 of the
        token is stored, so sessions.json never holds a usable credential."""
        import hashlib
        token = "sec-" + uuid.uuid4().hex + uuid.uuid4().hex
        now = time.time()
        is_admin = self.is_admin_user(user)
        ttl = self.SESSION_TTL_SECONDS.get(kind) or self.SESSION_TTL_SECONDS["user"]
        session_data = {
            "username": user.get("username") or user.get("name", "Unknown"),
            "role": user.get("role", "guest"),
            "name": user.get("name", "Unknown"),
            "allowed_projects": user.get("allowed_projects", []),
            "key_id": user.get("key_id") or ("test-" + str(user.get("name", "user"))),
            "created_at": now,
            "expires_at": now + ttl,
            "token_scope": "demo" if kind == "demo" else ("root" if is_admin else "user"),
        }
        self.sessions[hashlib.sha256(token.encode()).hexdigest()] = session_data
        self._save_sessions()
        return {"token": token, "user": dict(session_data)}

    def create_owner_session(self) -> dict:
        return self.create_session(dict(self.OWNER_USER), kind="admin")

    def __init__(self, base_dir=None):
        import sys
        if hasattr(sys, 'frozen') or '__compiled__' in globals() or getattr(sys, 'frozen', False):
            persist_dir = os.path.dirname(sys.executable)
        else:
            persist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        self.base_dir = base_dir or persist_dir
        self.sessions = {}
        self.sessions_file = os.path.join(self.base_dir, "sessions.json")
        self.keys_file = os.path.join(self.base_dir, "keys.json")
        self.keys = {}
        self._local_sec = None
        self._files_cache = {}
        self._load_sessions()
        self._load_keys()

    def invalidate_files_cache(self):
        if hasattr(self, "_files_cache") and isinstance(self._files_cache, dict):
            self._files_cache.clear()

    def _get_security(self):
        if self._local_sec is None:
            try:
                from security.local_security import LocalSecurity
                self._local_sec = LocalSecurity()
            except Exception as e:
                print(f"[Security] LocalSecurity init failed. Error: {e}")
                class Dummy:
                    def scrub_text(self, t): return t
                self._local_sec = Dummy()
        return self._local_sec

    @staticmethod
    def _is_hashed_session_key(k: str) -> bool:
        return isinstance(k, str) and len(k) == 64 and all(c in "0123456789abcdef" for c in k)

    def _load_sessions(self):
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception:
                loaded = {}
            # Drop legacy raw-token sessions (incl. the old shared
            # 'sec-root-owner-permanent' admin token) and anything expired.
            now = time.time()
            self.sessions = {
                k: v for k, v in (loaded or {}).items()
                if self._is_hashed_session_key(k) and isinstance(v, dict)
                and float(v.get("expires_at") or 0) > now
            }
            if len(self.sessions) != len(loaded or {}):
                self._save_sessions()

    def _save_sessions(self):
        try:
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f)
        except Exception:
            pass

    def reinit(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.invalidate_files_cache()
        self._load_sessions()

    def authenticate(self, access_key, password=None):
        """Authenticates a user using an access key or credentials pair and issues a bearer session token."""
        if password is not None:
            access_key = f"{access_key}:{password}"
        user = self.keys.get(access_key)
        
        if not user:
            from werkzeug.security import check_password_hash
            for stored_key, metadata in self.keys.items():
                if stored_key.startswith("scrypt:") or stored_key.startswith("pbkdf2:"):
                    if check_password_hash(stored_key, access_key):
                        user = metadata
                        user["hashed_key_ref"] = stored_key
                        break
                        
        if user and "expires_in_days" in user and user["expires_in_days"] is not None:
            expiration_time = user["created_at"] + (user["expires_in_days"] * 86400)
            if time.time() > expiration_time:
                print(f"[Security] Access key {access_key} has expired.")
                self.delete_key(user.get("hashed_key_ref", access_key))
                return None
        
        if (not user and access_key and ":" in access_key
                and os.environ.get("DEVCORE_ENABLE_TEST_USERS") == "1"):
            username, password = access_key.split(":", 1)
            test_user = self.TEST_USERS.get(username)
            if test_user and test_user["password"] == password:
                user = dict(test_user)
                user["key_id"] = "test-" + username

        # NOTE: no magic access keys. 'SUPER_ADMIN_AUTO' / 'sec-root…' used to log
        # anyone in as super-admin; the host-owner login now lives in the route
        # layer, where the client address can be checked (create_owner_session).
        if not user:
            return None

        return self.create_session(user, kind="admin" if self.is_admin_user(user) else "user")

    def _load_keys(self):
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, "r", encoding="utf-8") as f:
                    self.keys = json.load(f)
            except Exception as e:
                print(f"[Security] Error loading keys: {e}")
                self.keys = {}
        else:
            self.keys = {}
        # Every key needs a stable, non-secret id so access grants can name it.
        changed = False
        for meta in self.keys.values():
            if isinstance(meta, dict) and not meta.get("key_id"):
                meta["key_id"] = "kid-" + uuid.uuid4().hex[:12]
                changed = True
        if changed:
            self._save_keys()

    def list_principals(self) -> list:
        """Non-secret view of access keys, for the grant UI."""
        out = []
        for meta in self.keys.values():
            if not isinstance(meta, dict):
                continue
            out.append({
                "key_id": meta.get("key_id"),
                "name": meta.get("name"),
                "role": meta.get("role"),
                "created_at": meta.get("created_at"),
                "expires_in_days": meta.get("expires_in_days"),
            })
        return out

    def _save_keys(self):
        try:
            with open(self.keys_file, "w", encoding="utf-8") as f:
                json.dump(self.keys, f, indent=4)
        except Exception as e:
            print(f"[Security] Error saving keys: {e}")

    def generate_key(self, role, name, allowed_projects=None, expires_in_days=30):
        new_key = "key-" + uuid.uuid4().hex
        from werkzeug.security import generate_password_hash
        hashed_key = generate_password_hash(new_key)
        
        if allowed_projects is None:
            if role in [self.ROLE_ADMIN, "super_admin"]:
                allowed_projects = ["*"]
            else:
                allowed_projects = []
                
        self.keys[hashed_key] = {
            "role": role,
            "name": name,
            "allowed_projects": allowed_projects,
            "created_at": time.time(),
            "expires_in_days": expires_in_days,
            "hashed_key_ref": hashed_key,
            "key_id": "kid-" + uuid.uuid4().hex[:12],
        }
        self._save_keys()
        return new_key

    def delete_key(self, key_to_delete):
        if key_to_delete in self.keys:
            del self.keys[key_to_delete]
            self._save_keys()
            return True
        return False

    def get_all_keys(self):
        return self.keys

    def get_user_from_token(self, token, remote_addr=None, headers=None):
        """Resolve a bearer token to its session. With no valid token, falls back to
        the host owner ONLY for a direct loopback request on the master-key machine
        (pass remote_addr/headers); otherwise returns None."""
        user = None
        if token:
            hashed_session = __import__("hashlib").sha256(str(token).encode()).hexdigest()
            sess = self.sessions.get(hashed_session)
            if sess and float(sess.get("expires_at") or 0) > time.time():
                user = dict(sess)
            elif sess:
                self.sessions.pop(hashed_session, None)
                self._save_sessions()
        if not user and remote_addr is not None and self.is_host_owner_request(remote_addr, headers):
            user = dict(self.OWNER_USER)
            user["auth_method"] = "host_owner"
        return user

    def logout(self, token):
        hashed_session = __import__("hashlib").sha256(token.encode()).hexdigest()
        if hashed_session in self.sessions:
            del self.sessions[hashed_session]
            self._save_sessions()
        elif token in self.sessions:
            del self.sessions[token]
            self._save_sessions()
            return True
        return False

    def is_admin_user(self, user):
        return bool(user and user.get("role") in (self.ROLE_ADMIN, "super_admin", "super admin", "Tier5_SysAdmin"))

    def can_access_project(self, user, project_name):
        if not user:
            return False
        if self.is_admin_user(user):
            return True
        if not project_name:
            return False
        return ("*" in user.get("allowed_projects", [])) or (project_name in user.get("allowed_projects", []))

    def can_view_logs(self, user):
        return self.is_admin_user(user)

    def can_reload_engine(self, user):
        return self.is_admin_user(user)

    def classify_file(self, rel_path: str) -> str:
        norm_path = os.path.normpath(rel_path).replace("\\", "/")
        parts = norm_path.split("/")

        for p in parts[:-1]:
            if p in self.FORBIDDEN_NAMES or p in self.PACKAGE_ARTIFACT_DIRS or p.startswith(".") or p.endswith((".dist-info", ".egg-info")):
                return self.TIER_FORBIDDEN
            if p in self.CORE_DIRECTORIES:
                return self.TIER_CORE_ENGINE
                
        final_part = parts[-1]
        if final_part in self.FORBIDDEN_NAMES or final_part.startswith("."):
            return self.TIER_FORBIDDEN

        filename = os.path.basename(norm_path)
        if filename in self.CORE_FILES:
            return self.TIER_CORE_ENGINE

        if filename.endswith(".log"):
            return self.TIER_ADMIN_LOG

        _, ext = os.path.splitext(filename)
        if ext.lower() in self.ALLOWED_EXTENSIONS or ext == "":
            return self.TIER_SAFE_WORKSPACE

        return self.TIER_FORBIDDEN

    def resolve_safe_path(self, target_base: str, rel_path: str, user: dict = None) -> str:
        """Enforces absolute sandbox boundaries using realpath to prevent symlink escapes."""
        if not rel_path:
            raise ValueError("Empty file path")

        clean_rel = os.path.normpath(rel_path).lstrip("/\\")
        if clean_rel.startswith("..") or "/../" in clean_rel or "\\..\\" in clean_rel:
            raise PermissionError("Access Denied: Path traversal forbidden")

        is_admin = self.is_admin_user(user)
        if not is_admin:
            target_base = os.path.join(self.base_dir, "playground")
            os.makedirs(target_base, exist_ok=True)
        else:
            target_base = "/mnt/c/Users/michael/Documents/e_profile"
            if not os.path.exists(target_base):
                for candidate in [
                    os.path.expanduser("~/Documents/e_profile"),
                    r"C:\Users\Robert\Documents\e_profile",
                    r"C:\Users\michael\Documents\e_profile"
                ]:
                    if os.path.exists(candidate):
                        target_base = candidate
                        break
            
        real_base = os.path.realpath(target_base)
        candidate_path = os.path.join(real_base, clean_rel)

        if os.path.lexists(candidate_path):
            real_target = os.path.realpath(candidate_path)
        else:
            parent_dir = os.path.realpath(os.path.dirname(candidate_path))
            real_target = os.path.join(parent_dir, os.path.basename(candidate_path))

        if not real_target.startswith(real_base + os.sep) and real_target != real_base:
            raise PermissionError("Access Denied: Symlink or path escapes sandbox boundary")

        if user and not self.is_admin_user(user):
            tier = self.classify_file(clean_rel)
            if tier in (self.TIER_CORE_ENGINE, self.TIER_ADMIN_LOG, self.TIER_FORBIDDEN):
                raise PermissionError(f"Access Denied: Role '{user.get('role')}' cannot access {tier} files")

        return real_target

    def list_files(self, project_path: str, user: dict = None):
        """Lists files with role-aware filtering, directory pruning, and TTL caching."""
        is_admin = self.is_admin_user(user)
        is_modder = bool(user and user.get("role") == self.ROLE_MODDER)
        effective_base = project_path or self.base_dir
        cache_key = (os.path.abspath(effective_base), is_admin, is_modder)
        now = time.time()

        if not hasattr(self, "_files_cache") or self._files_cache is None:
            self._files_cache = {}

        cached_entry = self._files_cache.get(cache_key)
        if cached_entry and (now - cached_entry["ts"]) < self.FILES_CACHE_TTL_SECONDS:
            return cached_entry["items"]

        items = []

        try:
            for root, dirs, files in os.walk(effective_base):
                dirs[:] = [
                    d for d in dirs
                    if d not in self.FORBIDDEN_NAMES
                    and d not in self.PACKAGE_ARTIFACT_DIRS
                    and not d.startswith(".")
                    and not d.endswith((".dist-info", ".egg-info"))
                ]

                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, effective_base).replace("\\", "/")
                    tier = self.classify_file(rel_p)

                    if tier == self.TIER_FORBIDDEN:
                        continue

                    if not is_admin and tier in (self.TIER_CORE_ENGINE, self.TIER_ADMIN_LOG):
                        continue

                    can_read = is_admin or (tier == self.TIER_SAFE_WORKSPACE)
                    can_write = is_admin or (tier == self.TIER_SAFE_WORKSPACE and not is_modder)

                    try:
                        st = os.stat(full_p)
                        size = st.st_size
                        mtime = st.st_mtime
                    except Exception:
                        size = 0
                        mtime = 0

                    items.append({
                        "path": rel_p,
                        "name": f,
                        "size": size,
                        "mtime": mtime,
                        "tier": tier,
                        "can_read": can_read,
                        "can_write": can_write
                    })
        except Exception as e:
            print(f"[SecurityManager] Error listing files: {e}")

        items.sort(key=lambda x: (x["tier"] != self.TIER_SAFE_WORKSPACE, x["path"]))
        self._files_cache[cache_key] = {"ts": now, "items": items}
        return items

    def list_logs(self, user: dict = None):
        """Lists system logs for administrative review only."""
        if not self.can_view_logs(user):
            raise PermissionError("Access Denied: Administrator role required to view system logs")

        logs = []
        for name in ["upgrade.log", "server_stdout.log"]:
            p = os.path.join(self.base_dir, name)
            if os.path.exists(p):
                st = os.stat(p)
                logs.append({
                    "name": name,
                    "size": st.st_size,
                    "mtime": st.st_mtime
                })
        return logs

    def read_file_content(self, project_path: str, rel_path: str, user: dict = None):
        full_path = self.resolve_safe_path(project_path or self.base_dir, rel_path, user=user)
        tier = self.classify_file(rel_path)

        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"File not found: {rel_path}")

        if os.path.getsize(full_path) > 500 * 1024:
            raise ValueError("File exceeds maximum viewable size (500 KB)")

        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(full_path, flags)
        try:
            with open(fd, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            os.close(fd)
            raise

        is_admin = self.is_admin_user(user)
        is_modder = user and user.get("role") == self.ROLE_MODDER

        if not is_admin:
            try:
                sec = self._get_security()
                if sec:
                    content = sec.scrub_text(content)
            except Exception as e:
                print(f"[Security] Failed to load LocalSecurity for file redaction: {e}")
                
            content = f"<user_data_untrusted>\n{content}\n</user_data_untrusted>"

        return {
            "path": rel_path,
            "tier": tier,
            "content": content,
            "can_write": is_admin or (tier == self.TIER_SAFE_WORKSPACE and not is_modder)
        }

    def write_file_content(self, project_path: str, rel_path: str, content: str, user: dict = None):
        if user and user.get("role") == self.ROLE_MODDER:
            raise PermissionError("Access Denied: Modder role has read-only permissions")

        full_path = self.resolve_safe_path(project_path or self.base_dir, rel_path, user=user)
        tier = self.classify_file(rel_path)

        if tier == self.TIER_ADMIN_LOG:
            raise PermissionError("Access Denied: System logs are strictly read-only")

        if full_path.endswith('.lua') or full_path.endswith('.py') or full_path.endswith('.sh'):
            forbidden_calls = ['os.remove', 'os.execute', 'io.popen', 'subprocess', 'rm -rf']
            if any(call in content for call in forbidden_calls):
                raise PermissionError("Access Denied: High-risk system call detected in generated code. Write rejected.")

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(full_path, flags, 0o644)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            os.close(fd)
            raise

        self.invalidate_files_cache()
        return {"success": True, "path": rel_path, "size": len(content)}
