"""Write the KitchenLab n8n workflow export."""

from __future__ import annotations

import json
from pathlib import Path

CHECKER = "http://checker:8000"
CREDENTIAL_ID = "TOKEN_FACTORY_CREDENTIAL_ID"

RECIPE_PROMPT = """You research professional recipes and chef recommendations for the cooking question named in the user message, using only pages Tavily retrieves during this case.
Do not claim a recipe is proven in the user's kitchen. Do not invent URLs or passages.
Call tools in this order, then stop: one Tavily search for recipes and chef recommendations, one extract of at most two recipe pages. After those two calls, return the JSON.
Extract at most five techniques those recipes actually use. Do not invent the sample potato techniques unless those pages name them.
Each technique has id (a slug), name, purpose (one sentence from a retrieved page), mechanism if the page explains it, and terms (3-8 literal strings).
Return conflicts where retrieved recipes disagree.
Return JSON only. source_type for a chef or recipe page is Recipe. Other reporting is Independent. Passages are short quotations from retrieved pages.
When you call a tool, pass case_id exactly as given in the user message.
Shape:
{"summary_known":"","summary_unknown":"","open_questions":[],"sources":[{"ref":"01","title":"","url":"","source_type":"Recipe","published":null,"retrieved":"2026-10-18","passage":""}],"conflicts":[{"id":"","topic":"","summary":"","positions":[],"source_refs":["01"],"status":"CONTRADICTED"}],"techniques":[{"id":"","name":"","purpose":"","mechanism":"","terms":[]}]}
Allowed status values: OBSERVED, REPORTED, INFERRED, CONTRADICTED, UNKNOWN, NOT OBSERVED."""

SCIENCE_PROMPT = """You investigate the food science behind the techniques already stored on the case.
Call the catalog lookup once with the dish or a technique name. Then call Tavily search once for the relevant food science (starch, moisture, temperature, browning, or the named mechanism). You may extract at most two science pages. Then call technique checks once.
Pass case_id exactly as given. The checker loads techniques from the case and scans retrieved pages.
Do not claim a condition the check tool did not return. Do not invent citations.
Return JSON only: {"scope":"","observations":[],"sources":[]} copying the check tool's scope and observations, and any science pages you retrieved. source_type for food-science pages is Science."""

CHECKER_PROMPT = """You compare professional recipe recommendations with food science.
Findings must be the case's techniques, not a fixed demo list. Use the check status whose id matches the technique id. Do not upgrade it.
If a material disagreement is still UNKNOWN, call the follow-up search once. That is the only extra search you may run.
Do not say the recipe is proven. Do not hide a contradiction.
Every finding that is not UNKNOWN needs one Recipe source and one Science source, or set gap true.
NOT OBSERVED findings must copy the inspected scope (the retrieved pages).
why_it_matters must say how the recipe claim relates to the science mechanism.
recommendation_limits must say this was not cooked and does not test the user's kitchen.
Return a recipe with a scientific why for every important step.
Distinguish published tests from inferred mechanisms.
Return JSON only with summary_known, summary_unknown, open_questions, recommendation, recommendation_limits, sources, conflicts, findings, techniques, recipe.
Each finding has id, technique, purpose, observation, why_it_matters, limitations, next_check, status, scope, evidence_refs, gap.
Allowed status values: OBSERVED, REPORTED, INFERRED, CONTRADICTED, UNKNOWN, NOT OBSERVED."""


def node(node_id: str, name: str, node_type: str, version: float, x: int, y: int, parameters: dict, extra: dict | None = None) -> dict:
    body = {
        "id": node_id,
        "name": name,
        "type": node_type,
        "typeVersion": version,
        "position": [x, y],
        "parameters": parameters,
    }
    if extra:
        body.update(extra)
    return body


def http_tool(
    name: str,
    description: str,
    method: str,
    url: str,
    body: str | None,
    placeholders: list[tuple[str, str]],
    x: int,
    y: int,
) -> dict:
    parameters: dict = {
        "toolDescription": description,
        "method": method,
        "url": url,
        "options": {},
        "placeholderDefinitions": {
            "values": [
                {"name": placeholder, "description": hint, "type": "string"}
                for placeholder, hint in placeholders
            ]
        },
    }
    if body is not None:
        parameters.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    return node(
        name.lower().replace(" ", "-"),
        name,
        "@n8n/n8n-nodes-langchain.toolHttpRequest",
        1.1,
        x,
        y,
        parameters,
    )


