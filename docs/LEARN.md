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

---

## Chapter 3a: Calibration, and why we did not switch it on

### 3a.1 What calibration means

A forecaster is calibrated if, of all the times it says 70%, the thing happens about 70% of the time. Phase 2 found our model saying 68% where the home side won 74%: too timid. A calibration map is a small correction fitted to past forecasts and results that stretches the forecasts back into line.

We tried two maps (spec S5.6):

- **Power scaling:** raise each of the three probabilities to a power $\alpha$ and rescale so they sum to 1. With $\alpha > 1$, favourites go up and long shots go down.
- **Dirichlet calibration:** a small linear map on the logarithms of the three probabilities, $q = \text{softmax}(W \log p + b)$, pulled towards "no change" by a penalty. The three-outcome version of beta calibration.

After calibrating home, draw, and away, the scoreline table is stretched region by region to match (PRD item 22), so the heatmap, over/under, and both-teams-to-score all stay consistent.

### 3a.2 What happened

**The fixed map did nothing useful.** We chose the method on the tuning seasons (fit on 2021/22, check on 2022/23), as always. But in those seasons the model was *not* timid: its slope on 2022/23 was 0.97, almost perfect. So the best map was nearly "no change". On the test seasons it improved log loss by 0.0003, with a 95% interval from −0.0027 to +0.0021: noise [V: `reports/calibration_phase3a.md`].

**The timidity is new.** It appeared from 2023/24. That fits the Elo result: Elo refits its probability curve at every lock on recent results, so it adapts when the leagues become more lopsided. A map fitted once cannot follow a moving target.

**A monthly map follows it.** Spec S5.6 already describes refitting the map every month on recent predictions. We tested that, each month using only predictions whose results were known before the month began:

| | Slope | RPS | Log loss |
|---|---|---|---|
| Raw | 1.24 | 0.1967 | 0.9745 |
| Monthly map | 1.09 | 0.1963 | 0.9737 |
| Sharp market, for reference | 1.08 | | |

The shape is fixed: the forecasts are now as honest at the extremes as the market's. But the accuracy gain is small and not clear (log loss interval −0.0035 to +0.0017), and both-teams-to-score gets slightly worse (+0.0009, a real but tiny cost of stretching the table).

### 3a.3 Why we did not switch it on

Our rule: apply a correction only if it clearly improves out-of-sample log loss, meaning the whole 95% interval of the change sits below zero. Neither map passes. A small, uncertain gain is not worth changing live forecasts for.

Two further points. First, the calibration question returns in Phase 4, where the Bayesian model is blended with Elo; Elo's adaptive, well-calibrated probabilities may fix the timidity as part of the blend. Second, nothing is lost by waiting. Calibration is a fixed transformation of the raw locked probabilities, fitted only on the past, so we can compute at any time what a calibrated forecast would have said.

### 3a.4 The general lesson

Proper scoring rules (RPS, log loss) are dominated by the randomness of football itself. A correction that moves a 68% forecast to 74% changes the score of each such match only a little, so even a real improvement in honesty can be invisible in the average score over three seasons. That is why we track the slope separately, and why a clear-improvement rule protects us from fooling ourselves in both directions.

---

## Chapter 3b: Corners and yellow cards

### 3b.1 Counting things: Poisson and negative binomial

Corners and cards are counts: 0, 1, 2, and so on. The simplest model for a count is the Poisson distribution, where the spread (variance) equals the average. Real counts often spread more than that. The negative binomial adds one number, $\alpha$, to allow it:

$$\text{variance} = \text{mean} + \frac{\text{mean}^2}{\alpha}$$

A large $\alpha$ means nearly Poisson; a small one means much wider. The spec asks us to test both and keep the negative binomial unless the data show no extra spread.

### 3b.2 The corners surprise: the two sides pull against each other

Our first corners model predicted each team's corners separately, then added them up as if they were independent. Each team's corners do spread more than Poisson ($\alpha \approx 13$). But the total came out worse than simply using the league average [V: `reports/backtest_phase3b_corners_tune.md`].

The reason: home and away corners are **negatively correlated**, −0.35 in the EPL and −0.27 in La Liga over 2021/22 and 2022/23 [V: computed from the match data]. When one side leads, it sits back, and the side chasing the game wins corners. Adding two independent counts makes the total too spread out, because independence ignores this pull.

