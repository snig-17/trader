# Research: Daily cross-asset trend-following — realistic expectations

*Compiled 2026-06-18 via a multi-source, fact-checked deep-research pass (21 sources
fetched, 90 claims extracted, 25 adversarially verified with a 3-vote panel; 23
confirmed, 2 refuted and excluded). Sources are peer-reviewed finance research and
reputable practitioner white papers; hype/marketing was filtered out.*

## Bottom line
Trend-following (time-series momentum) is one of the most rigorously documented
anomalies in finance — real, pervasive, robust across 130+ years. **But the famous
numbers are a ceiling, not a forecast**, and the things that make them impressive are
exactly what a long-biased 5-ETF retail account cannot fully reproduce. An OOS Sharpe
of ~0.5 for this universe is at the **optimistic** end of realistic. This is a
research project, **not** a passive-income engine.

## 1. Realistic risk-adjusted returns
- **Gross / futures / diversified (the headline):** diversified TSMOM earned gross
  Sharpe **>1.0 (1985–2009), ~2.5× equities** (Moskowitz-Ooi-Pedersen 2012); **~1.8
  gross (1985–2012)** across 58 markets × 1/3/12-mo horizons (AQR *Demystifying
  Managed Futures*). Profitable in **all 67 markets, every decade since 1880** (avg
  per-market Sharpe ~0.4; Hurst-Ooi-Pedersen *Century of Evidence*).
- **The catch:** all gross of fees/slippage/roll, on **58–67 liquid futures** — not 5
  ETFs. Papers explicitly flag net performance as materially lower.
- **What happened live:** SG CTA Trend Index returned **~2.4%/yr, Sharpe 0.03, 22% max
  DD over 2010–2025** (Benhamou et al. 2025, arXiv preprint), a **record −18.6%
  rolling 12-mo drawdown by Apr 2025** (Man Group). AQR: trend made ~7.5%/yr over 30
  years but only **~1.8%/yr in the 2010s**.
- **Implication for this bot:** single-asset trend averages Sharpe **~0.3–0.4**. With
  ~3–4 effective bets (see §3), honest expectation is **~0.3–0.6 net**.

## 2. Signal vs. position sizing
A meaningful share of the premium is **volatility-targeting, not the entry rule.**
Kim-Tse-Wald (2016): TSMOM is *"largely driven by volatility-scaling returns rather
than time-series momentum itself"* (monthly alpha 1.27% vol-scaled vs 0.41%
unscaled). **Caveat:** AQR's OOS test (2011–2019) showed vol-targeting raised returns
mostly by taking *more risk* — risk-adjusted benefit is real but **modest.**
→ This bot's ATR vol-targeting is genuinely load-bearing. Keep it.

## 3. Breadth — the dominant lever (and this bot's biggest gap)
The high portfolio Sharpe is **mechanically a diversification result**: single-asset
trend strategies have **avg pairwise correlation <0.1**. Real programs run **60–70+
futures across 4 asset classes** (29 commodities, 11 equity indices, 15 bonds, 12
currencies). This universe is **5 ETFs, and SPY+EFA are correlated equity sleeves**,
so the **effective number of independent bets is ~3–4, not 5** — *"the single biggest
reason retail expectations should be discounted."* Benefit comes from *uncorrelated*
markets (not just more), and saturates ~40–60. (Caveat: AQR/Man sell these products.)
→ Highest-value change: add **uncorrelated** sleeves (more distinct commodities,
currencies, curve points) — **not** another equity ETF.

## 4. Transaction costs & turnover
Verified: **short-horizon/fast trend underperforms** — standalone short-term trend
Sharpe **0.20**, frequent whipsaws; a 2-week model *"amplifies short-term noise →
frequent turning points and higher turnover/drawdowns."* Slower signals are more
cost-resilient.
**Refuted (0-3, NOT asserted):** that gross Sharpe falls *monotonically* with
rebalance frequency; that costs drive *most* managed-futures alphas below zero; that a
0.49 Sharpe "bounds" expectations. So: direction holds (fast = worse, costs matter)
but **don't over-quantify cost drag.**
→ This bot's fast=20/slow=250 daily signal is on the slow, cost-resilient end. Don't
chase higher frequency.

## 5. "Passive income" reality check
- **Drawdowns are expected, not failure:** a 0.5-Sharpe / 10%-vol strategy has a
  **~80% chance of a 20%+ drawdown over 25 years** (~55% over 10y).
- **The decay is now ~15 years long** — longer than typical historical trend
  drawdowns. AQR/Man call it cyclical (*"fewer large moves… not a decline in
  ability"*), partly vindicated by 2022 — **but they sell trend** (most conflicted
  claim; medium confidence).
- **No credible base rate exists** for retail bot survival — itself telling.

## Implications for this bot
1. **Keep:** slow daily signal, ATR vol-targeting, validation gate, paper-first.
2. **Biggest lever:** breadth via *uncorrelated* instruments (not more equity ETFs).
3. **Reset expectations:** ~0.3–0.6 net Sharpe, mid-single-digit returns, double-digit
   drawdowns, multi-year flat spells. Early P&L is noise.
4. **Don't** chase frequency.
5. **Open question no source could answer:** nobody modeled this exact long-biased
   5-ETF universe net of retail costs — so this bot's own forward-test is the missing
   data point.

## Key sources (verified primary)
- Moskowitz, Ooi, Pedersen (2012), *Time Series Momentum*, JFE —
  https://www.sciencedirect.com/science/article/pii/S0304405X11002613
- Hurst, Ooi, Pedersen (2017), *A Century of Evidence on Trend-Following Investing* —
  https://fairmodel.econ.yale.edu/ec439/hurst.pdf
- AQR, *Demystifying Managed Futures* —
  https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf
- AQR, *You Can't Always Trend When You Want* —
  https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want
- AQR, *Chasing Your Own Tail (Risk) Revisited* —
  https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/AQR-Chasing-Your-Own-Tail-Risk-Revisited.pdf
- Benhamou et al. (2025), arXiv 2507.15876 (preprint, SG CTA 2010–2025) —
  https://arxiv.org/pdf/2507.15876
- Man Group, *Is This Time Different?* — https://www.man.com/insights/is-this-time-different
- Man Group, *Trend Following: Optimal Market Mix* —
  https://www.man.com/insights/trend-following-optimal-market-mix
