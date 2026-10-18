from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from kitchenlab.api import app, store
from kitchenlab.catalog import search_catalog, techniques_for
from kitchenlab.checks import run_checks
from kitchenlab.compose import build_report, remember_retrieval
from kitchenlab.schema import Case, Finding, ReportIn, Retrieval, Source, Status, Technique
from kitchenlab.simulate import looks_like_experiment, simulate_change
from kitchenlab.validate import ground_report


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DIR", str(tmp_path))
    store.root = tmp_path
    counter = tmp_path / "counter.txt"
    if counter.exists():
        counter.unlink()
    return TestClient(app)


def _potato_retrievals() -> list[Retrieval]:
    return [
        Retrieval(
            url="https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe",
            title="The Best Roast Potatoes Ever",
            passage=(
                "Parboil the potatoes with a pinch of baking soda so the surfaces break down, "
                "then shake the pot to roughen them before a high-heat roast on a preheated sheet."
            ),
        ),
        Retrieval(
            url="https://www.bonappetit.com/recipe/crispy-roast-potatoes",
            title="Crispy roast potatoes",
            passage=(
                "Some cooks skip the boil and roast from raw. Others simmer first, drain well, "
                "and roast at 425F until browned."
            ),
        ),
    ]


def test_catalog_finds_potato_techniques():
    result = search_catalog("crispy roast potatoes")
    ids = {item["id"] for item in result["techniques"]}
    assert {"parboiling", "roughening", "baking-soda", "high-heat"} <= ids
    named = techniques_for("crispy oven-roasted potatoes")
    assert [item.id for item in named][:4]


def test_checks_observe_mentioned_techniques():
    techniques = techniques_for("crispy roast potatoes")
    result = run_checks(_potato_retrievals(), techniques=techniques)
    by_id = {item["check"]: item for item in result["observations"]}
    assert by_id["parboiling"]["status"] == "OBSERVED"
    assert by_id["baking-soda"]["status"] == "OBSERVED"
    assert "seriouseats.com" in result["scope"] or "Best Roast Potatoes" in result["scope"]


def test_checks_mark_missing_technique_not_observed():
    drying = Technique(
        id="steam-rack-dry",
        name="Drying on a rack",
        purpose="Removes surface water",
        terms=["steam dry", "pat dry"],
    )
    result = run_checks(_potato_retrievals(), techniques=[drying])
    assert result["observations"][0]["status"] == "NOT OBSERVED"
    assert "retrieved pages" in result["observations"][0]["scope"] or result["scope"]


def test_not_observed_requires_scope():
    with pytest.raises(ValueError):
        Finding(
            id="parboiling",
            technique="Parboiling",
            purpose="Softens the exterior",
            observation="None found",
            why_it_matters="Starch gelatinizes.",
            limitations="Scope is limited.",
            next_check="Read another recipe.",
            status=Status.NOT_OBSERVED,
            evidence_refs=["01"],
        )


def test_report_requires_recipe_and_science_sources():
    report = ReportIn(
        sources=[
            Source(ref="01", title="A recipe", url="https://example.com/a", source_type="Recipe"),
        ],
        findings=[
            Finding(
                id="parboiling",
                technique="Parboiling",
                purpose="Softens the exterior",
                observation="Seen",
                why_it_matters="It matters.",
                limitations="Limited.",
                next_check="Look again.",
                status=Status.REPORTED,
                evidence_refs=["01"],
            )
        ],
    )
    with pytest.raises(ValueError):
        ground_report(report, ["https://example.com/a"], [])


def test_primary_url_must_have_been_retrieved():
    report = ReportIn(
        sources=[
            Source(
                ref="01",
                title="A recipe",
                url="https://example.com/not-retrieved",
                source_type="Recipe",
                passage="A sentence.",
            ),
            Source(
                ref="02",
                title="Science",
                url="https://example.com/science",
                source_type="Science",
                passage="Starch gelatinizes in hot water.",
            ),
        ],
        findings=[
            Finding(
                id="parboiling",
                technique="Parboiling",
                purpose="Softens the exterior",
                observation="Seen",
                why_it_matters="It matters.",
                limitations="Limited.",
                next_check="Look again.",
                status=Status.INFERRED,
                evidence_refs=["01", "02"],
            )
        ],
    )
    with pytest.raises(ValueError):
        ground_report(report, ["https://example.com/science"], [])


