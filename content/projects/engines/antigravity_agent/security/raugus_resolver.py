"""
DevCore Raugus Resolver Module.
Imports from installed raugus_core package when available, with full transparent local fallback.
"""
try:
    from raugus_core.resolver import (
        RaugusResolver,
        resolver,
        normalize_cross_platform_path,
        discover_onedrive_roots,
        is_path_in_onedrive,
        is_onedrive_sync_root,
        get_path_inode,
        is_sensitive_inode,
        _SENS_INO_CACHE,
        _OD_CACHE,
        _DEVCORE_ENGINE_ROOT,
        ONEDRIVE_GUID_MARKER
    )
except ImportError:
    import json
    import os
    import logging

    class RaugusResolver:
        def __init__(self, map_file="raugus_map.json", redis_url=None):
            # Resolve path relative to this script to ensure it always finds the map
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.map_file = os.path.join(base_dir, map_file)
            self.phonebook = {}

            # [REDIS MIGRATION PLACEHOLDER]
            # Future architecture will shift to Redis to fully decouple the security map
            # from the local Python memory state.
            # self.redis_client = None
            # if redis_url:
            #     import redis
            #     self.redis_client = redis.from_url(redis_url, decode_responses=True)
            #     self._seed_redis_map()
            # else:
            self._load_phonebook()

        def _load_phonebook(self):
            if os.path.exists(self.map_file):
                with open(self.map_file, 'r') as f:
                    self.phonebook = json.load(f)

                # DYNAMIC PATH CORRECTION FOR COMPILED EXECUTABLES:
                # We recalculate the real_path based on the current executable's root directory,
                # ignoring the hardcoded machine paths from when the map was generated.
                current_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                for alias, data in self.phonebook.items():
                    if alias.startswith("devcore."):
                        old_path = data.get("real_path", "")
                        if "DevCore" in old_path:
                            parts = old_path.split("DevCore")
                            rel_path = parts[-1].lstrip("\\/")
                            data["real_path"] = os.path.join(current_root, rel_path)

                logging.info(f"[RAUGUS] Loaded and dynamically patched {len(self.phonebook)} aliases from {self.map_file}")
            else:
                logging.error(f"[RAUGUS FATAL] Raugus Map not found at {self.map_file}")

        def get_path(self, alias, user_tier):
            """
            Resolves an alias to a physical path, enforcing RBAC Tiers.
            Returns the physical_path if authorized.
            Raises KeyError if alias is invalid (Blocks Path Traversal).
            Raises PermissionError if Tier is too low.
            """
            if alias not in self.phonebook:
                logging.warning(f"[RAUGUS BLOCKED] Invalid alias requested: {alias}. Potential traversal attack.")
                raise KeyError(f"Alias '{alias}' does not exist in the Raugus Map.")

            entry = self.phonebook[alias]
            required_tier = entry.get("required_tier", 5)

            if user_tier < required_tier:
                logging.warning(f"[RAUGUS DENIED] Tier {user_tier} attempted to access Tier {required_tier} alias '{alias}'.")
                raise PermissionError(f"Access Denied. Tier {required_tier} clearance required.")

            logging.info(f"[RAUGUS APPROVED] Alias '{alias}' resolved for Tier {user_tier}.")
            real_path = entry.get("real_path")
            if not real_path or not os.path.exists(real_path):
                base_dir = os.path.dirname(os.path.abspath(__file__)) # security folder
                devcore_root = os.path.dirname(base_dir) # DevCore root or bundle root
                if "Documents/DevCore/" in real_path:
                    rel = real_path.split("Documents/DevCore/")[-1].replace("/", os.sep)
                elif "/DevCore/" in real_path:
                    rel = real_path.split("/DevCore/")[-1].replace("/", os.sep)
                else:
                    rel = os.path.basename(real_path)
                candidate = os.path.normpath(os.path.join(devcore_root, rel))
                if os.path.exists(candidate):
                    return candidate
                cwd_candidate = os.path.normpath(os.path.join(os.getcwd(), rel))
                if os.path.exists(cwd_candidate):
                    return cwd_candidate
            return real_path

        def enforce_path_security(self, path: str, user_tier: int):
            """
            Evaluates a physical path against the Raugus Map.
            Raises PermissionError if the user's tier is too low to access it.
            """
            target_path = os.path.abspath(path)

            highest_tier_required = 1  # Default to Safe Workspace

            for alias, data in self.phonebook.items():
                real_path = os.path.abspath(data.get("real_path", ""))
                if target_path == real_path or target_path.startswith(real_path + os.sep):
                    req_tier = data.get("required_tier", 1)
                    if req_tier > highest_tier_required:
                        highest_tier_required = req_tier

            if user_tier < highest_tier_required:
                logging.error(f"[RAUGUS INTRUSION] Tier {user_tier} attempted to access Tier {highest_tier_required} asset: {target_path}")
                raise PermissionError(f"Raugus Semantic Firewall: Access Denied to Tier {highest_tier_required} asset.")

            return True

        def enforce_feedback_policy(self, path: str):
            """
            Queries the Raugus map to determine if a file is allowed to request execution feedback.
            Blocks feedback requests on documentation, text files, and markdown.
            """
            if not path:
                return

            target_path = os.path.abspath(path)

            # Query the map for the physical path
            for alias, data in self.phonebook.items():
                real_path = os.path.abspath(data.get("real_path", ""))

                # If the file matches exactly, or is inside a mapped directory
                if target_path == real_path or target_path.startswith(real_path + os.sep):
                    # Block if it's in the docs directory, or is a markdown file
                    if ".docs." in alias or "devlog" in alias.lower() or alias.endswith(".md") or "textbook" in alias.lower() or "module" in alias.lower():
                        raise PermissionError(f"Raugus Firewall: Alias '{alias}' is classified as documentation. RequestFeedback=True is strictly forbidden.")

            return True

        def is_sensitive_path(self, path: str) -> bool:
            """
            Checks if a physical path (or any of its parent directories) is marked
            with `"sensitive": true` in the Raugus Map, resides inside any
            automatically detected OneDrive sync root, OR matches a sensitive
            hardware inode (even if the folder or file was renamed).
            """
            if not path:
                return False
            target_path = normalize_cross_platform_path(path)
            if is_path_in_onedrive(target_path):
                return True
            if is_sensitive_inode(target_path, self.phonebook):
                return True
            for alias, data in self.phonebook.items():
                if data.get("sensitive") is True:
                    real_path = os.path.abspath(data.get("real_path", ""))
                    if target_path == real_path or target_path.startswith(real_path + os.sep):
                        return True
            return False

        def get_block_by_tag(self, tag_or_id: str, user_tier: int = 5) -> dict:
            """
            Resolves an AST symbol or Markdown section block by its persistent invariant UUID (`id`)
            or symbol/section tag name (e.g. `SEC_01_OVERVIEW` or `reload_system`),
            enforcing RBAC tier clearance. Returns the entry dict with key or None.
            """
            if not tag_or_id:
                return None
            # 1. Direct match by UUID
            for k, entry in self.phonebook.items():
                if entry.get("id") == tag_or_id:
                    req_tier = int(entry.get("required_tier", 5))
                    if int(user_tier) < req_tier:
                        raise PermissionError(f"Access Denied to tag '{tag_or_id}'. Tier {req_tier} required.")
                    res = dict(entry)
                    res["key"] = k
                    return res

            # 2. Match by symbol_name or section tag
            for k, entry in self.phonebook.items():
                if entry.get("symbol_name") == tag_or_id or k.endswith(f"::{tag_or_id}"):
                    req_tier = int(entry.get("required_tier", 5))
                    if int(user_tier) < req_tier:
                        raise PermissionError(f"Access Denied to symbol/section '{tag_or_id}'. Tier {req_tier} required.")
                    res = dict(entry)
                    res["key"] = k
                    return res

            return None


    ONEDRIVE_GUID_MARKER = ".849C9593-D756-4E56-8D6E-42412F2A707B"
    _DEVCORE_ENGINE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


    def get_path_inode(path: str) -> int:
        """
        Returns the 64-bit OS/NTFS Master File Table inode (st_ino) for a path, or 0 if non-existent.
        """
        if not path:
            return 0
        try:
            return int(os.stat(normalize_cross_platform_path(path)).st_ino)
        except Exception:
            return 0


    _SENS_INO_CACHE = None

    def is_sensitive_inode(path: str, phonebook: dict = None) -> bool:
        """
        Walks `path` and its existing ancestor directories and compares their hardware
        inodes (`st_ino`) against all sensitive entries in `phonebook`.
        Prevents bypassing vault protection by renaming or moving a sensitive folder.
        """
        global _SENS_INO_CACHE
        if not path:
            return False
        if _SENS_INO_CACHE is None:
            s_inodes = set()
            if phonebook:
                for data in phonebook.values():
                    if data.get("sensitive") is True:
                        ino = data.get("inode", 0)
                        if ino:
                            s_inodes.add(int(ino))
                        rp = data.get("real_path", "")
                        if rp:
                            live_ino = get_path_inode(rp)
                            if live_ino:
                                s_inodes.add(live_ino)
            for od_root in discover_onedrive_roots():
                od_ino = get_path_inode(od_root)
                if od_ino:
                    s_inodes.add(od_ino)
            _SENS_INO_CACHE = s_inodes
        sensitive_inodes = _SENS_INO_CACHE

        if not sensitive_inodes:
            return False

        curr = normalize_cross_platform_path(path)
        stop_dirs = {"/", "/mnt", "/mnt/c", "/mnt/c/Users", "/home", _DEVCORE_ENGINE_ROOT}
        for _ in range(15):
            if not curr or curr in stop_dirs:
                break
            ino = get_path_inode(curr)
            if ino and ino in sensitive_inodes:
                return True
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent

        return False


    def normalize_cross_platform_path(path: str) -> str:
        """
        Normalizes Windows paths (e.g. C:\\Users\\... or C:/Users/...) and POSIX/WSL paths
        into canonical absolute paths on the current OS.
        """
        if not path:
            return ""
        s = path.strip().strip("'\"")
        if os.name == "posix" and len(s) >= 3 and s[0].isalpha() and s[1] == ":" and s[2] in ("\\", "/"):
            drive = s[0].lower()
            rest = s[3:].replace("\\", "/")
            return os.path.abspath(f"/mnt/{drive}/{rest}")
        return os.path.abspath(s)


    def is_onedrive_sync_root(dir_path: str) -> bool:
        """
        Detects whether a directory is a OneDrive sync root regardless of what it is named:
        1. Folder name contains 'onedrive' (case-insensitive)
        2. Contains Microsoft OneDrive's universal sync-root GUID marker (.849C9593-D756-4E56-8D6E-42412F2A707B)
        3. Contains a desktop.ini referencing OneDrive.exe
        Never classifies the DevCore engine root itself as a OneDrive root.
        """
        if not dir_path:
            return False
        norm_dir = normalize_cross_platform_path(dir_path)
        if norm_dir == _DEVCORE_ENGINE_ROOT or norm_dir.startswith(_DEVCORE_ENGINE_ROOT + os.sep):
            return False
        base = os.path.basename(norm_dir).lower()
        if "onedrive" in base:
            return True
        if not os.path.isdir(norm_dir):
            return False
        if os.path.exists(os.path.join(norm_dir, ONEDRIVE_GUID_MARKER)):
            return True
        desktop_ini = os.path.join(norm_dir, "desktop.ini")
        if os.path.isfile(desktop_ini):
            try:
                with open(desktop_ini, "rb") as f:
                    raw = f.read(1024)
                text = raw.decode("utf-8", errors="ignore") + raw.decode("utf-16", errors="ignore")
                if "onedrive" in text.lower():
                    return True
            except Exception:
                pass
        return False


    _OD_CACHE = None
    def discover_onedrive_roots() -> list:
        global _OD_CACHE
        if _OD_CACHE is not None: return _OD_CACHE
        """
        Automatically discovers all OneDrive folders on the machine across user profiles
        and environment variables, even if custom-named.
        """
        roots = set()
        users_base = "/mnt/c/Users"
        skip_users = {"All Users", "Default", "Default User", "Public", "desktop.ini"}
        if os.path.isdir(users_base):
            try:
                for user_entry in os.listdir(users_base):
                    if user_entry in skip_users:
                        continue
                    user_dir = os.path.join(users_base, user_entry)
                    if not os.path.isdir(user_dir):
                        continue
                    try:
                        for sub in os.listdir(user_dir):
                            sub_path = os.path.join(user_dir, sub)
                            if os.path.isdir(sub_path) and is_onedrive_sync_root(sub_path):
                                roots.add(os.path.abspath(sub_path))
                    except Exception:
                        continue
            except Exception:
                pass
        for env_key in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer", "ONEDRIVE"):
            val = os.environ.get(env_key)
            if val:
                norm_val = normalize_cross_platform_path(val)
                if os.path.isdir(norm_val):
                    roots.add(norm_val)
        _OD_CACHE = sorted(roots); return _OD_CACHE


    def is_path_in_onedrive(path: str):
        """
        Returns the normalized path if `path` is inside any OneDrive directory
        (matched via discovered roots, parent-directory marker inspection, or path segments),
        otherwise None.
        """
        if not path:
            return None
        norm_p = normalize_cross_platform_path(path)
        if norm_p == _DEVCORE_ENGINE_ROOT or norm_p.startswith(_DEVCORE_ENGINE_ROOT + os.sep):
            return None

        for root in discover_onedrive_roots():
            if norm_p == root or norm_p.startswith(root + os.sep):
                return norm_p

        curr = norm_p
        stop_dirs = {"/", "/mnt", "/mnt/c", "/mnt/c/Users", "/home"}
        for _ in range(15):
            if not curr or curr in stop_dirs:
                break
            if is_onedrive_sync_root(curr):
                return norm_p
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent

        return None


    # Singleton instance for the application to import
    resolver = RaugusResolver()
