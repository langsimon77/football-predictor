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

**Worked example.** The daily run at 04:41 UTC locks every match that kicks off 24 to 48 hours later. (The spec said 05:00. We run off the hour because GitHub delays jobs scheduled on the hour.) City v Sunderland kicked off at 13:00 UTC on Sunday 20 Sep. The run at 04:41 UTC on Saturday 19 Sep came about 32 hours before kickoff, so that run locked it. Its as_of time is **Sat 19 Sep, 04:41 UTC**.

Now take Brighton v Arsenal, played at 14:00 UTC on Saturday 19 Sep. It finished about 21 hours before City kicked off. Its result still cannot touch the City prediction, because it became known around 17:00 UTC, about 12 hours after the lock. A careless pipeline that uses "every match before kickoff" would include it. Ours stamps every row with the time it became known and refuses anything after as_of. A unit test in Phase 1 fails the build if any feature breaks this.

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

---

## Chapter 1: The pipeline, and how it protects itself

### 1.1 Four steps, every day

1. **Download.** Fetch football-data.co.uk and openfootball files. Wait at least 3 seconds between requests to a site. Keep a dated copy of everything in `data/raw/`. Never edit those copies.
2. **Build.** Turn the raw files into four clean tables: `matches` (7,719 top-flight matches since 2016/17), `fixtures` (all 760 matches this season, played or not), `second_tier` (for promoted teams), and `referee_appointments`.
3. **Validate.** Check every table against a written list of rules. Any broken rule stops the run.
4. **Load.** Save the tables as Parquet files and point a DuckDB database at them, so any question about the data is one SQL query.

`make data` runs all four. `make rebuild` rebuilds everything from the raw copies without downloading.

### 1.2 Validation earns its keep

The rules come from spec S4: no duplicate matches, no negative counts, every time in UTC, every team mapped. We added more: 380 matches in every finished season, 20 teams, nobody plays themselves, odds above 1.

Building it surfaced two real problems: one in the data, one in our own rule.

- **An impossible price.** Barcelona v Girona, 18 Oct 2025, had Pinnacle closing over/under odds of 0.0 in the source file. Decimal odds of 0 would mean a certain loss on a bet, which no bookmaker offers. It was a placeholder for "missing". The builder now treats any odds of 1.0 or less as missing and logs a warning.
- **A silent time-zone guess.** An early version of the rule converted a time with no time zone into UTC without complaint. That would hide the worst kind of bug: a UK or Spanish local time quietly treated as UTC, shifting every lock by one or two hours. A test that feeds in naive times caught it. Now any time without a time zone fails.

Each rule has a test that feeds in bad data and checks that the rule rejects it. A rule that has never been seen to fail is a rule you cannot trust.

### 1.3 The lock clock

The daily run happens at 04:41 UTC. A match is locked by the last run that is at least 24 hours before kickoff:

$$\text{lock} = \big\lfloor \text{kickoff} - 24\text{h} - 04{:}41 \big\rfloor_{\text{day}} + 04{:}41$$

Subtract 24 hours. Step back to the most recent 04:41. The result always lands 24 to 48 hours before kickoff. A test checks this for kickoffs at awkward times, such as one minute after the run.

**Worked example: the first two matches after the break** [V: openfootball calendar].

| Match | Kickoff (UTC) | Kickoff minus 24 h | Lock (UTC) | Hours before kickoff |
|---|---|---|---|---|
| Málaga v Espanyol | Fri 9 Oct, 19:00 | Thu 8 Oct, 19:00 | Thu 8 Oct, 04:41 | 38.3 |
| Arsenal v Leeds | Sat 10 Oct, 11:30 | Fri 9 Oct, 11:30 | Fri 9 Oct, 04:41 | 30.8 |

So the pipeline must be running by the Thursday 8 Oct run. In the backtest, the same formula sets each past match's as_of time. That way the backtest sees exactly what the live system would have seen.

**When is a result known?** We treat every result as known 3 hours after kickoff. A match lasts about 2 hours with stoppages. Taking 3 is deliberately cautious: counting a result as known too late costs a little information, while counting it too early is leakage.

### 1.4 A ledger that cannot be quietly edited

Each locked prediction is a row in `ledger/predictions.parquet`. Each row stores a fingerprint: the SHA-256 hash of its own contents plus the previous row's fingerprint.

A hash is a 64-character code computed from data. Change one digit of the input and the code changes completely. Because each row folds in the previous row's code, the rows form a chain. Edit row 1 and its code changes, which breaks row 2's link, which breaks row 3's, and so on to the end. Anyone can recompute the chain and see where it broke.

Two more guards sit on top. The code refuses to lock the same match twice for the same model, unless the kickoff moved more than 7 days. And CI compares the ledger with the previous commit and fails if any old row changed or vanished. Git records when each commit was pushed, which proves each prediction existed before its kickoff.

Tests prove all three: editing a probability, deleting a row, and double-locking a match each get caught.

### 1.5 Is the data fresh?

