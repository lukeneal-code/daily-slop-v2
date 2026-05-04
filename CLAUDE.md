# Working on this repo

## Tone for written articles

The Daily Slop is a satirical British newspaper in the style of *The Daily Mash* and *Private Eye*. The voice is **deadpan, dry, absurdist, and quintessentially British**. Writers mock institutions, politicians, and cultural trends — never individual private citizens, never vulnerable groups.

When editing prompts in `backend/app/agents/prompts/`, keep these rules:

- Headlines must be ≤ 8 words, punchy, tabloid-flavoured (think "FREDDIE STARR ATE MY HAMSTER").
- Subheadlines carry the second irony layer.
- One ridiculous-but-plausible-sounding fictional quote per piece.
- Image prompts must NOT contain `gothic`, `macabre`, `darkly`, `horror`, or speech bubbles. The new style is Charles Addams + Private Eye, not Addams Family.

## Agents

| Agent | Model | Role |
|---|---|---|
| Nigel | Claude Sonnet 4.6 | Main writer. Witty, brief, intelligent. |
| Steve | Grok 4 (xAI) | Risky/left-field pieces. ~25% of stories, never headlines, never `royals`. |
| Elle | GPT-4o | Antagonistic editor. Final word. Stricter on Steve's pieces. |

Pushback rule: a writer may push back **once** if Elle wants a revision. Elle then re-evaluates with the writer's argument. After one pushback + one revision, Elle's verdict stands; if `severity != high`, the article publishes with her note logged; if `severity == high`, it's rejected.

## Stack rules

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, LangGraph, `uv` for env.
- **Frontend**: React 19, Vite, TypeScript, vanilla CSS (no Tailwind — port v1's `newspaper.css`).
- **Infra**: Terraform with GCS remote state. New secrets are created in `bootstrap.sh`; Terraform only references existing secrets via `data` blocks so key material never lands in tfstate.
- **CI/CD**: GitHub Actions auths to GCP via Workload Identity Federation. No long-lived service-account JSON keys.

## v1 reference

The legacy project lives at `/Users/lukeneal/the-daily-slop/` (also at `https://dailyslop.co.uk`). Prefer to **port** v1's CSS/Masthead/Footer verbatim rather than reinvent — the look-and-feel is part of the brand. v1 source files of interest:

- `backend/src/ai/prompts.ts` — Nigel's prompt is a near-verbatim port (drop `darkly humorous, macabre overtones` from line 14).
- `frontend/src/styles/newspaper.css` — full port.
- `frontend/src/components/{Masthead,Footer}.tsx` — port verbatim.

## Repo conventions

- Default to writing **no comments**; add only when the WHY is non-obvious.
- New files belong under their phase's directory; do not invent top-level dirs.
- Tests live next to what they test under `backend/tests/{unit,integration,eval}` and `frontend/src/**/*.test.tsx`.
- Don't add backwards-compat shims or placeholder feature flags. v1 is a separate codebase; v2 starts clean.
