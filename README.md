# Competitive Intel Agent

Local prototype of a conversational competitive marketing intelligence agent for a GTM Engineer take-home assessment. It uses deterministic dummy tools and dummy public-source-style content so the full pipeline can be tested without scraping, API keys, paid data, or real web access.

## What It Does

Given a competitor name or domain, the agent generates:

- A markdown competitive brief in `outputs/`.
- A structured JSON report with sources, extracted claims, confidence scores, timestamps, tool call logs, coverage gaps, recommendations, and eval scores.
- A run log in `outputs/` with pipeline logs, tool calls, planner decision, eval summary, and any raw LLM responses.

The prototype includes dummy source content for Gusto, Deel, BambooHR, and a lower-confidence generic fallback.

## Real API Tools

The social discovery category can call a real Apify actor for public LinkedIn company posts, and the paid ads category can call Adyntel for public Meta, LinkedIn, and Google ad library results:

```text
EXA_API_KEY=...
EXA_RESEARCH_MAX_RESULTS=5
EXA_RESEARCH_CACHE_TTL_HOURS=24
EXA_RESEARCH_CONTENT_MAX_AGE_HOURS=24
EXA_PRESS_RECENCY_MONTHS=18
APIFY_TOKEN=...
APIFY_LINKEDIN_MAX_POSTS_PER_COMPANY=5
AGENT_CACHE_DIR=.agent_cache
APIFY_LINKEDIN_CACHE_TTL_HOURS=5

ADYNTEL_EMAIL=...
ADYNTEL_API_KEY=...
ADYNTEL_BASE_URL=https://api.adyntel.com
ADYNTEL_MAX_ADS_PER_PLATFORM=5
ADYNTEL_AD_CACHE_TTL_HOURS=120
```

Exa is used in multiple places:

- Website positioning, product pages, pricing, and press/news source agents search official competitor pages first, using the resolved company domain when available.
- If official pages do not return usable evidence, those agents fall back to external public sources. External evidence is marked third-party and gets lower reliability/confidence.
- Low-quality social domains are dropped for these page-research categories.
- Press/news searches use Exa's `news` category for external results and default to the last 18 months.

The page-research tools use capped page extraction:

```json
{
  "type": "auto",
  "num_results": 5,
  "contents": {
    "highlights": {"query": "{category-specific research question}", "maxCharacters": 2000},
    "text": {"maxCharacters": 2600},
    "maxAgeHours": 24
  }
}
```

Before Apify runs, the social source agent calls Exa to resolve the competitor's LinkedIn company URL. That prevents the Apify tool from guessing based on the company name alone. The Exa LinkedIn search uses:

```json
{
  "query": "{competitor} official LinkedIn company page",
  "type": "auto",
  "num_results": 5,
  "include_domains": ["linkedin.com"],
  "contents": {"highlights": true}
}
```

The resolved LinkedIn company URL is then passed into the Apify actor as `companyUrls[0]`.

The actor endpoint is:

```text
https://api.apify.com/v2/acts/automation-lab~linkedin-company-posts-scraper/run-sync-get-dataset-items
```

For now the tool always sends `maxPostsPerCompany=5` and `maxCompanies=1` so test runs stay small. If `APIFY_TOKEN` is missing or the actor fails, the pipeline logs the failed tool call and continues with dummy social tools.

Before Adyntel runs, the paid ads source agent resolves the competitor's website domain. If the competitor profile already has a domain, it normalizes that value to bare `company.com` format and skips Exa. If the profile has no domain, it calls Exa with:

```json
{
  "query": "{competitor} official website",
  "type": "auto",
  "num_results": 5,
  "contents": {"highlights": true}
}
```

The resolved domain is passed to the Adyntel direct REST endpoints:

```text
POST https://api.adyntel.com/facebook
POST https://api.adyntel.com/linkedin
POST https://api.adyntel.com/google
```

For now each Adyntel platform adapter logs and returns at most 5 ads. If `ADYNTEL_EMAIL` or `ADYNTEL_API_KEY` is missing, the pipeline logs the failed tool call and continues with dummy paid-ad tools.

Successful API tool calls attach redacted request details and raw API output to `tool_call_logs` in the JSON report. The same API request/output blocks are written into `outputs/{competitor}_run.log`.

