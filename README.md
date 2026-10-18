# BreachMirror

BreachMirror reconstructs a documented security incident and checks which of its prerequisites are visible in one authorized repository.

The sample incident is the July 2026 OpenAI–Hugging Face intrusion:

- Hugging Face, published 16 July 2026: https://huggingface.co/blog/security-incident-july-2026
- OpenAI, published 26 August 2026: https://openai.com/index/hugging-face-incident-and-the-road-ahead/

The demo target is `demo-target/before` in this repository. The checker reads that tree, or one public GitHub URL. It does not scan other hosts, validate credentials, or claim that a repository is safe.

## What a run does

n8n runs three Token Factory agents. The incident investigator searches and extracts with Tavily, then looks up MITRE ATLAS ids. The infrastructure investigator calls the deterministic checker. The threat analyst compares the two. If the authorization check is still unknown, it may call one follow-up that includes `docs/`. The workbench shows the tool calls that were actually recorded.

Inference uses Nebius Token Factory at `https://api.tokenfactory.nebius.com/v1`. Set `NEBIUS_MODEL` to the Beam id from the catalog, or to `MiniMaxAI/MiniMax-M3`. Web retrieval uses the Tavily search and extract APIs. The checker stores every retrieved URL and rejects a primary citation that was not retrieved in that case.

## Run it

Requirements: Docker, a Token Factory key, and a Tavily key.

```bash
cp .env.example .env
# fill in NEBIUS_API_KEY, NEBIUS_MODEL, and TAVILY_API_KEY
docker compose up --build
python3 scripts/bootstrap.py
```

Open http://localhost:8080. Choose **Load sample case**. The header says the case is public sample evidence.

If bootstrap cannot sign in, open http://localhost:5678, create the owner, and run `python3 scripts/bootstrap.py` again. In the Token Factory credential, set the base URL to `https://api.tokenfactory.nebius.com/v1` and turn off the OpenAI Responses API on the chat model if the node enables it. The model id is `NEBIUS_MODEL`.

A report with no sources means `TAVILY_API_KEY` is missing or was not visible to the checker container.

## Checks without the model

Python 3.12 or newer:

```bash
cd checker
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn breachmirror.api:app --app-dir src --port 8000
```

`pytest` stubs GitHub and does not call Token Factory or Tavily.

## Workbench during development

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to the checker on port 8000 and `/hooks` to n8n on port 5678.

## Limits

`NOT OBSERVED` means the condition was not found in the inspected files. The simulation re-check only re-evaluates the unpinned model revision against `demo-target/after`. Neither result means the application is secure.
