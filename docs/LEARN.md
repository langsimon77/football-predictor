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

Why was Dixon-Coles less sure? Sunderland had conceded little in their first four games, and the shrinkage keeps City's ratings closer to average than their true level. At the time I expected the Bayesian model in Phase 2 to fix this by learning how much to shrink. **Correction (25 Sep 2026):** it did not. The Bayesian model gave City 64%. Chapter 2 shows the real cause: the whole Dixon-Coles family is too timid at the extremes, and a calibration step is the fix.

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

---

## Chapter 2: The Bayesian model

### 2.1 From one answer to a range of answers

The fast model finds the single best set of team ratings. The Bayesian model finds every set of ratings that fits the data, weighted by how well each fits. The answer is not "City's attack is +0.37" but "City's attack is probably between +0.27 and +0.47". Every forecast then carries that uncertainty through: City to beat Sunderland, 64%, with an 80% interval of 57% to 71% [V: fit as of 19 Sep 2026].

### 2.2 What the model says

The goals part is the same Dixon-Coles structure as chapter 1F. Two things change.

**The hierarchy.** Each club's attack and defence are drawn from a league-wide distribution:

$$a_k \sim \text{Normal}(0, \sigma_{\text{att}}), \qquad d_k \sim \text{Normal}(0, \sigma_{\text{def}})$$

The spreads $\sigma_{\text{att}}$ and $\sigma_{\text{def}}$ are learned from the data. A club with little data is pulled towards the league average by exactly as much as the league's spread suggests. The fast model used a fixed pull that we tuned by hand.

**Promoted clubs.** A promoted club gets its own prior from its second-tier season, through a regression over the 24 clubs promoted from 2017/18 to 2020/21 [V: `fp.models.promotion`]:

- first-season attack = −0.25 + 0.20 × second-tier attack (spread of the misses: 0.21)
- first-season defence = +0.19 + 0.28 × second-tier defence (spread of the misses: 0.21)

Promotion alone costs a club about 22% of its scoring rate ($e^{-0.25} = 0.78$). A dominant second-tier season claws some of that back. For 2026/27 this gives, for example, Hull an attack prior of −0.21 and a defence prior of +0.22.

### 2.3 Shots on target: a second reading of the same strength

Goals are rare, about 2.7 a match, so a few lucky or unlucky finishes move them a lot. Shots on target are about three times as common, so they carry more information per match about how good a team really is. The model reads both:

$$\text{shots on target} \sim \text{Poisson}\big(e^{\mu_s + h_s + b_{\text{att}} a_{\text{shooter}} + b_{\text{def}} d_{\text{opponent}}}\big)$$

The same $a$ and $d$ appear in the goals part and the shots part. So a team that keeps forcing saves gets credit for its attack even in a week it does not score. This replaced xG in the backtest (decision D1), because shots on target exist for every season.

On the tuning seasons, adding shots on target improved the home-draw-away RPS from 0.2031 to 0.2014 and the over/under 2.5 log loss from 0.6826 to 0.6797 [V: `reports/backtest_phase2_tune.md`].

### 2.4 How the computer draws the answers, and how we know it worked

The model is fitted with NUTS, a sampler that walks through the space of possible ratings and records where it goes. We run four walkers (chains) from different starting points, 1,000 recorded steps each. Three checks decide whether to trust the result (spec S5.1):

| Check | Plain meaning | Rule |
|---|---|---|
| R-hat | Did the four walkers end up describing the same answer? | Below 1.01 |
| Bulk effective sample size | How many truly independent draws the correlated steps are worth | Above 400 |
| Divergences | Did a walker hit terrain so sharp its steps broke? | Zero |

A fit that fails is never used. The daily run retries once, then falls back to the last posterior that passed and flags the rows as degraded.

**A real problem we met.** The same model can be written two ways. Written one way ("centred"), it sampled well for the EPL. For La Liga it failed: the league's spread of defensive strength is small, and the sampler stalled on it (effective sample size 80, R-hat 1.07). Written the other way ("non-centred"), La Liga sampled perfectly (effective sample size above 2,500). The two forms describe exactly the same model, so the fit tries the first and retries with the second. On the three test seasons, all 209 weekly fits passed [V: GitHub run 36182318598].

