"""Team news and the Question Queue (spec S6, Phase 5).

No compliant automated team-news source exists (decision D2), so news comes from
Lang through a daily GitHub Issue with checkboxes (PRD Q3):

- queue: which matches to ask about, the Issue text, and reading ticks back.
- impact: turning answers into capped changes to the scoring rates.
- managers: spotting a manager change on Wikipedia, for Lang to confirm.
- github: the few GitHub calls, with the rule that only the bot's own Issues,
  edited only by the bot or the repository owner, are trusted.
"""
