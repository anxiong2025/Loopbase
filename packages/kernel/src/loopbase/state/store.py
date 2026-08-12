"""Layer 7 — 状态落盘引擎。

``Store`` 是 STRUCTURE.md 里点名的 Rust 接缝之一：现在的默认实现是纯 Python
JSONL + fsync，以后换 Rust 后端是换实现、不改接口。

落盘只有两个动作：**追加一条**、**读回全部**。没有 update / delete——事件日志
是 append-only 的，改历史就不是证据了。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..observability import SCHEMA_VERSION, EvidenceRecord


class EvidenceSchemaMismatch(ValueError):
    """读到了当前内核不认识的事件 schema 版本。

    宁可明确报错，也不要用新代码去猜旧格式——静默读错比读不出来更危险
    （ROADMAP Stage 4 的「状态 schema 版本化」要求）。
    """


@runtime_checkable
class Store(Protocol):
    """证据记录的持久化后端。"""

    def append(self, record: EvidenceRecord) -> None: ...

    def read_all(self) -> list[EvidenceRecord]: ...


class JsonlStore:
    """一行一条记录的 append-only JSONL。

    ``fsync=True`` 时每次追加都落到磁盘再返回：这是「kill -9 之后日志不丢最后
    几条」的前提，也是这一层存在的理由。批量导入等不在意崩溃语义的场景可以关掉。
    """

    def __init__(self, path: str | Path, *, fsync: bool = True) -> None:
        self.path = Path(path)
        self.fsync = fsync

    def append(self, record: EvidenceRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.to_json() + "\n")
            if self.fsync:
                f.flush()
                os.fsync(f.fileno())

    def read_all(self) -> list[EvidenceRecord]:
        if not self.path.exists():
            return []
        records: list[EvidenceRecord] = []
        with self.path.open(encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                version = data.get("schema_version")
                if version != SCHEMA_VERSION:
                    raise EvidenceSchemaMismatch(
                        f"{self.path}:{line_number} has event schema {version!r}; "
                        f"this kernel reads {SCHEMA_VERSION!r}"
                    )
                records.append(EvidenceRecord.from_dict(data))
        return records


class MemoryStore:
    """进程内存实现。测试用，也是 ``Store`` 契约的第二个实现。"""

    def __init__(self) -> None:
        self.records: list[EvidenceRecord] = []

    def append(self, record: EvidenceRecord) -> None:
        self.records.append(record)

    def read_all(self) -> list[EvidenceRecord]:
        return list(self.records)
