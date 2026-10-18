# BreachMirror

BreachMirror reconstructs one documented security incident, inspects one authorized repository, and reports which attack prerequisites are observed, absent from the inspected scope, or still unknown.

## Claim boundary

- Identify plausible exposure to previously observed conditions. Do not predict that a breach will occur.
- `NOT OBSERVED` means the condition was not found in the named scope. It does not mean safe.
- `OBSERVED` means the configuration was found in inspected files. It does not mean the system was compromised or that an exploit would succeed.
- Public research mode only. Read public pages, public GitHub content, and `demo-target/`. Do not scan unrelated organizations, access private repositories, validate credentials, or query cloud IAM.
- Do not write exploit steps, payloads, proof-of-concept code, or reproduction details. Cite the public disclosure and name the condition.

## Evidence

- Use only these statuses: `OBSERVED`, `REPORTED`, `INFERRED`, `CONTRADICTED`, `UNKNOWN`, `NOT OBSERVED`.
- A finding needs an incident source and a target source, or an explicit gap when the target evidence does not exist.
- `NOT OBSERVED` always includes the inspected scope.
- Primary URLs must be URLs Tavily retrieved during that case. Do not invent citations.
- Target statuses for deterministic checks come from the checker. The analyst may explain them and may request one follow-up when a material condition is `UNKNOWN`.
- Keep occurred, disclosed, and retrieved dates distinct.
- Research log lines are recorded tool calls and stored conclusion changes only.

## Incident sample

The sample incident is the July 2026 OpenAI–Hugging Face intrusion.

- Hugging Face, 16 July 2026: https://huggingface.co/blog/security-incident-july-2026
- OpenAI, 26 August 2026: https://openai.com/index/hugging-face-incident-and-the-road-ahead/

Keep the two accounts distinct when they differ. Cap exposure at the five prerequisites in the case contract: exposed write-capable credentials, untrusted model or dataset loading, write-capable or networked agent tools, a separate authorization step, and documented isolation.

## UI

Implement `DESIGN.md`. Do not invent a second visual system, a chat transcript, a marketing page, or a breach-probability score.

## Stack

- n8n orchestrates three Token Factory agents: incident investigator, infrastructure investigator, threat analyst.
- Inference uses `NEBIUS_API_KEY` and `NEBIUS_MODEL` at `https://api.tokenfactory.nebius.com/v1`.
- Web retrieval uses the Tavily search and extract APIs. The checker records each call.
- The checker owns case state, ATLAS lookup, and deterministic repository checks.
- The workbench polls the case API.

## Secrets

Never commit or print `NEBIUS_API_KEY`, `TAVILY_API_KEY`, or `GITHUB_TOKEN`. Read them from the environment.
