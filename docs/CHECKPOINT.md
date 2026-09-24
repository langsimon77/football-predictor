# Checkpoint

## Latest: 23 Sep 2026, end of Phase 0 (data audit)

### Done
- PRD approved. Lang's answers to Q1 to Q4 logged in `docs/DECISIONS.md`.
- Installed `uv` 0.12.18 and Python 3.12.14. Created the project with pinned dependencies and `uv.lock`. Ran `git init` locally. No commits yet.
- Wrote the polite downloader: named User-Agent, 1 request per 3 s per domain, dated cache, retries.
- Downloaded and audited 44 football-data.co.uk files (2016/17 to 2026/27), `fixtures.csv`, and 22 openfootball files.
- Checked robots.txt and terms for every source in spec S3, plus new candidates.
- Built the canonical team table: 67 clubs, 158 aliases, 2 sources. 72 tests pass. `ruff` and the dash check pass.
- Wrote `docs/DATA_SOURCES.md` and `docs/LEARN.md` chapter 0.

### Phase 0 acceptance checks
| Check | Result |
|---|---|
| Every source in S3 marked Verified or replaced | Met, with two items waiting on Lang's free API keys (football-data.org, API-Football). |
| Mapping test passes for all 2021/22 to 2026/27 teams | Passed, and extended to 2016/17. 72 of 72 tests pass. |

### Open questions for Lang
- D1 to D6 in `docs/DATA_SOURCES.md` section 5.
- Is the robots.txt reading for football-data.co.uk acceptable? See `docs/DATA_SOURCES.md` section 2.
- Which name and email should Git commits use?

### Next actions
| Action | Owner |
|---|---|
| Approve Phase 0, or reply with changes. Decide D1 to D6. | Lang |
| Create an empty public GitHub repo named `football-predictor` and send the URL. | Lang |
| Register free keys at football-data.org and api-football.com. Put them in `.env` in the project folder as `FOOTBALL_DATA_ORG_TOKEN=...` and `API_FOOTBALL_KEY=...`. Do not paste keys into chat. | Lang |
| Phase 1 (pipeline, validation, leakage guard, ledger), then Phase 1F. Target: running on GitHub Actions with a dry run by Wed 7 Oct. | Claude, after approval |

### Facts still unverified
- football-data.org API behaviour. It timed out from this Mac and needs a key.
- API-Football free plan terms and season coverage.
- The `HxG` provider and whether it includes penalties.
- What counts as "activity" for GitHub's 60-day scheduled-workflow rule.
- GitHub Pages speed from Juba (Phase 6).

## History
- 23 Sep 2026, session 1: read spec, wrote PRD with 26 open questions.