The fix was to model the match total directly. Each club gets a "corner tendency" effect (how many corners its matches produce), plus how lopsided the match looks (Elo gap at lock) and both sides' recent shot volume. Once modelled this way, the total is close to Poisson ($\alpha \approx 51$), and the Poisson version scored best. Each side's expected corners come from splitting the total by the clubs' recent corner shares.

Yellow cards behave the other way: home and away yellows correlate positively (+0.18 EPL, +0.27 La Liga), because tense matches book both sides. The cards model works on the total from the start.

### 3b.3 The cards model

$$\log(\text{expected yellows}) = \text{league level} + \text{discipline}_{\text{home}} + \text{discipline}_{\text{away}} + \text{referee} + \text{match terms}$$

- **Club discipline:** pooled across the league, like attack and defence in chapter 2.
- **Referee:** EPL only (decision D3), also pooled. La Liga referees are appointed the day before kickoff, after our lock, so the model never uses them. For EPL matches where the appointment is not known at lock (Friday, Saturday, Tuesday, Wednesday kickoffs), the forecast averages over the referee spread, which makes it slightly wider.
- **Match terms:** how close the match looks, recent fouls, derby, and late-season importance.

What the data say [V: fit as of 9 Oct 2026]: derbies bring about 19% more yellows ($e^{0.177}$). Closeness and fouls matter a little. The spread between EPL referees is only about 3.6% once clubs and match type are accounted for, far less than football folklore suggests. So skipping referee questions (D3) costs little.

### 3b.4 No peeking: features at lock time

"How lopsided is this match?" uses the Elo gap as it stood at the lock, not a rating fitted later (PRD item 7). Rolling averages of shots, corners, fouls, and yellows use only results known at the lock. A test plants a fake 9-0 thrashing on the Saturday afternoon and checks that Man City's features for their Sunday match do not move. The live path and the backtest path give identical features for the same match.

### 3b.5 Worked example: Arsenal v Leeds, locked Fri 9 Oct, 04:41 UTC

| | Forecast |
|---|---|
| Expected corners | Arsenal 5.8, Leeds 4.2 |
| Over 9.5 corners | 54% |
| Expected yellow cards | 3.4 |
| Over 4.5 yellows | 26% |
| Referee | Not known at lock (Saturday kickoff), so averaged |

Inputs at lock: Elo gap +231 for Arsenal; Arsenal's matches average 5.1 corners for and 3.5 against; Leeds 4.4 for and 5.8 against [V: `features_for_fixtures` as of 9 Oct].

### 3b.6 Results on the test seasons (2023/24 to 2025/26, 2,280 matches, scored once)

| Model | Log score against league average | Against team average |
|---|---|---|
| Yellow cards (negative binomial) | −0.019 (interval −0.028 to −0.010) | −0.017 (interval −0.027 to −0.007) |
| Corners (total, Poisson) | −0.009 (interval −0.015 to −0.002) | −0.001 (not significant) |

Both beat the league-average baseline, as spec S11 requires. Cards also clearly beat a simple team average. Corners do not: once you know the two clubs' recent corner rates, our model adds little. That is an honest finding about how predictable corners are.

The calibration plots (`reports/figures/calibration_corners_total.png` and `calibration_cards.png`) show forecasts close to what happened on every line: when the model says 60% for over 9.5 corners, about 60% of those matches go over.

## Chapter 4: Challengers, blending, and confidence tiers

### 4.1 Four challengers

So far every forecast came from models built on football logic: Elo and Dixon-Coles. Phase 4 adds four general-purpose models that learn the link between numbers and results straight from past matches:

- **Ordered logit.** One number, "how much stronger is the home side", turned into home, draw, away by a fitted S-curve. Home win, draw, and away win are treated as steps on one ladder.
- **Multinomial logistic regression.** Gives each of the three results its own weighted sum of the inputs. Draws are free to behave differently from wins.
- **Random Forest.** 500 decision trees, each asking yes-or-no questions ("is the Elo gap above 120?"), then averaging their answers.
- **XGBoost.** Trees built one after another, each fixing the previous ones' mistakes.

