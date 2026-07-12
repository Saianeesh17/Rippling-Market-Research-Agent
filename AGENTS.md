# Agent Guide

This repository is a local prototype for a GTM competitive research agent. The main path takes a competitor, gathers public-source evidence, asks category-specific report agents to write detailed sections, and then writes a markdown brief plus structured JSON/run logs.

## First Reads

- `README.md` covers user setup, environment variables, and high-level product behavior.
- `docs/agents/pipeline.md` explains the run graph and what each node owns.
- `docs/agents/llm-and-output.md` explains LLM provider selection, report assembly, markdown cleanup, and the report Q&A loop.
- `docs/agents/tools-and-cache.md` explains real source tools, cache behavior, and API-cost guardrails.

## Common Commands

Run these from the repo root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m src.main --competitor "Gusto" --no-llm
.\.venv\Scripts\python.exe -m src.main --competitor "Gusto" --use-llm
.\.venv\Scripts\python.exe -m src.main --competitor "Gusto" --use-llm --interactive
```

Use `--no-llm` for deterministic offline checks. Use `--use-llm` only when `.env` has a configured provider and the needed source API keys.

## Repo Map

- `src/main.py`: CLI entry point and optional post-report Q&A loop.
- `src/graph.py`: ordered pipeline orchestration.
- `src/state.py`: mutable run state shared across nodes.
- `src/schemas.py`: Pydantic contracts for competitors, sources, claims, opportunities, reports, logs, and evals.
- `src/nodes/`: pipeline nodes. Each file should own one stage of reasoning or output assembly.
- `src/tools/`: bounded public-source tool adapters and dummy offline tools.
- `src/llm/`: provider clients and provider selection from `.env`.
- `src/cache.py`: local JSON cache helpers used by API tools.
- `tests/`: unit tests for tools, nodes, LLM wrappers, report formatting, and the graph.

## Guardrails

- Never print, commit, or copy values from `.env`. Logs and JSON should keep request details redacted.
- LLM runs use real-source mode. Dummy tools remain for no-LLM/offline testing and should not backfill real LLM reports.
- The final LLM should synthesize the brief, not decide the canonical Rippling opportunities. `src/nodes/rippling_opportunity_mapper.py` maps those deterministically from grounded evidence.
- Category report sections are canonical detailed findings. `src/nodes/output_writer.py` replaces any final-LLM generated detailed category block with the preserved subagent sections.
- Markdown cleanup is intentional. Several providers sometimes return single-line headings and source lists; the normalizers prevent entire sections from rendering as one blue heading/link block.
- Cache TTLs are part of the cost-control model. Prefer tightening payloads and cache keys before raising result limits.

## When Changing Behavior

- Add or update focused tests with the change. Formatting regressions are easy to miss by reading markdown alone.
- If a new real API tool is added, wire it through `src/tools/registry.py`, include cache/log behavior, and document the required env vars.
- If a report section changes, check both the markdown file and the JSON payload because downstream Q&A uses the saved report context.
