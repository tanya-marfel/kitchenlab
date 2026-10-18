from __future__ import annotations

import re

from kitchenlab.catalog import catalog_entry, match_technique
from kitchenlab.schema import Case, Simulation, Status, Technique

CHANGE_RE = re.compile(
    r"(?i)(?:what if i\s+)?(?:skip|omit|without|no|instead of|replace)\s+(.+?)(?:\?|$)"
)


def looks_like_experiment(message: str) -> bool:
    text = message.strip()
    if not text:
        return False
    return bool(
        re.search(
            r"(?i)\b(what if|skip |omit |without |instead of |replace )\b",
            text,
        )
    )


def _technique_for(case: Case, change: str) -> Technique:
    found = match_technique(change, case.techniques)
    if found:
        return found
    if case.techniques:
        return case.techniques[0]
    raise ValueError("No technique on this question matches that change.")


def _retrieval_mentions(case: Case, terms: list[str]) -> bool:
    blob = " ".join(item.passage for item in case.retrievals).casefold()
    return any(term.casefold() in blob for term in terms if term)


def simulate_change(case: Case, change: str) -> Simulation:
    text = change.strip()
    if not text:
        raise ValueError("Describe the change to test, for example skipping parboiling.")
    technique = _technique_for(case, text)
    entry = catalog_entry(technique.id) or {}
    supported = entry.get("skip_supported") or (
        f"Retrieved pages do not include a published test of skipping {technique.name}."
    )
    predicted = entry.get("skip_predicted") or (
        f"Skipping {technique.name} is expected to change the property it is meant to produce: {technique.purpose}."
    )
    tested = entry.get("support") == "tested"
    mentions = _retrieval_mentions(
        case,
        [*technique.terms, "test", "tested", "side-by-side", "comparison"],
    )
    if tested and mentions:
        supported_status = Status.REPORTED
    elif tested:
        supported_status = Status.INFERRED
        supported = (
            f"{supported} The catalog records published tests; those pages were not retrieved in this case."
        )
    else:
        supported_status = Status.UNKNOWN
    return Simulation(
        change=text,
        technique=technique.name,
        supported=supported,
        predicted=predicted,
        supported_status=supported_status,
        predicted_status=Status.INFERRED,
        limits=(
            "This experiment was not cooked. Supported lines come from published tests "
            "in the retrieved pages or the culinary catalog. Predicted lines are not kitchen results."
        ),
    )
