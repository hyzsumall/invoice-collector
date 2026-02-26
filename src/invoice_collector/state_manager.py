"""已处理邮件状态管理（去重 + 断点续传）"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("~/invoice-collector/state.json").expanduser()


class StateManager:
    def __init__(self, state_path: Path | None = None):
        self.path = state_path or DEFAULT_STATE_PATH
        self._state: dict = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"state.json读取失败，从空状态开始: {e}")
                self._state = {}

    def _save(self):
        """原子写：先写.tmp再rename"""
        tmp = self.path.with_suffix(".json.tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
        tmp.rename(self.path)

    def is_processed(self, uid: str) -> bool:
        return uid in self._state

    def get_processed_uids(self) -> set[str]:
        return set(self._state.keys())

    def mark_done(self, uid: str, subject: str, output_files: list[str]):
        self._state[uid] = {
            "subject": subject,
            "processed_at": datetime.now().isoformat(),
            "output_files": output_files,
            "status": "done",
        }
        self._save()

    def mark_failed(self, uid: str, subject: str, reason: str):
        self._state[uid] = {
            "subject": subject,
            "processed_at": datetime.now().isoformat(),
            "output_files": [],
            "status": "failed",
            "reason": reason,
        }
        self._save()

    def summary(self) -> dict:
        done = sum(1 for v in self._state.values() if v["status"] == "done")
        failed = sum(1 for v in self._state.values() if v["status"] == "failed")
        return {"total": len(self._state), "done": done, "failed": failed}
