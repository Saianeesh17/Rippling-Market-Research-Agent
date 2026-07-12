# LLM And Output Guide

The project supports OpenAI-compatible providers, Anthropic's Messages API, and compatible gateways. Provider selection lives in `src/llm/service.py` and reads `.env` through `python-dotenv`.

## Provider Selection

- `LLM_PROVIDER=anthropic` uses `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`.
- `LLM_PROVIDER=groq` uses `GROQ_API_KEY` with the OpenAI-compatible Groq endpoint.
- `LLM_PROVIDER=google` or `gemini` uses a Google AI Studio key through its OpenAI-compatible endpoint.
- `LLM_PROVIDER=openai` uses `OPENAI_API_KEY`.
- `LLM_PROVIDER=auto` chooses the first configured provider in service order.

Do not expose `.env` values in CLI output, docs, logs, or commits.

## LLM Call Roles

- `planner_decision`: decides whether one additional bounded search pass is useful.
- Category report section calls: one call per category, each with only that category's sources and analyses.
- `rippling_opportunity_mapper`: generates the canonical Rippling market opportunities from static Rippling positioning and grounded target-company evidence, with schema validation and deterministic fallback.
- `final_markdown_report`: synthesizes the full brief from compacted report context and preserved category sections.
- Report Q&A calls: answer from the generated brief when possible; use Exa follow-up search when the answer is not already in the report.

## Report Assembly Rules

The final report intentionally has two layers:

- The final LLM writes the main narrative, executive summary, gaps, confidence notes, and synthesis.
- Category subagent sections remain the canonical detailed category findings. `output_writer` replaces a generated detailed category section with the preserved subagent markdown so detail and citation lists are not lost.

The Rippling opportunities subsection is appended near the end from mapper-owned state, not chosen by the final report LLM. In LLM runs, the mapper generates those opportunities from Rippling's static positioning and grounded target-company evidence; if that call fails, the deterministic fallback keeps the section present and source-grounded.

## Markdown Formatting

Provider output can collapse headings, prose, and sources onto one line. When that happens, markdown renderers can treat entire paragraphs as headings or links. The cleanup helpers in `category_report_sections` and `output_writer` normalize:

- opening category headings,
- inline `Sources` blocks,
- duplicate source lists,
- category headings that include body text on the same line,
- template placeholders such as `{{product.name}}`.

When changing markdown prompts or output assembly, add tests for rendered structure rather than only checking that a string exists.

## Token And Cost Controls

The final report uses compact JSON context, but the markdown brief itself is allowed to stay detailed. If provider limits are hit, reduce the JSON payload or per-tool snippets before shortening the generated brief. Prefer:

- cached API results,
- smaller source snippets,
- per-category LLM sections,
- deterministic late sections,
- lower result limits during testing.
