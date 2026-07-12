# Tools And Cache Guide

Source tools live under `src/tools/` and are selected by category in `src/tools/registry.py`. All tools should return `ToolResult` objects with source records and observable logs.

## Real Tools

- Exa domain resolver: finds and caches official company domains.
- Exa LinkedIn resolver: finds and caches the company LinkedIn page before Apify runs.
- Exa Twitter/X resolver: finds and caches the official handle before the X posts actor runs.
- Exa research tools: collect website positioning, product pages, pricing, and press/news evidence.
- Apify LinkedIn tool: fetches recent LinkedIn company posts, currently capped at 5 posts for testing.
- Apify X/Twitter tool: fetches recent posts only when a valid handle is resolved, currently capped at 5 posts for testing.
- Adyntel tools: fetch Meta, LinkedIn, and Google ad-library data, currently capped at 5 ads per platform for testing.

Dummy tools remain in the registry for deterministic no-LLM runs. Real-source mode filters them out.

## Cache Model

`src/cache.py` stores JSON files under `AGENT_CACHE_DIR`, defaulting to `.agent_cache`.

- Company domain, LinkedIn URL, and Twitter/X handle resolution are effectively stable and cached without TTL.
- Exa page research defaults to a 24 hour TTL.
- Apify LinkedIn and X/Twitter post data default to a 5 hour TTL.
- Adyntel ad data defaults to a 120 hour TTL.

Cache hits should still be logged so a run can explain why no network request was made.

## Env Vars To Check

Core LLM:

```text
USE_LLM=auto
LLM_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=...
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=...
```

Source APIs:

```text
EXA_API_KEY=...
APIFY_TOKEN=...
ADYNTEL_EMAIL=...
ADYNTEL_API_KEY=...
```

Cost and cache controls:

```text
AGENT_CACHE_DIR=.agent_cache
EXA_RESEARCH_MAX_RESULTS=5
EXA_RESEARCH_CACHE_TTL_HOURS=24
APIFY_LINKEDIN_MAX_POSTS_PER_COMPANY=5
APIFY_LINKEDIN_CACHE_TTL_HOURS=5
APIFY_X_TWITTER_MAX_POSTS=5
APIFY_X_TWITTER_CACHE_TTL_HOURS=5
ADYNTEL_MAX_ADS_PER_PLATFORM=5
ADYNTEL_AD_CACHE_TTL_HOURS=120
```

## Logging Expectations

Every real API call should add enough detail to debug failures without leaking credentials:

- tool name, category, query, status, and source count,
- redacted request summary,
- compact response summary,
- cache hit or miss,
- error text when a call fails.

The full run log is written to `outputs/{competitor}_run.log`. The JSON report stores compact logs for downstream inspection.