def test_compose_uses_named_techniques(client: TestClient):
    created = client.post(
        "/cases",
        json={
            "question": "What's the best way to make crispy oven-roasted potatoes, and why do recipes disagree?",
            "dish": "crispy roast potatoes",
            "prompt": "What's the best way to make crispy oven-roasted potatoes, and why do recipes disagree?",
        },
    )
    assert created.status_code == 200, created.text
    case_id = created.json()["id"]
    stored = store.get(case_id)
    stored.retrievals = _potato_retrievals()
    stored.retrieved_urls = [item.url for item in stored.retrievals]
    stored.techniques = techniques_for("crispy roast potatoes")
    store.save(stored)
    composed = client.post(f"/cases/{case_id}/compose", json={})
    assert composed.status_code == 200, composed.text
    body = composed.json()
    assert body["findings"]
    assert {item["id"] for item in body["findings"]} <= {item.id for item in stored.techniques} | {
        item["id"] for item in body["findings"]
    }
    assert body["recipe"]["steps"]
    order = [step["technique_id"] for step in body["recipe"]["steps"]]
    assert order.index("baking-soda") < order.index("parboiling") < order.index("roughening")
    assert order.index("roughening") < order.index("drying") < order.index("high-heat")
    assert "does not test the user's kitchen" in (body["recommendation_limits"] or "")


def test_simulate_skip_parboiling(client: TestClient):
    created = client.post(
        "/cases",
        json={"question": "How do I roast crispy potatoes?", "dish": "crispy roast potatoes"},
    )
    case_id = created.json()["id"]
    stored = store.get(case_id)
    stored.retrievals = _potato_retrievals()
    stored.retrieved_urls = [item.url for item in stored.retrievals]
    stored.techniques = techniques_for("crispy roast potatoes")
    stored.findings = [
        Finding(
            id="parboiling",
            technique="Parboiling",
            purpose="Softens the exterior",
            observation="Mentioned in retrieved recipes.",
            why_it_matters="Surface starch gelatinizes.",
            limitations="Only retrieved pages were reviewed.",
            next_check="",
            status=Status.OBSERVED,
            scope="retrieved pages",
            evidence_refs=["01"],
            gap=True,
        )
    ]
    store.save(stored)
    assert looks_like_experiment("What if I skip parboiling?")
    experimented = client.post(f"/cases/{case_id}/simulate", json={"change": "What if I skip parboiling?"})
    assert experimented.status_code == 200, experimented.text
    simulation = experimented.json()["simulation"]
    assert simulation["label"] == "EXPERIMENT"
    assert simulation["technique"] == "Parboiling"
    assert simulation["predicted"]
    assert "not cooked" in simulation["limits"]
    local = simulate_change(store.get(case_id), "skip parboiling")
    assert local.predicted_status == Status.INFERRED


def test_interpret_reads_question_and_dish(monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert url.endswith("/chat/completions")
        assert "crispy" in json["messages"][1]["content"]
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"question":"What is the best way to make crispy oven-roasted potatoes?","dish":"crispy roast potatoes"}'
                        }
                    }
                ]
            },
            request=request,
        )

    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL", "test-model")
    monkeypatch.setattr("kitchenlab.interpret.httpx.post", fake_post)
    from kitchenlab.interpret import infer_request

    assert infer_request("What's the best way to make crispy oven-roasted potatoes, and why do recipes disagree?") == {
        "question": "What is the best way to make crispy oven-roasted potatoes?",
        "dish": "crispy roast potatoes",
    }


