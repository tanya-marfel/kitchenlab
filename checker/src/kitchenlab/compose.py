"""Build a report from pages and checks already recorded for a case."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from kitchenlab.catalog import catalog_entry, techniques_for, techniques_in_retrievals
from kitchenlab.schema import (
    Conflict,
    Finding,
    Recipe,
    RecipeStep,
    ReportIn,
    Retrieval,
    Source,
    Status,
    Technique,
)
from kitchenlab.validate import ground_report

ISO_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})\b",
    re.I,
)
US_DATE_RE = re.compile(
    r"\b((January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2})\b",
    re.I,
)

SCIENCE_HOSTS = (
    "seriouseats.com",
    "acs.org",
    "nature.com",
    "sciencedirect.com",
    "springer.com",
    "nih.gov",
    "wikipedia.org",
    "exploratorium.edu",
    "ift.org",
)
RECIPE_HOSTS = (
    "nytimes.com",
    "bonappetit.com",
    "food52.com",
    "bbcgoodfood.com",
    "allrecipes.com",
    "epicurious.com",
    "thekitchn.com",
    "budgetbytes.com",
    "smittenkitchen.com",
)


NAV_RE = re.compile(
    r"skip to|newsletter|subscribe|related recipes|jump to recipe|home›|latest recipes|fan favorites|verifiedapproved|\d:\d{2}",
    re.I,
)
SUMMARY_HEAD = re.compile(
    r"^(the |most |retrieved |professional |recipes |cooks |pages |these |across )",
    re.I,
)


def _clean_prose(text: str) -> str:
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    cleaned = re.sub(r"[#>*_`]+", " ", cleaned)
    return " ".join(cleaned.split())


def _fold(text: str) -> str:
    return (
        text.casefold()
        .replace("°c", "c")
        .replace("°f", "f")
        .replace(" degrees celsius", "c")
        .replace(" degrees fahrenheit", "f")
        .replace(" degrees", "")
    )


def _clip_sentence(part: str, limit: int) -> str:
    if len(part) <= limit:
        return part
    return part[:limit].rsplit(" ", 1)[0].rstrip(".,;") + "."


def _sentence(text: str, limit: int = 320) -> str:
    cleaned = _clean_prose(text)
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    for part in parts:
        if len(part) > 80 and part.count("/") < 2:
            return _clip_sentence(part, limit)
    return _clip_sentence(cleaned, limit)


def _relevant_sentence(text: str, techniques: list[Technique], limit: int = 280) -> str:
    cleaned = _clean_prose(text)
    if not cleaned:
        return "This page was retrieved during the case."
    terms: list[str] = []
    for item in techniques:
        if item.name:
            terms.append(item.name)
        terms.extend(item.terms)
        terms.append(item.id.replace("-", " "))
    ranked: list[tuple[int, int, str]] = []
    for part in re.split(r"(?<=[.!?])\s+", cleaned):
        part = part.strip()
        if len(part) < 40 or part.count("/") >= 2 or NAV_RE.search(part):
            continue
        blob = _fold(part)
        score = sum(1 for term in terms if term and _fold(term) in blob)
        ranked.append((score, -len(part), part))
    ranked.sort(reverse=True)
    if ranked and ranked[0][0] > 0:
        return _clip_sentence(ranked[0][2], limit)
    return _sentence(text, limit)


def _working_text(text: str, limit: int = 18000) -> str:
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    cleaned = re.sub(r"[#>*_`]+", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].rstrip(".,;") + "."


def remember_retrieval(case, url: str, title: str = "", passage: str = "") -> None:
    if not url:
        return
    if url not in case.retrieved_urls:
        case.retrieved_urls.append(url)
    snippet = _working_text(passage) if passage else ""
    for item in case.retrievals:
        if item.url == url:
            if title and not item.title:
                item.title = title
            if snippet and len(snippet) > len(item.passage):
                item.passage = snippet
            return
    case.retrievals.append(Retrieval(url=url, title=title or url, passage=snippet))


def _date_in(text: str) -> str | None:
    if not text:
        return None
    match = ISO_RE.search(text) or TEXT_DATE_RE.search(text) or US_DATE_RE.search(text)
    return match.group(1) if match else None


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _source_type_for(url: str, preferred: dict[str, str]) -> str:
    host = _host(url)
    if host in preferred:
        return preferred[host]
    if any(host.endswith(item) for item in SCIENCE_HOSTS):
        return "Science"
    if any(host.endswith(item) for item in RECIPE_HOSTS):
        return "Recipe"
    return "Independent"


def _preferred_hosts(sources: list[Source]) -> dict[str, str]:
    hosts: dict[str, str] = {}
    for source in sources:
        if not source.url:
            continue
        if source.source_type in {"Recipe", "Science", "Independent"}:
            hosts[_host(source.url)] = source.source_type
    return hosts


def _mentions_techniques(text: str, techniques: list[Technique]) -> bool:
    blob = _fold(text)
    for item in techniques:
        if item.name and _fold(item.name) in blob:
            return True
        if item.id.replace("-", " ") in blob:
            return True
        if any(_fold(term) in blob for term in item.terms if term):
            return True
    return False


def _plain_name(name: str) -> str:
    if not name:
        return name
    if len(name) > 1 and name[0].isupper() and name[1].isupper():
        return name
    return name[0].lower() + name[1:]


def _join_and(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _looks_like_summary(text: str, techniques: list[Technique]) -> bool:
    if not _mentions_techniques(text, techniques):
        return False
    if re.match(r"^retrieved pages mention", text, re.I):
        return False
    if SUMMARY_HEAD.match(text):
        return True
    blob = text.casefold()
    named = 0
    for item in techniques:
        if item.name and item.name.casefold() in blob:
            named += 1
            continue
        if any(term.casefold() in blob for term in item.terms[:3] if term):
            named += 1
    return named >= 2 and len(text) < 240


def _known_summary(techniques: list[Technique], observed: list[str]) -> str:
    if observed:
        return f"The pages we read use {_join_and([_plain_name(name) for name in observed])}."
    if techniques:
        return "The pages we read name these techniques, but none of them showed up in the text."
    return "We retrieved pages, but could not extract a technique to check."


def _unknown_summary(case, open_names: list[str]) -> str:
    canned = {
        "Named techniques that were not established in the retrieved pages remain open.",
        "Recipes still disagree about which of these steps are necessary.",
    }
    existing = (case.summary_unknown or "").strip()
    if open_names:
        if existing and existing not in canned and SUMMARY_HEAD.match(existing):
            return existing
        return (
            f"We did not find {_join_and([_plain_name(name) for name in open_names])} "
            "in those pages. That does not mean those steps fail."
        )
    if existing and existing not in canned:
        return existing
    return "Recipes still disagree about whether you need every one of those steps."


def _summary_known(case, techniques: list[Technique], observed: list[str]) -> str:
    existing = (case.summary_known or "").strip()
    if existing and _looks_like_summary(existing, techniques):
        return _sentence(existing)
    return _known_summary(techniques, observed)


def _technique_mentioned(item: Technique, retrievals) -> bool:
    blob = " ".join(filter(None, (f"{row.title} {row.passage}" for row in retrievals))).casefold()
    if item.id.replace("-", " ") in blob or item.name.casefold() in blob:
        return True
    catalog_terms = list((catalog_entry(item.id) or {}).get("terms") or [])
    return any(term.casefold() in blob for term in [*item.terms, *catalog_terms] if term)


def _relevant_to_dish(item: Technique, dish: str) -> bool:
    if not dish.strip() or not catalog_entry(item.id):
        return True
    relevant = {entry.id for entry in techniques_for(dish, limit=12)}
    return not relevant or item.id in relevant


def _techniques_for(case) -> list[Technique]:
    dish = case.dish or case.question
    mentioned = techniques_in_retrievals(case.retrievals, limit=5, dish=dish)
    if not case.techniques:
        return mentioned
    kept = [
        item
        for item in case.techniques
        if _technique_mentioned(item, case.retrievals) and _relevant_to_dish(item, dish)
    ]
    if not kept:
        return mentioned
    seen = {item.id for item in kept}
    for item in mentioned:
        if item.id in seen:
            continue
        kept.append(item)
        seen.add(item.id)
        if len(kept) >= 5:
            break
    return kept[:5]


def _collect_sources(case, techniques: list[Technique]) -> list[Source]:
    preferred = _preferred_hosts(case.sources)
    sources: list[Source] = []
    seen: set[str] = set()
    by_url = {item.url.rstrip("/"): item for item in case.retrievals if item.url}
    for source in case.sources:
        if source.source_type in {"Recipe", "Science", "Independent"} and source.url:
            retrieval = by_url.get(source.url.rstrip("/"))
            if retrieval and retrieval.passage:
                better = _relevant_sentence(retrieval.passage, techniques)
                current = source.passage or ""
                if _mentions_techniques(better, techniques) and not _mentions_techniques(current, techniques):
                    source = source.model_copy(update={"passage": better})
                elif NAV_RE.search(current) or current.count("+") >= 3:
                    source = source.model_copy(update={"passage": better})
            sources.append(source)
            seen.add(source.url.rstrip("/"))
    for index, item in enumerate(case.retrievals, start=len(sources) + 1):
        if not item.url or item.url.rstrip("/") in seen:
            continue
        if len(sources) >= 8:
            break
        passage = (
            _relevant_sentence(item.passage, techniques)
            if item.passage
            else "This page was retrieved during the case."
        )
        sources.append(
            Source(
                ref=f"{index:02d}",
                title=item.title or item.url,
                url=item.url,
                source_type=_source_type_for(item.url, preferred),
                passage=passage,
                published=_date_in(item.passage) or None,
            )
        )
        seen.add(item.url.rstrip("/"))
    return sources


def _conflicts_for(techniques: list[Technique], sources: list[Source], existing: list[Conflict]) -> list[Conflict]:
    if existing:
        return existing
    conflicts: list[Conflict] = []
    refs = [source.ref for source in sources[:2]]
    for item in techniques:
        entry = catalog_entry(item.id)
        if not entry or not entry.get("disagreement"):
            continue
        conflicts.append(
            Conflict(
                id=f"conflict-{item.id}",
                topic=item.name,
                summary=entry["disagreement"],
                positions=[],
                source_refs=refs,
                status=Status.CONTRADICTED,
            )
        )
    return conflicts[:5]


def _step_rank(technique_id: str, fallback: int) -> int:
    entry = catalog_entry(technique_id) or {}
    order = entry.get("step_order")
    return order if isinstance(order, int) else fallback


def _recipe_title(dish: str) -> str:
    text = " ".join(dish.split()) or "This dish"
    return text[:1].upper() + text[1:]


def _recipe_for(case, techniques: list[Technique], sources: list[Source]) -> Recipe:
    if case.recipe and case.recipe.steps:
        return case.recipe
    refs = [source.ref for source in sources[:2]]
    ranked = sorted(enumerate(techniques), key=lambda pair: (_step_rank(pair[1].id, 1000 + pair[0]), pair[0]))
    steps: list[RecipeStep] = []
    for offset, (_, item) in enumerate(ranked, start=1):
        entry = catalog_entry(item.id) or {}
        instruction = entry.get("default_step") or f"Apply {item.name}."
        why = item.mechanism or entry.get("mechanism") or item.purpose or entry.get("purpose", "")
        steps.append(
            RecipeStep(
                id=f"step-{offset}",
                instruction=instruction,
                why=why,
                technique_id=item.id,
                evidence_refs=refs,
            )
        )
    return Recipe(
        title=_recipe_title(case.dish or case.question or "this dish"),
        steps=steps,
        notes="This method follows the retrieved pages. It was not cooked.",
    )


def build_report(case, checks: list[dict]) -> ReportIn:
    techniques = _techniques_for(case)
    sources = _collect_sources(case, techniques)
    if not sources:
        raise ValueError("No retrieved pages are available to cite.")
    by_check = {item["check"]: item for item in checks}
    recipe_ref = next((source.ref for source in sources if source.source_type == "Recipe"), None)
    science_ref = next((source.ref for source in sources if source.source_type == "Science"), None)
    any_ref = sources[0].ref
    scope = next((item.get("scope") or "" for item in checks if item.get("scope")), "retrieved pages")
    findings: list[Finding] = []
    observed: list[str] = []

    for item in techniques:
        checked = by_check.get(item.id)
        status = Status(checked["status"]) if checked else Status.UNKNOWN
        detail = checked["detail"] if checked else "Not checked against the retrieved pages."
        finding_scope = (checked or {}).get("scope") or scope
        entry = catalog_entry(item.id) or {}
        refs = [ref for ref in (recipe_ref, science_ref) if ref]
        gap = not (recipe_ref and science_ref)
        if not refs:
            refs = [any_ref]
            gap = True
        if status == Status.UNKNOWN:
            gap = True
        findings.append(
            Finding(
                id=item.id,
                technique=item.name,
                purpose=item.purpose or entry.get("purpose", ""),
                observation=detail,
                why_it_matters=item.mechanism or entry.get("mechanism") or item.purpose,
                limitations="Only the retrieved pages and the culinary catalog were reviewed.",
                next_check="",
                status=status,
                scope=finding_scope,
                evidence_refs=refs,
                gap=gap,
            )
        )
        if status == Status.OBSERVED:
            observed.append(item.name)

    open_names = [finding.technique for finding in findings if finding.status in {Status.UNKNOWN, Status.NOT_OBSERVED}]
    if techniques:
        recommendation = (
            "Start with the steps that showed up in the pages, and treat the disagreements as things you can test."
            if observed
            else "None of the named techniques showed up in the pages we read."
        )
        unknown_ids = {finding.id for finding in findings if finding.status == Status.UNKNOWN}
        questions = case.open_questions or [
            item.purpose or item.name for item in techniques if item.id in unknown_ids
        ]
        if not questions:
            questions = ["Which disagreements still need a published side-by-side test?"]
    else:
        recommendation = "The question was not reduced to checkable techniques."
        questions = case.open_questions or ["Which techniques do the retrieved recipes actually use?"]

    report = ReportIn(
        summary_known=_summary_known(case, techniques, observed),
        summary_unknown=_unknown_summary(case, open_names),
        open_questions=questions[:6],
        recommendation=recommendation,
        recommendation_limits="This was not cooked and does not test the user's kitchen.",
        sources=sources,
        conflicts=_conflicts_for(techniques, sources, case.conflicts),
        findings=findings,
        techniques=techniques,
        recipe=_recipe_for(case, techniques, sources),
    )
    return ground_report(report, case.retrieved_urls, checks)