They all read the same 28 inputs, each as it stood at the lock: the fast Dixon-Coles forecast, the Elo gap, rolling shots, corners, fouls and yellows, rest days, league games in the last 14 days, games played this season, promoted flags, derby, and late-season importance. No odds and no team news (spec S5.5, PRD item 6).

### 4.2 Choosing settings without peeking

Each model has dials, like the depth of the trees. We set them by testing on 2017/18 to 2020/21 only, always training on earlier matches and scoring later ones. The tuning and test seasons played no part. Then we walked forward over 2021/22 to 2025/26: at the first lock of each month, refit on results known by then, and forecast that month's matches [V: `data/backtests/challengers_walkforward_2021_2025_cv.parquet`].

Simple settings won: the multinomial with the strongest shrinkage, XGBoost with the shallowest trees (two questions deep) and the fewest of them, Random Forest with large leaves. A sign that there is little extra pattern to find.

### 4.3 Blending: the stacked ensemble

A stack is a weighted average of the models' probabilities:

$$p_{\text{stack}} = w_1\, p_{\text{Elo}} + w_2\, p_{\text{fast DC}} + \dots + w_7\, p_{\text{XGBoost}}$$

The weights are fitted to give the lowest log loss on the tuning seasons, with every model kept at 5% or more so it can earn its way back (spec S5.6). The fit gave XGBoost 41%, the multinomial 34%, and 5% to each of the other five [V: `data/stacking/stack_1x2.json`].

### 4.4 What the test seasons say (2023/24 to 2025/26, 2,227 matches with odds, scored once)

| Forecast | Log loss |
|---|---|
| League base rates | 1.0702 |
| Elo | 0.9786 |
| XGBoost | 0.9775 |
| Fast Dixon-Coles | 0.9770 |
| Bayesian (live primary) | 0.9759 |
| Random Forest | 0.9752 |
| Ordered logit | 0.9746 |
| Multinomial | 0.9739 |
| **Stack** | **0.9738** |
| Market at the Friday or Tuesday snapshot | 0.9601 |
| Sharp closing market | 0.9571 |

[V: `reports/backtest_phase4.md`]

- The stack beats Elo clearly (−0.0049, interval −0.0096 to −0.0005).
- It beats the Bayesian model on average (−0.0022), but the interval (−0.0064 to +0.0019) includes zero. Not proven.
- Apart from base rates, every model sits within 0.005 of the others. The market is 0.014 ahead even at the Friday or Tuesday snapshot, taken at about the same time as our lock [E: football-data.co.uk notes, PRD item 9].

**Why the blend barely helps.** Blending pays when models make different mistakes. These seven all read the same thing, team strength from past results, so they make nearly the same mistakes. The weights show it: fitted on 2021/22 alone, Random Forest gets 48%; on 2022/23 alone, XGBoost gets 59%, and Random Forest drops to the 5% floor. When the weights swing like that, the data cannot tell the models apart. Equal weights on all seven do just as well on the tuning seasons.

**The recommendation** follows the rule we used for calibration: change only when the whole interval favours the change. Keep the Bayesian model as the published forecast. Log the stack and the four challengers every day as shadow models, like Elo today, and test again at the end of 2026/27 with a full live season added.

One thing the stack does better: it is less timid (calibration slope 1.10 against 1.23 for the Bayesian model), because the challengers learn their probabilities straight from results. No calibration map improved it further [V: section 4 of the report].

### 4.5 Confidence tiers: a safety margin that hides nothing

Every match still gets a forecast. The tier is a label: how far to trust it.

**Why it helps.** A 70% forecast that is honest still loses 3 times in 10. The tier cannot change that. What it can do is sort the forecasts so that the High group holds the matches where the model is surest and nothing is known to be wrong with the inputs. You then know which forecasts to lean on. Nothing is hidden: Medium and Low are published beside High, with their own records.

**Why small and good beats large and poor.** A High tier that covers 20% of matches and wins 74% of the time tells you something. A High tier that covers 60% and wins 55% is just the average forecast with a badge. The margin costs coverage; the dashboard will show both the record and the coverage so you can see the trade (spec S7).

**The rule.**

