"""Layer 9 — 可观测性与证据日志（雏形）。

现在只做最朴素的 append-only JSONL：每个状态转移写一行，带 schema 版本。
Stage 4 会把「来源标记」「检查点恢复」接进来，这里先定好写入契约。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "event/v1"


@dataclass
class EvidenceRecord:
    """一条不可变证据。kind 由调用方指定，payload 是任意结构化数据。"""

    kind: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: str = SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class JsonlEvidenceLog:
    """append-only 证据日志。只追加，不修改历史行。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, kind: str, payload: dict[str, Any]) -> EvidenceRecord:
        record = EvidenceRecord(kind=kind, payload=payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.to_json() + "\n")
        return record

    def read_all(self) -> list[EvidenceRecord]:
        if not self.path.exists():
            return []
        records: list[EvidenceRecord] = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records.append(EvidenceRecord(**data))
        return records