### API Cache

To reduce API spend, real API tools use a local JSON cache:

- Exa LinkedIn URL resolution is cached indefinitely by competitor/domain. The tool only calls Exa on cache miss.
- Exa company domain resolution is cached indefinitely by competitor/domain. Existing competitor profile domains are normalized and cached without an Exa call.
- Exa page-research data is cached by tool/category/company/input. The default TTL is 24 hours.
- Apify LinkedIn post data is cached by LinkedIn URL and actor input. The default TTL is 5 hours because company posts can change.
- Adyntel ad data is cached by platform/domain/input. The default TTL is 120 hours, or 5 days, because ad libraries can change but do not need to be re-queried during quick iteration.
- `AGENT_CACHE_DIR` controls the cache location. It defaults to `.agent_cache`, which is ignored by git.
- `EXA_RESEARCH_CACHE_TTL_HOURS`, `EXA_RESEARCH_CONTENT_MAX_AGE_HOURS`, and `EXA_PRESS_RECENCY_MONTHS` control Exa page-research cost/freshness.
- `APIFY_LINKEDIN_CACHE_TTL_HOURS` controls the Apify cache expiry.
- `ADYNTEL_AD_CACHE_TTL_HOURS` controls the Adyntel cache expiry.

Cache hits are still logged in `tool_call_logs` with `api_request.cache_hit=true` and `api_response.cache_hit=true`.

## Category Report Subagents

After source analysis and evidence extraction, each research category gets its own report-section subagent:

- Website positioning
- Product pages
- Pricing and packaging
- Paid ads
- Social and LinkedIn posts
- Press and news
- Comparison pages

Each subagent receives only its category's sources and analyses and generates a markdown section with numeric inline citations such as `[1]`. Each section ends with a `Sources` list mapping citation numbers to source titles and URLs. The final LLM call is reserved for synthesis: executive summary, confidence and gaps, Rippling opportunities, and campaign implications.

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

## Optional LLM Mode

The repo includes `.env` and `.env.example`. Groq is the default provider:

```text
LLM_PROVIDER=groq
USE_LLM=auto
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_OPENAI_BASE_URL=https://api.groq.com/openai/v1
```

Anthropic models through the Qualcomm QGenie gateway are also supported:

```text
LLM_PROVIDER=anthropic
USE_LLM=auto
ANTHROPIC_BASE_URL=https://qgenie-api.qualcomm.com/
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_VERIFY_SSL=false
ANTHROPIC_MODEL=claude-opus-4-8
```

The code uses Anthropic's native Messages API shape against `{ANTHROPIC_BASE_URL}/v1/messages`. `ANTHROPIC_AUTH_TOKEN` is passed as the gateway credential. `ANTHROPIC_VERIFY_SSL=false` disables SSL verification only for that Anthropic/QGenie client.

The app uses Groq through its OpenAI-compatible endpoint, so the same chat-completions wrapper works for planner decisions and final report writing.

Google AI Studio is also supported:

```text
LLM_PROVIDER=google
USE_LLM=auto
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
GEMINI_OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

OpenAI is still supported:

```text
LLM_PROVIDER=openai
USE_LLM=auto
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.5
OPENAI_BASE_URL=
```

With `LLM_PROVIDER=auto`, Anthropic/QGenie is preferred when `ANTHROPIC_AUTH_TOKEN` is set, then Groq, then Gemini, then OpenAI. With `USE_LLM=auto`, the CLI uses an LLM when the selected provider has a key and otherwise uses deterministic fallback logic. You can override LLM usage per run:

```bash
python -m src.main --competitor "Gusto" --use-llm
python -m src.main --competitor "Gusto" --no-llm
```

Current LLM-backed steps:

- Planner decision: the model receives source coverage, gaps, replanning limits, and the bounded tool registry, then returns a validated `PlannerDecision`.
- Final markdown report: the model receives the structured dummy report data and writes the final markdown brief.

The CLI prints raw LLM responses for now to make debugging easier. The same responses are also written to the generated `outputs/{competitor}_run.log` file and included in `llm_call_logs` in the JSON output.

The discovery tools and source data are still dummy data. The LLM does not scrape, browse, or call tools directly.

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
- outputs/gusto_run.log

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
