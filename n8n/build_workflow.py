"""Write the BreachMirror n8n workflow export."""

from __future__ import annotations

import json
from pathlib import Path

CHECKER = "http://checker:8000"
CREDENTIAL_ID = "TOKEN_FACTORY_CREDENTIAL_ID"

INCIDENT_PROMPT = """You reconstruct one documented security incident from pages Tavily retrieves during this case.
Do not predict that a breach will occur. Do not write exploit steps, payloads, or reproduction instructions.
Search, then extract the primary pages you will cite. Look up ATLAS techniques and use only ids the lookup returns.
Keep the Hugging Face account published 16 July 2026 and the OpenAI account published 26 August 2026 distinct when both appear.
Separate occurred dates from disclosed dates. If a date is not in the retrieved page, write "Date unknown".
Return JSON only. source_type for disclosure pages is Primary. Passages are short quotations from retrieved pages.
Shape:
{"summary_known":"","summary_unknown":"","open_questions":[],"sources":[{"ref":"01","title":"","url":"","source_type":"Primary","published":null,"retrieved":"2026-10-18","passage":""}],"timeline":[{"id":"","title":"","summary":"","occurred":"Date unknown","disclosed":"Date unknown","status":"REPORTED","source_refs":["01"]}]}
Allowed status values: OBSERVED, REPORTED, INFERRED, CONTRADICTED, UNKNOWN, NOT OBSERVED."""

INFRA_PROMPT = """You inspect only the authorized target repository named in the user message.
Call the source-check tool once. Do not claim a condition the tool did not return. Do not validate credentials or scan any other host.
Return JSON only: {"scope":"","observations":[]} copying the tool's scope and observations."""

ANALYST_PROMPT = """You compare an incident reconstruction with deterministic repository checks.
Use the check status for each target condition. Do not upgrade it.
Finding ids map to check ids:
exposed-credentials = exposed_token_literal
untrusted-load = unpinned_pretrained
agent-tools = write_or_network_tool
authorization = authorization_step
isolation = isolation
If authorization_step is UNKNOWN, call the authorization-doc tool once. That is the only extra check you may run.
You may make one Tavily search if a material disclosure detail is still missing.
Do not write exploit steps, payloads, or proof-of-concept code. Do not say the application is secure.
Every finding that is not UNKNOWN needs one Primary source ref and one Code or Documentation source ref.
NOT OBSERVED findings must copy the inspected scope.
recommendation_limits must say that this does not establish that the application is secure.
Return JSON only with summary_known, summary_unknown, open_questions, recommendation, recommendation_limits, sources, timeline, findings.
Each finding has id, prerequisite, observation, why_it_matters, limitations, next_check, status, scope, evidence_refs, atlas_ids, mitigation_ids, gap.
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


def http_tool(name: str, description: str, method: str, url: str, body: str | None, x: int, y: int) -> dict:
    parameters: dict = {
        "toolDescription": description,
        "method": method,
        "url": url,
        "options": {},
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
    incident = node(
        "incident-investigator",
        "Incident investigator",
        "@n8n/n8n-nodes-langchain.agent",
        1.8,
        720,
        280,
        {
            "promptType": "define",
            "text": "=Incident: {{ $('Create case').item.json.incident }}\nCase id: {{ $('Create case').item.json.id }}",
            "options": {"systemMessage": INCIDENT_PROMPT, "maxIterations": 8},
        },
    )
    infra = node(
        "infrastructure-investigator",
        "Infrastructure investigator",
        "@n8n/n8n-nodes-langchain.agent",
        1.8,
        720,
        560,
        {
            "promptType": "define",
            "text": "=Target: {{ $('Create case').item.json.target }}\nCase id: {{ $('Create case').item.json.id }}\nCall the source-check tool once.",
            "options": {"systemMessage": INFRA_PROMPT, "maxIterations": 3},
        },
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
        "threat-analyst",
        "Threat analyst",
        "@n8n/n8n-nodes-langchain.agent",
        1.8,
        1480,
        420,
        {
            "promptType": "define",
            "text": "=Incident JSON:\n{{ JSON.stringify($('Parse incident').item.json) }}\n\nCheck JSON:\n{{ JSON.stringify($('Parse checks').item.json) }}\n\nCase id: {{ $('Create case').item.json.id }}\nTarget: {{ $('Create case').item.json.target }}",
            "options": {"systemMessage": ANALYST_PROMPT, "maxIterations": 4},
        },
    )
    tools = [
        http_tool(
            "Tavily search",
            "Search the public web with Tavily. Arguments: query, and depth basic or advanced.",
            "POST",
            f"{CHECKER}/tools/tavily/search",
            '={{ JSON.stringify({ case_id: $(\'Create case\').item.json.id, query: $fromAI(\'query\', \'search query\', \'string\'), depth: $fromAI(\'depth\', \'basic or advanced\', \'string\') }) }}',
            980,
            160,
        ),
        http_tool(
            "Tavily extract",
            "Extract text from https URLs already returned by Tavily search.",
            "POST",
            f"{CHECKER}/tools/tavily/extract",
            '={{ JSON.stringify({ case_id: $(\'Create case\').item.json.id, urls: $fromAI(\'urls\', \'https urls\', \'string\').split(\'\\n\').filter(Boolean) }) }}',
            980,
            280,
        ),
        http_tool(
            "ATLAS lookup",
            "Look up MITRE ATLAS techniques and mitigations by id or name.",
            "GET",
            "={{ 'http://checker:8000/atlas/search?case_id=' + $('Create case').item.json.id + '&q=' + encodeURIComponent($fromAI('query', 'technique or mitigation query', 'string')) }}",
            None,
            980,
            400,
        ),
        http_tool(
            "Source checks",
            "Run deterministic checks on the authorized target. Does not read docs/.",
            "POST",
            f"{CHECKER}/checks/run",
            '={{ JSON.stringify({ case_id: $(\'Create case\').item.json.id, target: $(\'Create case\').item.json.target, include_docs: false }) }}',
            980,
            560,
        ),
        http_tool(
            "Authorization docs",
            "Re-run the checks including docs/. Call only when authorization_step is UNKNOWN.",
            "POST",
            f"{CHECKER}/checks/run",
            '={{ JSON.stringify({ case_id: $(\'Create case\').item.json.id, target: $(\'Create case\').item.json.target, include_docs: true }) }}',
            1680,
            280,
        ),
        http_tool(
            "Follow-up search",
            "One Tavily search for a missing disclosure detail.",
            "POST",
            f"{CHECKER}/tools/tavily/search",
            '={{ JSON.stringify({ case_id: $(\'Create case\').item.json.id, query: $fromAI(\'query\', \'follow-up query\', \'string\'), depth: \'advanced\' }) }}',
            1680,
            400,
        ),
    ]
    parse_js = """const raw = $input.first().json.output || '';
