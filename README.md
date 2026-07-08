# Competitive Intel Agent

Local prototype of a conversational competitive marketing intelligence agent for a GTM Engineer take-home assessment. It uses deterministic dummy tools and dummy public-source-style content so the full pipeline can be tested without scraping, API keys, paid data, or real web access.

## What It Does

Given a competitor name or domain, the agent generates:

- A markdown competitive brief in `outputs/`.
- A structured JSON report with sources, extracted claims, confidence scores, timestamps, tool call logs, coverage gaps, recommendations, and eval scores.

The prototype includes dummy source content for Gusto, Deel, BambooHR, and a lower-confidence generic fallback.

## Architecture

```text
User Input
  -> Competitor Resolver
  -> Initial Research Planner
  -> Tool-Constrained Source Discovery
  -> Source Coverage Review
  -> Coverage Gap Detection
  -> Planner Decision / Replanning
  -> Source Analysis
  -> Evidence Extraction + Claim Store
  -> Messaging + Positioning Analyzer
  -> Recent Change Detector
  -> Rippling Opportunity Mapper
  -> Campaign Angle Generator
  -> Eval Layer
  -> Markdown + JSON Output
```

## Why This Is Agentic

The agent is bounded but not a linear scraper:

- A tool registry assigns each source category only the tools it is allowed to use.
- Category-specific discovery agents run website, product, pricing, ads, social, press/news, and comparison workflows.
- Tool calls are observable in logs and final JSON.
- Coverage is scored before analysis so weak, partial, or missing sections can be caveated.
- Pricing can use third-party public sources, but those sources receive lower reliability and confidence.
- Claims must be source-grounded before they feed messaging, opportunity, and campaign recommendations.
- The eval layer checks grounding, source coverage, JSON validity, recommendation quality, public-source compliance, and third-party caveats.

## How To Run With A Python Venv

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m src.main --competitor "Gusto"
pytest
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m src.main --competitor "Gusto"
pytest
```

The `.venv/` directory is ignored by git.

## CLI Examples

```bash
python -m src.main --competitor "Gusto"
python -m src.main --competitor "Deel" --interactive
python -m src.main --competitor "unknown competitor"
```

Example output:

```text
Resolved competitor: Gusto / gusto.com

Running source discovery using bounded tool registry...

Tool calls:
- DummyHomepageTool -> 1 source
- DummyThirdPartyPricingTool -> 1 source

Generated:
- outputs/gusto_brief.md
- outputs/gusto_data.json

Eval summary:
Overall quality score: 0.86
Claim grounding score: 1.0
Third-party caveat score: 0.9
```

## How To Replace Dummy Tools Later

Each tool subclasses `BaseSourceTool` in `src/tools/base.py` and returns a `ToolResult`. To add real data, replace or add adapters for:

- Website crawler
- Web search API
- Webpage scraper
- Sitemap parser
- Meta Ad Library adapter
- Google Ads Transparency Center adapter
- Twitter/X API adapter
- LinkedIn API adapter
- News/search API
- Pricing page scraper

Keep new tools registered in `src/tools/registry.py` so category agents stay bounded by allowed tools.

## Evaluation Approach

The eval layer checks:

- Source coverage score
- Claim grounding score
- Unsupported claim count
- JSON schema validity
- Recommendation specificity
- Public-source compliance
- Third-party caveat handling
- Overall quality score

Run `pytest` to verify the end-to-end pipeline, schema behavior, registry boundaries, confidence handling, graceful tool failure logging, and planner decisions.
