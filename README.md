# KitchenLab

KitchenLab investigates a cooking question, compares professional recipes with culinary science, and reports which techniques the retrieved sources support, contradict, or leave open.

The sample question is crispy oven-roasted potatoes: why recipes disagree, and which steps have published tests behind them.

The checker looks up techniques in a local culinary catalog and scans the pages Tavily retrieved during that case. It does not cook the dish, scrape private recipes, or claim a method is proven in your kitchen.

## What a run does

n8n runs three Token Factory agents. The recipe investigator searches and extracts professional recipes, then names at most five techniques those pages actually use. The science investigator looks up those techniques in the catalog and searches for food-science explanations. The fact-checker compares the two, marks conflicts, and writes a recipe with a reason for every important step. If a material disagreement is still unknown, it may run one follow-up search. The workbench shows the tool calls that were actually recorded.

A timed fallback can also compose a report from the pages retrieved so far before all three agents finish. A visible report therefore does not by itself mean the full agent workflow has completed; inspect the recorded activity and evidence gaps.

After a report, ask a what-if such as "What if I skip parboiling?" The experiment simulator explains which properties are expected to change and separates published-test support from predicted outcomes.

Inference uses Nebius Token Factory at `https://api.tokenfactory.nebius.com/v1`. Set `NEBIUS_MODEL` to the Beam id from the catalog, or to `MiniMaxAI/MiniMax-M3`. Web retrieval uses the Tavily search and extract APIs. The checker stores every retrieved URL and marks a primary citation as unverified if its URL was not retrieved in that case.

## Run it

Requirements: Git, Docker with Compose, Python 3.11 or newer, a Token Factory key, and a Tavily key.

```bash
git clone https://github.com/tanya-marfel/kitchenlab.git
cd kitchenlab
cp .env.example .env
# fill in NEBIUS_API_KEY, NEBIUS_MODEL, and TAVILY_API_KEY
```

After saving `.env`, export its values for the bootstrap script and start the services:

```bash
set -a
source .env
set +a
docker compose up --build -d
python3 scripts/bootstrap.py
```

Open http://localhost:8080. Ask a cooking question in one message, then send. For the sample, ask about crispy oven-roasted potatoes and why recipes disagree.

If bootstrap cannot sign in, open http://localhost:5678 and create the owner using the `BOOTSTRAP_EMAIL` and `BOOTSTRAP_PASSWORD` from `.env`. If an owner already exists, update those values to match that account. Re-export `.env` as above and run `python3 scripts/bootstrap.py` again. In the Token Factory credential, set the base URL to `https://api.tokenfactory.nebius.com/v1` and turn off the OpenAI Responses API on the chat model if the node enables it. The model id is `NEBIUS_MODEL`.

A report with no sources can indicate a missing `TAVILY_API_KEY` or a retrieval failure. Check that the key is available to the checker container and inspect `docker compose logs checker n8n`.

## Checks without the model

Python 3.11 or newer:

```bash
cd checker
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn kitchenlab.api:app --app-dir src --port 8000
```

`pytest` stubs the model and does not call Token Factory or Tavily.

## Workbench during development

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to the checker on port 8000 and `/hooks` to n8n on port 5678.

## Limits

`NOT OBSERVED` means the technique was not found in the retrieved pages. An experiment only re-evaluates the named change against those pages and the catalog. Neither result was cooked, and neither tests your kitchen.
