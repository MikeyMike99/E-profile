import importlib
from .mixins import comms_mixin as _cm_mod
from .mixins import execution_mixin as _em_mod
from .mixins import transcript_mixin as _tm_mod

importlib.reload(_cm_mod)
importlib.reload(_em_mod)
importlib.reload(_tm_mod)

from .mixins.comms_mixin import CommsMixin
from .mixins.execution_mixin import ExecutionMixin
from .mixins.transcript_mixin import TranscriptMixin
import logging
import asyncio
import json
import os
import time
import sys
import shutil
import random
import re
import traceback

def _find_existing_agent_mgr():
    for mod_name in ("__main__", "core.server"):
        mod = sys.modules.get(mod_name)
        if mod is not None:
            mgr = getattr(mod, "agent_mgr", None)
            if mgr is not None:
                return mgr
            app_obj = getattr(mod, "app", None)
            if app_obj is not None and getattr(app_obj, "agent_mgr", None) is not None:
                return app_obj.agent_mgr
    return None

class AgentTaskManager(CommsMixin, ExecutionMixin, TranscriptMixin):
    """
    Manages Antigravity background tasks independently of client WebSocket connections.
    Uses an ACK-backed message queue to guarantee zero message loss:
      - Every event is assigned a monotonic sequence number (seq).
      - All broadcast events are retained in a server buffer until explicitly ACKed by the client.
      - Reconnecting clients can replay all unacknowledged events seamlessly.
      - Periodic heartbeats prevent connection drops on WSL 2 and high-latency networks.
    """
    def __new__(cls, *args, **kwargs):
        existing = _find_existing_agent_mgr()
        if existing is not None:
            existing.__class__ = cls
            return existing
        return super().__new__(cls)

    def __init__(self, project_manager=None):
        if getattr(self, "_initialized", False):
            if project_manager is not None:
                self.project_manager = project_manager
            if not hasattr(self, "queued_prompts") or self.queued_prompts is None:
                self.queued_prompts = []
            if not hasattr(self, "_steering_interrupt"):
                self._steering_interrupt = False
            if not hasattr(self, "_steer_lock") or self._steer_lock is None:
                self._steer_lock = asyncio.Lock()
            if not hasattr(self, "last_user"):
                self.last_user = None
            if not hasattr(self, "last_admin_override"):
                self.last_admin_override = False
            return

        self._initialized = True
        self.project_manager = project_manager
        self.active_task: asyncio.Task = None
        self.active_proc: asyncio.subprocess.Process = None
        self.current_prompt: str = None
        self.current_model: str = "Gemini 3.8 Flash (Low)"
        self.start_time: float = None
        self.output_buffer: list = []
        self.actions: list = []
        self.last_completed_task: dict = None
        self.connected_clients: dict = {}
        self.active_task_owner: str = None
        self.current_conversation_id: str = None

        self.queued_prompts: list = []
        self._steering_interrupt: bool = False
        self._steer_lock: asyncio.Lock = asyncio.Lock()
        self.last_user: dict = None
        self.last_admin_override: bool = False

        self.current_seq: int = 0
        self.message_queue: list = []
        self.max_queue_size: int = 1000
        self._lock = asyncio.Lock()
        self._local_sec = None

        self.rate_limits = {}

    @property
    def active_task_id(self):
        return self.active_task

    @active_task_id.setter
    def active_task_id(self, val):
        self.active_task = val

    def reinit(self, project_manager=None):
        """Re-initializes state while preserving client connections and pending queue."""
        if project_manager:
            self.project_manager = project_manager
        self.output_buffer = []
        self.actions = []
        if not hasattr(self, "queued_prompts") or self.queued_prompts is None:
            self.queued_prompts = []
        if not hasattr(self, "_steering_interrupt"):
            self._steering_interrupt = False
        if not hasattr(self, "_steer_lock") or self._steer_lock is None:
            self._steer_lock = asyncio.Lock()

    def is_running(self) -> bool:
        return self.active_proc is not None and self.active_proc.returncode is None

_live_mgr = _find_existing_agent_mgr()
if _live_mgr is not None:
    _live_mgr.__class__ = AgentTaskManager
    _live_mgr._initialized = True
    if not hasattr(_live_mgr, "queued_prompts") or _live_mgr.queued_prompts is None:
        _live_mgr.queued_prompts = []
    if not hasattr(_live_mgr, "_steering_interrupt"):
        _live_mgr._steering_interrupt = False
    if not hasattr(_live_mgr, "_steer_lock") or _live_mgr._steer_lock is None:
        _live_mgr._steer_lock = asyncio.Lock()
    if not hasattr(_live_mgr, "last_user"):
        _live_mgr.last_user = None
    if not hasattr(_live_mgr, "last_admin_override"):
        _live_mgr.last_admin_override = False
