from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from kitchenlab.paths import case_dir
from kitchenlab.schema import Case, CreateCase, ResearchEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class CaseStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or case_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, case_id: str) -> Path:
        return self.root / f"{case_id}.json"

    def _counter(self) -> Path:
        return self.root / "counter.txt"

    def list_cases(self) -> list[Case]:
        cases = []
        for path in self.root.glob("*.json"):
            try:
                cases.append(Case.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            except (ValidationError, json.JSONDecodeError, OSError):
                continue
        cases.sort(key=lambda case: (case.updated_at, case.created_at, case.id), reverse=True)
        return cases

    def get(self, case_id: str) -> Case:
        path = self._path(case_id)
        if not path.exists():
            raise KeyError(case_id)
        return Case.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _write(self, case: Case) -> Case:
        case.updated_at = now_iso()
        path = self._path(case.id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(case.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        return case

    def save(self, case: Case) -> Case:
        with self._lock:
            return self._write(case)

    def create(self, payload: CreateCase) -> Case:
        with self._lock:
            current = 0
            if self._counter().exists():
                current = int(self._counter().read_text(encoding="utf-8") or "0")
            current += 1
            self._counter().write_text(str(current), encoding="utf-8")
            case_id = f"{current:03d}"
            stamp_time = now_iso()
            question = payload.question.strip()
            dish = payload.dish.strip() or question
            case = Case(
                id=case_id,
                stamp=f"Q / {case_id}",
                question=question,
                dish=dish,
                prompt=payload.prompt.strip() or question,
                sample=payload.sample,
                stage="RESEARCHING",
                created_at=stamp_time,
                updated_at=stamp_time,
                scope_label="RETRIEVED SOURCES",
            )
            self._write(case)
            return case

    def delete(self, case_id: str) -> None:
        with self._lock:
            path = self._path(case_id)
            if not path.exists():
                raise KeyError(case_id)
            path.unlink()

    def add_event(self, case_id: str, summary: str) -> Case:
        with self._lock:
            case = self.get(case_id)
            case.events.append(ResearchEvent(at=now_iso(), summary=summary))
            return self._write(case)
