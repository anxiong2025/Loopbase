"""Layer 7 — 证据日志：把事件语义（Layer 9）接到落盘后端（``Store``）上。"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..observability import Actor, EvidenceRecord
from .store import JsonlStore, Store


class EvidenceLog:
    """append-only 证据日志。只追加，不修改历史行。

    ``run_id`` 在构造时绑定：同一次运行写出的所有事件共享它，不传就自动生成一个。
    一个 store 里可以并存多次运行的事件，靠 ``run_id`` 区分。
    """

    def __init__(self, store: Store, *, run_id: str | None = None) -> None:
        self.store = store
        self.run_id = run_id or uuid.uuid4().hex

    def append(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        actor: str = Actor.KERNEL,
        caused_by: str | None = None,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            kind=str(kind),
            payload=payload,
            run_id=self.run_id,
            actor=str(actor),
            caused_by=caused_by,
        )
        self.store.append(record)
        return record

    def read_all(self) -> list[EvidenceRecord]:
        """读回 store 里的全部事件，包含别的运行写的。"""
        return self.store.read_all()

    def read_run(self, run_id: str | None = None) -> list[EvidenceRecord]:
        """只读某一次运行的事件，默认是本 log 绑定的那次。"""
        target = run_id or self.run_id
        return [record for record in self.read_all() if record.run_id == target]


class JsonlEvidenceLog(EvidenceLog):
    """默认实现：写一个 JSONL 文件，每次追加都 fsync。"""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str | None = None,
        fsync: bool = True,
    ) -> None:
        super().__init__(JsonlStore(path, fsync=fsync), run_id=run_id)

    @property
    def path(self) -> Path:
        return self.store.path  # type: ignore[attr-defined]
