# KitchenLab

KitchenLab investigates one cooking question, compares professional recipes with culinary science, and reports which techniques are observed in retrieved sources, contradicted by those sources, or still unknown.

## Claim boundary

- Identify plausible techniques and the evidence behind them. Do not claim a recipe is proven in the user's kitchen.
- `NOT OBSERVED` means the technique was not found in the named retrieved sources. It does not mean the technique fails.
- `OBSERVED` means the technique appeared in inspected recipe or science pages. It does not mean the method is best.
- `CONTRADICTED` means retrieved sources disagree. It does not pick a winner by default.
- Public research mode only. Read public pages retrieved during the case. Do not scrape private recipes, paywall-bypass, or invent citations.
- Distinguish results supported by published tests from outcomes the system only predicts. Label experiment lines `supported` or `predicted`.

## Evidence

- Use only these statuses: `OBSERVED`, `REPORTED`, `INFERRED`, `CONTRADICTED`, `UNKNOWN`, `NOT OBSERVED`.
- A finding needs a recipe source and a science source, or an explicit gap when one side was not retrieved.
- `NOT OBSERVED` always includes the inspected scope.
- Primary URLs must be URLs Tavily retrieved during that case. Do not invent citations.
- Technique statuses for deterministic checks come from the checker. The analyst may explain them and may request one follow-up search when a material conflict is `UNKNOWN`.
- Keep published and retrieved dates distinct.
- Research log lines are recorded tool calls and stored conclusion changes only.
- Cap a case at five techniques extracted from the retrieved pages.

## Sample question

The sample question is crispy oven-roasted potatoes:

- "What's the best way to make crispy oven-roasted potatoes, and why do recipes disagree?"

For that sample the catalog names parboiling, roughening the surface, baking soda in the cooking water, high-temperature roasting, and drying before oiling.

## UI

Implement `DESIGN.md`. The interface is a ChatGPT-style thread. Do not add a confidence score or a second visual system.

## Stack

- n8n orchestrates three Token Factory agents: recipe investigator, science investigator, fact-checker.
- Inference uses `NEBIUS_API_KEY` and `NEBIUS_MODEL` at `https://api.tokenfactory.nebius.com/v1`.
- Web retrieval uses the Tavily search and extract APIs. The checker records each call.
- The checker owns case state, the culinary catalog, deterministic technique checks, and the experiment simulator.
- The workbench polls the case API.

## Secrets

Never commit or print `NEBIUS_API_KEY` or `TAVILY_API_KEY`. Read them from the environment.