football-data.co.uk has the statistics we need, but it updates a few times a week. openfootball updates every day but has only scores. The freshness check compares the two. A match that finished more than 72 hours ago and is still missing from football-data.co.uk marks that league as stale. The run then takes the score from openfootball and flags itself. The check also lists any match within 72 hours that still has no confirmed kickoff time, because such a match cannot be locked on schedule.

---

## Chapter 1F: Two fast models, Elo and Dixon-Coles

### 1F.1 Elo: one number per club

Every club carries a rating. Before a match the model computes how often the home side "should" win:

$$E = \frac{1}{1 + 10^{-(R_{\text{home}} + H - R_{\text{away}})/400}}$$

$H = 60$ points is the home edge. After the match, the home side's rating moves by $K \cdot G \cdot (S - E)$ and the away side's by the same amount the other way. $S$ is 1 for a home win, 0.5 for a draw, 0 for a loss. $G$ grows with the winning margin: 1 for one goal, 1.5 for two, more for bigger wins. $K = 10$ sets how fast ratings react. Between seasons each rating moves a quarter of the way back to 1500, and promoted clubs start at the average of the clubs that went down.

A rating gap is not yet a probability of home, draw, or away. An ordered logistic curve, refitted at each lock, turns the gap into those three numbers.

**Intuition.** Elo only asks "who won, and by how much, against whom". It forgets nothing and learns slowly. That makes it a strong, simple benchmark.

### 1F.2 Dixon-Coles: goals, not just results

Each club gets two numbers: attack (how much it scores above average) and defence (how much it concedes above average; lower is better). Goals follow a Poisson distribution:

$$\lambda_{\text{home}} = e^{\mu + h + a_{\text{home}} + d_{\text{away}}}, \qquad \lambda_{\text{away}} = e^{\mu + a_{\text{away}} + d_{\text{home}}}$$

$\mu$ is the league's base scoring rate and $h$ the home edge. Poisson treats goals as independent chances, which slightly misjudges low scores: real matches end 0-0 and 1-1 a little more often than that. Dixon and Coles added one parameter, $\rho$, that corrects only the four scores 0-0, 1-0, 0-1, and 1-1.

From the two rates we build a table of every scoreline from 0-0 to 10-10. Everything else is a sum over that table: home win (all cells where home scores more), over 2.5 (all cells with three or more goals), both teams to score, and the likeliest scores.

Two refinements make it work on real data:

- **Time decay.** A match played $t$ days ago counts with weight $e^{-0.002 t}$, so a result loses half its weight in 347 days. Tuned on 2021/22 and 2022/23.
- **Shrinkage.** A penalty pulls every club towards a prior, so a club with few matches is not rated on a lucky week. Most clubs are pulled to average. Promoted clubs are pulled to the level promoted clubs really had in their first season: about 19% fewer goals scored and 14% more conceded than average [V: fitted on 24 promoted clubs, 2017/18 to 2020/21].

### 1F.3 Worked example: Man City v Sunderland, locked Sat 19 Sep, 04:41 UTC

This comes from the replay of the daily run over the rounds before the break [V: replay ledger].

| | Elo | Dixon-Coles | Market (Betfair close) |
|---|---|---|---|
| Inputs | City 1631, Sunderland 1440, gap 252 with home edge | City attack +0.35, defence −0.36; Sunderland attack −0.17, defence −0.12 | |
| Home, draw, away | 73%, 17%, 10% | 63%, 24%, 13% | 73%, 17%, 10% |
| Expected goals | none | 1.90 v 0.76 | |
| Likeliest scores | none | 2-0 (12.7%), 1-0 (12.2%), 1-1 (11.2%) | |

City won 5-3. The surprise for a home win was $-\ln 0.73 = 0.32$ for Elo and $-\ln 0.63 = 0.46$ for Dixon-Coles.

Why was Dixon-Coles less sure? Sunderland had conceded little in their first four games, and the shrinkage keeps City's ratings closer to average than their true level. That is the fast model's known weakness: it shrinks every club by the same fixed amount. The Bayesian model in Phase 2 learns from the data how much to shrink, club by club.

### 1F.4 What the backtest says

Walk-forward over 2023/24 to 2025/26, 2,227 matches, each predicted at the run that would have locked it [V: `reports/backtest_1f.md`]:

| Model | RPS (lower is better) |
|---|---|
| League base rates | 0.229 |
| Elo | 0.198 |
| Dixon-Coles | 0.197 |
| Market, Friday snapshot | 0.192 |
| Sharp closing market | 0.191 |

Dixon-Coles beats the base rates clearly. It ties Elo on home, draw, away: the difference is −0.0008 with a 95% interval from −0.0024 to +0.0008, which includes zero. Its extra value is the goals markets, which Elo cannot price. Both trail the closing market by about 0.006, close to the 0.005 we called a strong free-data result. Top-pick accuracy is 53%, well under the 60% leakage alarm.

**An honest note on tuning.** The first tuning grid put the best settings on its edge, which means the true best could lie outside it. The grid was widened and the choice made again from the tuning seasons only. The test seasons were therefore scored twice, and the report says so. The result barely moved.
