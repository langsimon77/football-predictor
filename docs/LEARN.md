# Learning Notes

One chapter per phase. Each chapter shows the maths once, then the intuition, then a worked example on a real 2026/27 match.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

---

## Chapter 0: The data, and the rule that keeps the model honest

### 0.1 What one match looks like

Every match is one row in a football-data.co.uk CSV. Here is Manchester City v Sunderland, Sunday 20 Sep 2026 [V: `E0_2627.csv`].

| Column | Value | Meaning |
|---|---|---|
| `Date`, `Time` | 20/09/2026, 14:00 | Kickoff in UK local time |
| `FTHG`, `FTAG` | 5, 3 | Full-time goals, home and away |
| `HxG`, `AxG` | 2.82, 3.57 | Expected goals, home and away |
| `HST`, `AST` | 6, 9 | Shots on target |
| `HC`, `AC` | 6, 5 | Corners |
| `HY`, `AY` | 0, 1 | Yellow cards |
| `Referee` | R Jones | EPL only |
| `BFECH`, `BFECD`, `BFECA` | 1.36, 5.70, 10.00 | Betfair Exchange closing odds: home, draw, away |

**Time zones.** The file stores UK time. In September the UK runs on UTC+1, so 14:00 UK is 13:00 UTC. Juba runs on UTC+2 all year, so Lang saw this kickoff at 15:00. The pipeline stores every time in UTC and converts only for display.

**What xG says here.** City scored 5 from 2.82 expected goals. Sunderland created more (3.57) but scored 3. xG adds up the probability that each shot becomes a goal, judged by where and how it was taken. Goals are noisy: a team can finish far above or below its chances in one match. That is why xG is useful as a second, less noisy signal of team strength. We only have xG for 2026/27, so the backtest uses shots on target in its place (DATA_SOURCES.md, D1).

### 0.2 From odds to probabilities

Decimal odds of 1.36 mean a stake of 1 returns 1.36. The implied probability is the reciprocal.

$$p_{\text{implied}} = \frac{1}{\text{odds}}$$

For this match: 1/1.36 + 1/5.70 + 1/10.00 = 0.735 + 0.175 + 0.100 = **1.011**.

The three outcomes cannot sum to more than 1, so the extra 0.011 is the bookmaker's margin, 1.1% here. Dividing each by 1.011 gives home 72.7%, draw 17.4%, away 9.9%. The market-average closing odds for the same match summed to 1.057, a 5.7% margin. Exchanges like Betfair charge commission instead of building a margin into the prices, which is why their margin is small.

Simple division spreads the margin evenly. Bookmakers tend to load more margin onto long shots, so Phase 4 uses the power method instead. It raises each implied probability to a common power $k$ chosen so the results sum to 1. Chapter 4 covers it.

**Intuition.** The closing price is the market's final, collective estimate. It includes the confirmed lineups. Our model locks 24 to 48 hours earlier, so we also compare against the Friday snapshot, which knew roughly what we know.

### 0.3 The as_of rule

**The rule.** Every number the model uses for a match must have been knowable at that match's lock time.

Break it and the backtest looks brilliant, then the live season disappoints. The model was quietly reading the future. This is called leakage.

**Worked example.** The daily run at 05:00 UTC locks every match that kicks off 24 to 48 hours later. City v Sunderland kicked off at 13:00 UTC on Sunday 20 Sep. The run at 05:00 UTC on Saturday 19 Sep was 32 hours before kickoff, so that run locked it. Its as_of time is **Sat 19 Sep, 05:00 UTC**.

Now take Brighton v Arsenal, played at 14:00 UTC on Saturday 19 Sep. It finished about 21 hours before City kicked off. Its result still cannot touch the City prediction, because it came in 9 hours after the lock. A careless pipeline that uses "every match before kickoff" would include it. Ours stamps every row with the time it became known and refuses anything after as_of. A unit test in Phase 1 fails the build if any feature breaks this.

The same rule decides which sources are useful at all. La Liga referee appointments go up the day before each match [V: RFEF], which is always after our lock. So the model can never use them for a La Liga match, however good the data is.

### 0.4 Scoring a prediction by its surprise

After the match, we score how surprised the forecast was: the negative log of the probability it gave the actual result.

$$\text{surprise} = -\ln p(\text{actual outcome})$$

The market gave City a 72.7% chance. City won, so the surprise was $-\ln 0.727 = 0.32$. Had Sunderland won, the surprise would have been $-\ln 0.099 = 2.31$. A forecaster that says 99% and loses takes a huge penalty. That keeps everyone honest about uncertainty. This is the log loss, one of our scoring rules. The miss audit in S5.6 ranks matches by this number.

### 0.5 One club, one ID

Sources disagree on names: "Man United", "Manchester United", "Manchester United FC". The pipeline never joins on a name. It maps every spelling to one ID (`man_united`) and joins on that. A test proves both sources name the same 20 clubs in every season since 2016/17. It also proves the 119 matches played so far this season have identical dates and scores in both. If a new spelling appears, the mapping raises an error rather than guessing.

### 0.6 Baselines worth remembering

Averages over 2023/24 to 2025/26, 1,140 matches per league [V: `make audit` data]:

| | EPL | La Liga |
|---|---|---|
| Home win, draw, away win | 43.2%, 24.5%, 32.4% | 45.8%, 26.1%, 28.2% |
| Goals a match | 2.99 | 2.65 |
| Corners a match | 10.4 | 9.5 |
| Yellow cards a match | 3.99 | 4.55 |

Any model must beat these base rates before it earns a place. Note the yellow-card gap. Part of it is how cards are counted: EPL files leave out the first yellow of a two-yellow red, La Liga files include it [V: notes.txt].