1. Favoured probability sets the starting tier. For home, draw, away that is the top probability. For an over/under line it is the chance of the likelier side. Cut points come from the tuning seasons: the top quarter starts High, the bottom third starts Low [A: the quarter and third are design choices].
2. Uncertainty drops one tier: an 80% interval wider than 90% of tuning forecasts, or the stack and the Bayesian model disagreeing more than 90% of tuning forecasts.
3. Data flags: one caps the tier at Medium; two force Low. Flags: unknown referee (cards), manager change in the last 30 days, unanswered key question, source failure. A promoted club with fewer than 6 league games is shown in the flags column but does not count (see below).

**Results for the Bayesian forecast, test seasons, under the rule now live** [V: section 6 of the report]:

| Tier | Share of matches | Promised (mean top probability) | Favourite won | 95% interval |
|---|---|---|---|---|
| High | 20% | 68% | 74% | 70% to 78% |
| Medium | 41% | 53% | 53% | 50% to 56% |
| Low | 39% | 42% | 43% | 39% to 46% |

The three tiers are clearly apart: no interval overlaps the next. High wins more often than promised, the known timidity from chapter 2.

**The honest test (PRD item 13).** Separation by top probability is arithmetic: any sensible model shows it. The real question is whether the other inputs pick out forecasts that do worse than they promise. We measure "excess surprise": the log loss a forecast earned, minus the log loss it expected of itself. Zero means honest; above zero means worse than promised.

- **Wide interval, disagreement:** no clear effect for the Bayesian forecast. For the stack, big disagreement with the Bayesian model does flag worse forecasts on the test seasons (+0.083, interval +0.012 to +0.154).
- **Promoted club, early season:** the opposite of its purpose. Those forecasts did *better* than promised (−0.084, interval −0.154 to −0.010). The promoted-team prior from chapter 2 appears to handle them well. So it no longer caps a tier (your decision, 26 Sep 2026); it stays visible as a note.
- **Unknown EPL referee:** cards over 3.5 forecasts without a known referee do worse than promised (+0.030, interval +0.009 to +0.049). The flag earns its place.
- **Over/under lines:** forecasts sit between about 50% and 75%, so the tiers barely separate. Clearly separated on only 4 of 11 lines (over 1.5 and over 3.5 goals, over 8.5 corners, over 5.5 yellows). Read an over/under High as "a bit surer", not "safe".

### 4.6 Worked example: Arsenal v Leeds, locked Fri 9 Oct, 04:41 UTC

Every challenger was refitted on the 6,959 matches with results known at lock and fed this match's lock-time inputs: Elo gap +231 for Arsenal, 14 days' rest each, 5 league games played each, neither promoted [V: computed 26 Sep 2026 from results up to 20 Sep; Bayesian numbers from section 2.6]. XGBoost here ran on the Mac; GitHub's Linux runner, which makes the live forecasts, gave values up to 1.6 points different in a replay test, so the live stack can differ by about half a point.

| Model | Arsenal | Draw | Leeds | Weight in stack |
|---|---|---|---|---|
| Elo | 69.8% | 18.6% | 11.6% | 5% |
| Fast Dixon-Coles | 60.0% | 25.1% | 14.8% | 5% |
| Bayesian | 62% | 24% | 14% | 5% |
| Ordered logit | 62.9% | 22.1% | 15.0% | 5% |
| Multinomial | 61.2% | 24.0% | 14.7% | 34% |
| Random Forest | 66.3% | 21.8% | 11.9% | 5% |
| XGBoost | 64.0% | 23.8% | 12.2% | 41% |
| **Stack** | **63.1%** | **23.5%** | **13.4%** | |

Tiers for the published Bayesian forecast:

| Market | Favoured side | Tier | Why |
|---|---|---|---|
| 1X2 | Arsenal 62% | High | 62% is above the 58% cut; interval 14 points wide (limit 16); stack and Bayesian differ by 1 point (limit 7); no flags. |
| Over/under 2.5 goals | Under, 56% | Medium | Between the 55% and 61% cuts. Its interval (36% to 52%) sits right on the 16-point limit, so the live run's unrounded numbers decide whether it drops to Low. |
| Over/under 9.5 corners | Over, 54% | Low | Below the 56% cut. |
| Over/under 4.5 yellows | Under, 74% | Medium | Between the 60% and 76% cuts; the referee is unknown at lock (Saturday), which would cap it at Medium anyway. |