### 2.5 Can the model find the truth? Two tests

**Simulation.** We invented two seasons from team strengths we chose, then asked the model to find them. The true values fell inside the model's 90% intervals for 85%, 90%, and 95% of the 40 team effects across three runs. Spec S13 asks for at least 85% [V: `tests/test_bayes_dc.py`].

**Replays of a real season.** We fitted 2025/26, then replayed that season 400 times from the model. If the model is sound, the real season should look like a typical replay [V: `reports/figures/ppc_EPL.png`, `ppc_LaLiga.png`].

- EPL: goals per match, draws, 0-0s, and home wins all sat between the 38th and 64th percentile of the replays. Good.
- La Liga: goals, draws, and home wins looked typical. But the real season had only 3.9% goalless draws, fewer than any replay. The previous nine seasons ranged from 5.5% to 11.3%, so 2025/26 was an unusual season rather than a broken model. Worth watching, because 0-0s drive the under 1.5 and both-teams-to-score markets.

### 2.6 Worked example: Arsenal v Leeds, locked Fri 9 Oct, 04:41 UTC

The first EPL match after the break, fitted on everything known at its lock time [V: fit as of 9 Oct 2026, R-hat 1.004].

| | Forecast | 80% interval |
|---|---|---|
| Arsenal win | 62% | 55% to 69% |
| Draw | 24% | 21% to 28% |
| Leeds win | 14% | 10% to 18% |
| Over 2.5 goals | 44% | 36% to 52% |
| Expected goals | 1.75 v 0.70 | |
| Likeliest scores | 1-0 (14.5%), 2-0 (13.1%), 1-1 (11.1%) | |

Read the interval as: "given the matches so far, the model's own estimate of Arsenal's chance could reasonably be anywhere from 55% to 69%". It is not a range for the result.

### 2.7 What the test seasons say

Walk-forward over 2023/24 to 2025/26, 2,227 matches, scored once with the settings chosen on the tuning seasons [V: `reports/backtest_phase2_test.md`]:

| Model | RPS |
|---|---|
| League base rates | 0.2289 |
| Elo | 0.1982 |
| Fast Dixon-Coles | 0.1974 |
| **Bayesian with shots on target** | **0.1970** |
| Sharp closing market | 0.1912 |

- It beats the base rates clearly.
- It beats Elo on average (by 0.0012), but the 95% interval (−0.0030 to +0.0006) includes zero, so overall the edge is not proven. In the EPL alone the edge is real (−0.0030, interval −0.0055 to −0.0003). In La Liga it is level.
- It is 0.0058 behind the sharp closing market, slightly closer than the fast model.
- On over/under 2.5 it is our best model (log loss 0.6732 against 0.6761 for the fast model and 0.6647 for the market).

### 2.8 The biggest lesson: the model is too timid

Split the matches into five groups by forecast home-win chance, then compare each group's forecast with what happened:

| | Lowest fifth | Highest fifth | Slope |
|---|---|---|---|
| Bayesian | said 23%, happened 18% | said 68%, happened 74% | 1.22 |
| Elo | said 19%, happened 18% | said 73%, happened 74% | 1.00 |

A slope of 1 is perfect. Above 1, the model squeezes its probabilities towards the middle: strong favourites win more often than it believes. That is why Man City got 64% where the market said 73%. Both Dixon-Coles models share it; Elo does not, because Elo's probabilities come from a curve fitted straight to past results.

The cure is a calibration map, a small curve fitted on the tuning seasons that stretches the forecasts back out (spec S5.6, Phase 4). Stretching a timid but otherwise good forecast is exactly what calibration is for.

### 2.9 Tried and dropped

- **Goals only, no shots on target.** Tuning RPS 0.2031 against 0.2014 with shots. Dropped.
- **Random-walk ratings** that drift month by month instead of time-decay weights (spec S5.1 challenger). On 2022/23: RPS 0.2075 against 0.2063, twice the fitting time, and 2 of 35 fits failed diagnostics. Dropped.