def main() -> None:
    recipes = node(
        "recipe-investigator",
        "Recipe investigator",
        "@n8n/n8n-nodes-langchain.agent",
        1.8,
        720,
        280,
        {
            "promptType": "define",
            "text": "=Question: {{ $('Create case').item.json.question }}\nDish: {{ $('Create case').item.json.dish }}\nCase id: {{ $('Create case').item.json.id }}",
            "options": {"systemMessage": RECIPE_PROMPT, "maxIterations": 6},
        },
        {"onError": "continueRegularOutput"},
    )
    science = node(
        "science-investigator",
        "Science investigator",
        "@n8n/n8n-nodes-langchain.agent",
        1.8,
        720,
        560,
        {
            "promptType": "define",
            "text": "=Dish: {{ $('Create case').item.json.dish }}\nCase id: {{ $('Create case').item.json.id }}\nTechniques: {{ JSON.stringify($('Parse recipes').item.json.techniques || []) }}\nCall catalog lookup, one science search, then technique checks.",
            "options": {"systemMessage": SCIENCE_PROMPT, "maxIterations": 6},
        },
        {"onError": "continueRegularOutput"},
    )
    model = node(
        "token-factory",
        "Token Factory",
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        1.2,
        720,
        40,
        {
            "model": {"__rl": True, "mode": "id", "value": "={{ $env.NEBIUS_MODEL }}"},
            "responsesApiEnabled": False,
            "options": {"timeout": 120000, "temperature": 0.2},
        },
        {"credentials": {"openAiApi": {"id": CREDENTIAL_ID, "name": "Token Factory"}}},
    )
    analyst = node(
        "fact-checker",
        "Fact-checker",
        "@n8n/n8n-nodes-langchain.agent",
        1.8,
        1480,
        420,
        {
            "promptType": "define",
            "text": "=Recipe JSON:\n{{ JSON.stringify($('Parse recipes').item.json) }}\n\nCheck JSON:\n{{ JSON.stringify($('Parse checks').item.json) }}\n\nTechniques:\n{{ JSON.stringify($('Parse recipes').item.json.techniques || []) }}\n\nCase id: {{ $('Create case').item.json.id }}\nDish: {{ $('Create case').item.json.dish }}",
            "options": {"systemMessage": CHECKER_PROMPT, "maxIterations": 4},
        },
        {"onError": "continueRegularOutput"},
    )
    tools = [
        http_tool(
            "TavilySearch",
            "Search the public web with Tavily for recipes or chef recommendations. Arguments: query, and depth basic or advanced.",
            "POST",
            f"{CHECKER}/tools/tavily/search",
            '{"case_id":"{case_id}","query":"{query}","depth":"{depth}"}',
            [
                ("case_id", "Case id from the user message"),
                ("query", "Search query"),
                ("depth", "basic or advanced"),
            ],
            980,
            160,
        ),
        http_tool(
            "TavilyExtract",
            "Extract text from https URLs already returned by Tavily search.",
            "POST",
            f"{CHECKER}/tools/tavily/extract",
            '{"case_id":"{case_id}","urls":"{urls}"}',
            [
                ("case_id", "Case id from the user message"),
                ("urls", "HTTPS URLs separated by spaces"),
            ],
            980,
            280,
        ),
        http_tool(
            "CatalogLookup",
            "Look up culinary techniques, mechanisms, and skip effects by dish or technique name.",
            "POST",
            f"{CHECKER}/catalog/search",
            '{"case_id":"{case_id}","query":"{query}"}',
            [
                ("case_id", "Case id from the user message"),
                ("query", "Dish or technique query"),
            ],
            980,
            400,
        ),
        http_tool(
            "TechniqueChecks",
            "Scan retrieved pages for the case's named techniques.",
            "POST",
            f"{CHECKER}/checks/run",
            '{"case_id":"{case_id}","dish":"{dish}"}',
            [
                ("case_id", "Case id from the user message"),
                ("dish", "Dish from the user message"),
            ],
            980,
            560,
        ),
        http_tool(
            "ScienceSearch",
            "Search the public web for food-science explanations.",
            "POST",
            f"{CHECKER}/tools/tavily/search",
            '{"case_id":"{case_id}","query":"{query}","depth":"advanced"}',
            [
                ("case_id", "Case id from the user message"),
                ("query", "Food-science query"),
            ],
            980,
            680,
        ),
        http_tool(
            "FollowUpSearch",
            "One Tavily search for a missing disagreement or test.",
            "POST",
            f"{CHECKER}/tools/tavily/search",
            '{"case_id":"{case_id}","query":"{query}","depth":"advanced"}',
            [
                ("case_id", "Case id from the user message"),
                ("query", "Follow-up query"),
            ],
            1680,
            400,
        ),
    ]
    parse_js = """const item = $input.first().json || {};
let raw = item.output;
if (raw && typeof raw === 'object') {
  return [{ json: raw }];
}
if (raw == null || raw === '') {
  raw = item.text || '';
}
if (typeof raw !== 'string') {
  raw = JSON.stringify(raw || {});
}
const start = raw.indexOf('{');
const end = raw.lastIndexOf('}');
if (start < 0 || end <= start) {
  return [{ json: {} }];
}
try {
  return [{ json: JSON.parse(raw.slice(start, end + 1)) }];
} catch (error) {
  return [{ json: {} }];
}"""
    nodes = [
        node(
            "start-case",
            "Start case",
            "n8n-nodes-base.webhook",
            2,
            240,
            420,
            {"httpMethod": "POST", "path": "kitchenlab", "responseMode": "responseNode", "options": {}},
            {"webhookId": "kitchenlab-start"},
        ),
        node(
            "create-case",
            "Create case",
            "n8n-nodes-base.httpRequest",
            4.2,
            460,
            420,
            {
                "method": "POST",
                "url": f"{CHECKER}/cases",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({ question: $json.body.question, dish: $json.body.dish || '', sample: Boolean($json.body.sample), prompt: $json.body.prompt || '' }) }}",
                "options": {},
            },
        ),
        node(
            "respond-with-case",
            "Respond with case",
            "n8n-nodes-base.respondToWebhook",
            1.1,
            680,
            420,
            {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ id: $json.id, stamp: $json.stamp, stage: $json.stage }) }}",
                "options": {"responseCode": 202},
            },
        ),
        model,
        recipes,
        science,
        node(
            "parse-recipes",
            "Parse recipes",
            "n8n-nodes-base.code",
            2,
            1100,
            280,
            {"language": "javaScript", "jsCode": parse_js},
            {"onError": "continueRegularOutput"},
        ),
        node(
            "store-recipes",
            "Store recipes",
            "n8n-nodes-base.httpRequest",
            4.2,
            1280,
            280,
            {
                "method": "POST",
                "url": "={{ 'http://checker:8000/cases/' + $('Create case').item.json.id + '/recipes' }}",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json) }}",
                "options": {},
            },
        ),
        node(
            "parse-checks",
            "Parse checks",
            "n8n-nodes-base.code",
            2,
            1100,
            560,
            {"language": "javaScript", "jsCode": parse_js},
            {"onError": "continueRegularOutput"},
        ),
        analyst,
        *tools,
        node(
            "parse-report",
            "Parse report",
            "n8n-nodes-base.code",
            2,
            1880,
            420,
            {"language": "javaScript", "jsCode": parse_js},
            {"onError": "continueRegularOutput"},
        ),
        node(
            "hold-for-tools",
            "Hold for tools",
            "n8n-nodes-base.wait",
            1.1,
            900,
            720,
            {"resume": "timeInterval", "amount": 35, "unit": "seconds"},
        ),
        node(
            "compose-report",
            "Compose report",
            "n8n-nodes-base.httpRequest",
            4.2,
            1120,
            720,
            {
                "method": "POST",
                "url": "={{ 'http://checker:8000/cases/' + $('Create case').item.json.id + '/compose' }}",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify({}) }}",
                "options": {},
            },
        ),
        node(
            "store-report",
            "Store report",
            "n8n-nodes-base.httpRequest",
            4.2,
            2080,
            420,
            {
                "method": "POST",
                "url": "={{ 'http://checker:8000/cases/' + $('Create case').item.json.id + '/report' }}",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json) }}",
                "options": {},
            },
        ),
    ]
    workflow = {
        "name": "KitchenLab",
        "nodes": nodes,
        "connections": {
            "Start case": {"main": [[{"node": "Create case", "type": "main", "index": 0}]]},
            "Create case": {"main": [[{"node": "Respond with case", "type": "main", "index": 0}]]},
            "Respond with case": {
                "main": [[
                    {"node": "Recipe investigator", "type": "main", "index": 0},
                    {"node": "Hold for tools", "type": "main", "index": 0},
                ]]
            },
            "Hold for tools": {"main": [[{"node": "Compose report", "type": "main", "index": 0}]]},
            "Recipe investigator": {"main": [[{"node": "Parse recipes", "type": "main", "index": 0}]]},
            "Parse recipes": {"main": [[{"node": "Store recipes", "type": "main", "index": 0}]]},
            "Store recipes": {"main": [[{"node": "Science investigator", "type": "main", "index": 0}]]},
            "Science investigator": {"main": [[{"node": "Parse checks", "type": "main", "index": 0}]]},
            "Parse checks": {"main": [[{"node": "Fact-checker", "type": "main", "index": 0}]]},
            "Fact-checker": {"main": [[{"node": "Parse report", "type": "main", "index": 0}]]},
            "Parse report": {"main": [[{"node": "Store report", "type": "main", "index": 0}]]},
            "Token Factory": {
                "ai_languageModel": [[
                    {"node": "Recipe investigator", "type": "ai_languageModel", "index": 0},
                    {"node": "Science investigator", "type": "ai_languageModel", "index": 0},
                    {"node": "Fact-checker", "type": "ai_languageModel", "index": 0},
                ]]
            },
            "TavilySearch": {"ai_tool": [[{"node": "Recipe investigator", "type": "ai_tool", "index": 0}]]},
            "TavilyExtract": {"ai_tool": [[{"node": "Recipe investigator", "type": "ai_tool", "index": 0}]]},
            "CatalogLookup": {"ai_tool": [[{"node": "Science investigator", "type": "ai_tool", "index": 0}]]},
            "ScienceSearch": {"ai_tool": [[{"node": "Science investigator", "type": "ai_tool", "index": 0}]]},
            "TechniqueChecks": {"ai_tool": [[{"node": "Science investigator", "type": "ai_tool", "index": 0}]]},
            "FollowUpSearch": {"ai_tool": [[{"node": "Fact-checker", "type": "ai_tool", "index": 0}]]},
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": True},
    }
    destination = Path(__file__).resolve().parents[1] / "n8n" / "workflows" / "kitchenlab.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