### 4.7 What you decided, and what runs now

You approved both recommendations on 26 Sep 2026:

1. The Bayesian model stays the published forecast. Every daily run also locks the four challengers and the stack as **shadow** rows (`ordered_logit_v1`, `multinomial_v1`, `random_forest_v1`, `xgboost_v1`, `stack_v1`). They are scored like every other row. At the end of 2026/27 we re-test the stack against the Bayesian model with the same strict rule.
2. Every Bayesian row carries a tier for each market: home, draw, away; over 1.5, 2.5, 3.5 goals; both teams to score; four corners lines; three yellows lines. The report shows the home, draw, away tier and the over 2.5 tier.

A check before switching on: for 40 recent matches, the daily run builds exactly the same 28 inputs as the backtest did [V: 26 Sep 2026]. So the live challengers see nothing the backtest did not.

## Chapter 5: Team news and the Question Queue

### 5.1 Why you, not a scraper

The spec wanted team news scraped automatically. The Phase 0 audit found no source we may use: the Fantasy Premier League terms forbid automated collection, Understat's robots.txt blocks everyone, laliga.com forbids reproduction, and API-Football's free plan does not cover 2026/27 [V: `docs/DATA_SOURCES.md`, decision D2]. So news comes from you, through the Question Queue. You approved this fallback in Phase 0.

### 5.2 How a question reaches you

Every daily run (06:41 Juba time) opens one GitHub Issue, "Questions for Lang: <date>", which GitHub emails to you. It asks about the matches that will lock at the *next* run, so you have about a day to tick. For each club you tick how many regular starters will miss the match (0, 1, 2, 3 or more), and whether the main goal threat is one of them. Each club has a search link for its team news.

- At most 10 matches a day. When there are more, the ones where an answer would move the forecast most come first.
- Nothing ticked for a club means "don't know". Two contradictory ticks also mean "don't know".
- Only ticks in Issues the bot itself opened, and edited only by you or the bot, are read. Anyone can open an Issue in a public repository, but only you can edit the bot's Issues.
- When all of an Issue's matches have locked, the run closes it and saves the answers it used in `data/manual/answers.yaml`.

### 5.3 What an answer does

Goals depend on two scoring rates: how many the home side should score, and how many the away side should. An answer scales them [A: sizes are Assumptions, with no player data to fit them]:

| For each ... | Own scoring rate | Opponent's scoring rate |
|---|---|---|
| Regular starter out | −2.5% | +2.5% |
| Main goal threat out (extra) | −6% | |

No rate moves more than 12% either way (spec S6.3). Every market that comes from the scoreline table (home, draw, away, over/under, both teams score) moves with it. Corners and cards do not.

**Example ticks, not real news** [V: `reports/phase5_dry_run.md`]: Chelsea with 3 or more starters out including the main goal threat would lose 7.5% + 6% = 13.5% of their scoring rate; the cap stops it at 12%. Bournemouth's rate rises 7.5%. Chelsea's win chance falls from 43% to 36%.

### 5.4 Keeping score of the news itself

Whenever news moves a forecast, the run also locks the same forecast without news, as a shadow row (`dc_bayes_v1_nonews`). After 10 gameweeks we compare the two on the same matches (spec S6.5). If the news version is not better, I will propose shrinking or dropping the effects. That test, not my guess, decides the sizes.

### 5.5 Unanswered questions and manager changes lower the tier

- A club left unticked, or "don't know", is a data flag: the match locks without that club's news and its tiers are capped at Medium. The ledger lists the unanswered questions.
- Each run also reads the manager of every club playing in the next 72 hours from Wikipedia. A new name opens a "Manager check" question. Until you answer "no", the club carries a manager-change flag for 30 days, which also caps its tiers at Medium.

The spec gives two versions of the unanswered rule: "the tier drops one level" (S6) and "a data flag" (S7). We use the flag, the same as every other data problem (your decision, 26 Sep 2026). With one flag, High becomes Medium and Medium stays Medium.

You switched the queue on and accepted the effect sizes on 26 Sep 2026. A self-test on GitHub opened a test Issue (#2), ticked it as the bot, read the ticks back through the trust rule, and closed it [V: workflow runs 36225539559 and 36225611381].