const start = raw.indexOf('{');
const end = raw.lastIndexOf('}');
if (start < 0 || end < start) {
  throw new Error('The agent did not return JSON.');
}
return [{ json: JSON.parse(raw.slice(start, end + 1)) }];"""
    nodes = [
        node(
            "start-case",
            "Start case",
            "n8n-nodes-base.webhook",
            2,
            240,
            420,
            {"httpMethod": "POST", "path": "breachmirror", "responseMode": "responseNode", "options": {}},
            {"webhookId": "breachmirror-start"},
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
                "jsonBody": "={{ JSON.stringify({ incident: $json.body.incident, target: $json.body.target, sample: Boolean($json.body.sample) }) }}",
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
        incident,
        infra,
        node(
            "parse-incident",
            "Parse incident",
            "n8n-nodes-base.code",
            2,
            1100,
            280,
            {"language": "javaScript", "jsCode": parse_js},
        ),
        node(
            "store-incident",
            "Store incident",
            "n8n-nodes-base.httpRequest",
            4.2,
            1280,
            280,
            {
                "method": "POST",
                "url": f"={CHECKER}/cases/{{{{ $('Create case').item.json.id }}}}/incident",
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
        ),
        node(
            "join-investigations",
            "Join investigations",
            "n8n-nodes-base.merge",
            3,
            1360,
            420,
            {"mode": "combine", "combineBy": "combineAll", "options": {}},
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
                "url": f"={CHECKER}/cases/{{{{ $('Create case').item.json.id }}}}/report",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json) }}",
                "options": {},
            },
        ),
    ]
    # The f-string above doubled braces incorrectly for n8n expressions that already use {{ }}.
    # Fix the two URLs that were meant to be n8n expressions.
    for item in nodes:
        if item["name"] == "Store incident":
            item["parameters"]["url"] = "={{ 'http://checker:8000/cases/' + $('Create case').item.json.id + '/incident' }}"
        if item["name"] == "Store report":
            item["parameters"]["url"] = "={{ 'http://checker:8000/cases/' + $('Create case').item.json.id + '/report' }}"
    workflow = {
        "name": "BreachMirror",
        "nodes": nodes,
        "connections": {
            "Start case": {"main": [[{"node": "Create case", "type": "main", "index": 0}]]},
            "Create case": {"main": [[{"node": "Respond with case", "type": "main", "index": 0}]]},
            "Respond with case": {
                "main": [[
                    {"node": "Incident investigator", "type": "main", "index": 0},
                    {"node": "Infrastructure investigator", "type": "main", "index": 0},
                ]]
            },
            "Incident investigator": {"main": [[{"node": "Parse incident", "type": "main", "index": 0}]]},
            "Parse incident": {"main": [[{"node": "Store incident", "type": "main", "index": 0}]]},
            "Store incident": {"main": [[{"node": "Join investigations", "type": "main", "index": 0}]]},
            "Infrastructure investigator": {"main": [[{"node": "Parse checks", "type": "main", "index": 0}]]},
            "Parse checks": {"main": [[{"node": "Join investigations", "type": "main", "index": 1}]]},
            "Join investigations": {"main": [[{"node": "Threat analyst", "type": "main", "index": 0}]]},
            "Threat analyst": {"main": [[{"node": "Parse report", "type": "main", "index": 0}]]},
            "Parse report": {"main": [[{"node": "Store report", "type": "main", "index": 0}]]},
            "Token Factory": {
                "ai_languageModel": [[
                    {"node": "Incident investigator", "type": "ai_languageModel", "index": 0},
                    {"node": "Infrastructure investigator", "type": "ai_languageModel", "index": 0},
                    {"node": "Threat analyst", "type": "ai_languageModel", "index": 0},
                ]]
            },
            "Tavily search": {"ai_tool": [[{"node": "Incident investigator", "type": "ai_tool", "index": 0}]]},
            "Tavily extract": {"ai_tool": [[{"node": "Incident investigator", "type": "ai_tool", "index": 0}]]},
            "ATLAS lookup": {"ai_tool": [[{"node": "Incident investigator", "type": "ai_tool", "index": 0}]]},
            "Source checks": {"ai_tool": [[{"node": "Infrastructure investigator", "type": "ai_tool", "index": 0}]]},
            "Authorization docs": {"ai_tool": [[{"node": "Threat analyst", "type": "ai_tool", "index": 0}]]},
            "Follow-up search": {"ai_tool": [[{"node": "Threat analyst", "type": "ai_tool", "index": 0}]]},
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": True},
    }
    destination = Path(__file__).resolve().parents[1] / "n8n" / "workflows" / "breachmirror.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