def test_history_keeps_the_prompt_and_lists_newest_first(client: TestClient):
    first = client.post(
        "/cases",
        json={
            "question": "Should I salt steak ahead?",
            "dish": "steak",
            "prompt": "Should I salt steak before cooking or afterward?",
        },
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/cases",
        json={
            "question": "Does oil in pasta water help?",
            "dish": "pasta",
            "prompt": "Does adding oil to pasta water prevent sticking?",
        },
    )
    assert second.status_code == 200, second.text
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    history = client.get("/history")
    assert history.status_code == 200, history.text
    items = history.json()
    assert [item["id"] for item in items[:2]] == [second_id, first_id]
    assert items[0]["prompt"] == "Does adding oil to pasta water prevent sticking?"
    assert "findings" not in items[0]
    assert "sources" not in items[0]

    renamed = client.post(f"/cases/{first_id}/prompt", json={"prompt": "The question I actually asked"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["prompt"] == "The question I actually asked"

    removed = client.delete(f"/cases/{first_id}")
    assert removed.status_code == 204
    assert client.get(f"/cases/{first_id}").status_code == 404
    remaining = [item["id"] for item in client.get("/history").json()]
    assert first_id not in remaining
    assert second_id in remaining


def test_recipes_section_is_kept_after_compose(client: TestClient):
    created = client.post(
        "/cases",
        json={"question": "Why do roast potato recipes disagree?", "dish": "crispy roast potatoes"},
    )
    case_id = created.json()["id"]
    stored = store.get(case_id)
    stored.retrieved_urls = ["https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe"]
    stored.retrievals = _potato_retrievals()[:1]
    store.save(stored)
    recipes = {
        "summary_known": "Professional recipes parboil potatoes, then roughen and roast them hot.",
        "summary_unknown": "Dosage for baking soda is not consistent.",
        "sources": [
            {
                "ref": "01",
                "title": "The Best Roast Potatoes Ever",
                "url": "https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe",
                "source_type": "Science",
                "published": "2016-12-07",
                "passage": "Parboil the potatoes with a pinch of baking soda so the surfaces break down, then shake the pot to roughen them before a high-heat roast on a preheated sheet.",
            }
        ],
        "techniques": [
            {
                "id": "parboiling",
                "name": "Parboiling",
                "purpose": "Softens the exterior before roasting",
                "mechanism": "Gelatinizes surface starch.",
                "terms": ["parboil", "boil first"],
            }
        ],
    }
    saved = client.post(f"/cases/{case_id}/recipes", json=recipes)
    assert saved.status_code == 200, saved.text
    composed = client.post(f"/cases/{case_id}/compose", json={})
    assert composed.status_code == 200, composed.text
    body = composed.json()
    assert body["summary_known"].startswith("Professional recipes")
    ids = [item["id"] for item in body["findings"]]
    assert ids[0] == "parboiling"
    assert "parboiling" in ids
    assert body["findings"][0]["status"] == "OBSERVED"


def test_remember_retrieval_keeps_page_text():
    case = Case(
        id="011",
        stamp="Q / 011",
        question="Why do roast potato recipes disagree?",
        dish="crispy roast potatoes",
        created_at="2026-10-18T00:00:00+00:00",
        updated_at="2026-10-18T00:00:00+00:00",
    )
    remember_retrieval(
        case,
        "https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe",
        "The Best Roast Potatoes Ever",
        "Parboil the potatoes with baking soda. Shake the pot to roughen them. Roast on a preheated sheet at 425F.",
    )
    assert "Parboil the potatoes with baking soda." in case.retrievals[0].passage
    assert "425F" in case.retrievals[0].passage


def test_compose_extracts_when_search_snippets_miss_techniques(client: TestClient, monkeypatch):
    created = client.post(
        "/cases",
        json={"question": "Why do roast potato recipes disagree?", "dish": "crispy roast potatoes"},
    )
    case_id = created.json()["id"]
    stored = store.get(case_id)
    stored.retrieved_urls = ["https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe"]
    stored.retrievals = [
        Retrieval(
            url="https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe",
            title="The Best Roast Potatoes Ever",
            passage="The potatoes sit in the middle of the waxy-starchy spectrum.",
        )
    ]
    stored.techniques = techniques_for("crispy roast potatoes")
    store.save(stored)

    def fake_extract(urls):
        return {
            "results": [
                {
                    "url": urls[0],
                    "content": (
                        "Parboil the potatoes with a pinch of baking soda so the surfaces break down, "
                        "then shake the pot to roughen them before a high-heat roast on a preheated sheet."
                    ),
                }
            ]
        }

    monkeypatch.setattr("kitchenlab.api.tavily_extract", fake_extract)
    composed = client.post(f"/cases/{case_id}/compose", json={})
    assert composed.status_code == 200, composed.text
    body = composed.json()
    by_id = {item["id"]: item["status"] for item in body["findings"]}
    assert by_id["parboiling"] == "OBSERVED"
    assert by_id["baking-soda"] == "OBSERVED"
    assert any(event["summary"].startswith("Extracted ") for event in body["events"])


def test_compose_extracts_leftover_thin_pages(client: TestClient, monkeypatch):
    created = client.post(
        "/cases",
        json={"question": "Why do roast potato recipes disagree?", "dish": "crispy roast potatoes"},
    )
    case_id = created.json()["id"]
    stored = store.get(case_id)
    stored.retrieved_urls = [
        "https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe",
        "https://www.thekitchn.com/roasted-potatoes-recipe-showdown-23773251",
    ]
    stored.retrievals = [
        Retrieval(
            url="https://www.seriouseats.com/the-best-roast-potatoes-ever-recipe",
            title="The Best Roast Potatoes Ever",
            passage=_potato_retrievals()[0].passage + " " + ("Roast until the edges brown. " * 120),
        ),
        Retrieval(
            url="https://www.thekitchn.com/roasted-potatoes-recipe-showdown-23773251",
            title="The Recipe for the Crispiest Roasted Potatoes",
            passage="PxPixel Editor Faves Quick and Easy.",
        ),
    ]
    stored.techniques = techniques_for("crispy roast potatoes")
    store.save(stored)
    store.add_event(case_id, "Extracted 1 pages")

    def fake_extract(urls):
        assert "https://www.thekitchn.com/roasted-potatoes-recipe-showdown-23773251" in urls
        return {
            "results": [
                {
                    "url": "https://www.thekitchn.com/roasted-potatoes-recipe-showdown-23773251",
                    "content": "The winning method parboils the potatoes, then roughens the edges before roasting.",
                }
            ]
        }

    monkeypatch.setattr("kitchenlab.api.tavily_extract", fake_extract)
    composed = client.post(f"/cases/{case_id}/compose", json={})
    assert composed.status_code == 200, composed.text
    body = composed.json()
    by_id = {item["id"]: item["status"] for item in body["findings"]}
    assert by_id["parboiling"] == "OBSERVED"
    assert by_id["roughening"] == "OBSERVED"


def test_compose_without_techniques_uses_mentioned_pages():
    case = Case(
        id="010",
        stamp="Q / 010",
        question="What's the best way to make crispy oven-roasted potatoes?",
        dish="crispy roast potatoes",
        created_at="2026-10-18T00:00:00+00:00",
        updated_at="2026-10-18T00:00:00+00:00",
        retrievals=_potato_retrievals(),
        retrieved_urls=[item.url for item in _potato_retrievals()],
    )
    report = build_report(case, [])
    assert report.findings
    assert "parboiling" in {item.id for item in report.techniques}
    assert report.recipe and report.recipe.steps


def test_compose_drops_catalog_techniques_the_pages_do_not_name():
    case = Case(
        id="012",
        stamp="Q / 012",
        question="How do I make oven-baked potatoes crispy?",
        dish="oven-baked potatoes",
        created_at="2026-10-18T00:00:00+00:00",
        updated_at="2026-10-18T00:00:00+00:00",
        techniques=techniques_for("crispy roast potatoes"),
        retrievals=[
            Retrieval(
                url="https://www.loveandlemons.com/baked-potato",
                title="Perfect Baked Potato Recipe",
                passage="Pat dry the potatoes and roast at 425F on a hot sheet until the skins crisp.",
            )
        ],
        retrieved_urls=["https://www.loveandlemons.com/baked-potato"],
    )
    report = build_report(case, [])
    ids = {item.id for item in report.techniques}
    assert "high-heat" in ids
    assert "drying" in ids
    assert "baking-soda" not in ids
    assert "roughening" not in ids
    assert "oil-in-water" not in ids


def test_compose_ignores_unrelated_summary_known():
    case = Case(
        id="013",
        stamp="Q / 013",
        question="How do I roast crispy potatoes?",
        dish="crispy roast potatoes",
        created_at="2026-10-18T00:00:00+00:00",
        updated_at="2026-10-18T00:00:00+00:00",
        summary_known="You should get about six wedges from each half, or twelve from a whole potato.",
        retrievals=_potato_retrievals(),
        retrieved_urls=[item.url for item in _potato_retrievals()],
        techniques=techniques_for("crispy roast potatoes")[:3],
    )
    report = build_report(
        case,
        [
            {
                "check": item.id,
                "status": "OBSERVED",
                "detail": f"{item.name} is mentioned in the retrieved pages.",
                "scope": "retrieved pages",
            }
            for item in case.techniques
        ],
    )
    assert "wedges" not in report.summary_known
    assert "The pages we read use" in report.summary_known


def test_thin_report_does_not_mark_case_complete(client: TestClient):
    created = client.post(
        "/cases",
        json={"question": "How do I roast crispy potatoes?", "dish": "crispy roast potatoes"},
    )
    case_id = created.json()["id"]
    posted = client.post(
        f"/cases/{case_id}/report",
        json={
            "summary_known": "You should get about six wedges from each half.",
            "findings": [],
            "sources": [],
        },
    )
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert body["stage"] not in {"COMPLETE", "PARTIAL", "FAILED"}
