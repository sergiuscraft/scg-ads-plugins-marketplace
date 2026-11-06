---
name: budget
description: Budget and pricing analysis for scg-ads - ask prices/margins/policies, forecast from keyword data and account history, propose scenarios, pick top keywords/campaigns, set the campaign budget through propose-confirm.
argument-hint: "[optional: price, margin, target CPA, monthly cap]"
---

# Budget & pricing

Called from `setup`, `new-campaign`, `update`. Numbers must come from data or from the human - state which. Never invent conversion rates silently.

## 1. Ask (AskUserQuestion; offer discovered values + "Other")
Price of the offer(s); margin or LTV; target CPA / ROAS or breakeven CPA; monthly cap and currency (read the account's currency); expected conversion rate (or "unknown"); business policies that affect ads: refund/shipping terms, price claims, promo conditions, regulated category, trademark rules. Record them in `account-brief.md` / `campaign-brief.md`.

## 2. Analyse
- Account history (GAQL via `search_search`): spend, clicks, CTR, avg CPC, conversions, CPA, `search_budget_lost_impression_share`, `search_rank_lost_impression_share`, by campaign / ad group / keyword / hour / day-of-week. Use the `google-ads-api-account-diagnostics` skill when diagnosing limits.
- New keywords: volume x CPC from the CSV or `keyword_ideas.py` (low/high top-of-page bid is a range, not the CPC you will pay). Build a table per ad group: est. searches, est. CPC, assumed CTR (use account CTR if present, else state the benchmark assumption), assumed CVR (from the human, account, or "unknown -> show breakeven CVR instead"), est. clicks/conversions/cost.
- Breakeven check: max CPA = price x margin (or LTV share). If CPC / CVR > max CPA, say so plainly.

## 3. Suggest 3 scenarios
Conservative / Balanced / Aggressive: daily budget, projected clicks and conversions, CPA vs breakeven, bidding strategy fit (e.g. Maximize clicks with a CPC cap until ~30 conversions, then Maximize conversions / tCPA). Warn when the budget is too small for the strategy or the keyword set (rule of thumb: daily budget should cover >= 10x the target CPA for conversion-based bidding, say it is a rule of thumb).

## 4. Select top
Rank keywords / ad groups / campaigns by projected efficiency and value. Let the human choose: top N, a cutoff, or a manual list. The rest: leave out, put in a later phase, or create paused. For several campaigns propose a split of the total.

## 5. Apply (propose-confirm)
`budgets_create_campaign_budget` -> `campaigns_create_campaign` with `daily_budget`/`existing_budget_id`; or `campaigns_update_campaign_budget` / `budgets_update_budget` / `budgets_set_campaign_budget`. Before touching a **shared** budget, list the other campaigns using it (GAQL) and warn. Bidding goals via `campaigns_update_campaign`. Remember the API takes account currency, not micros, in the MCP tools - confirm units in the dry-run output.

## 6. Policies
Before ads are created, check each headline/description against the stated business policies and basic ad policy (unverifiable claims, superlatives, prices that don't match the landing page, restricted categories, trademarks, excessive caps/punctuation). Flag, never silently rewrite, risky lines.
