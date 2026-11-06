# Keyword sources (do it yourself, bring a CSV back)

| Source | Link | Good for | Export |
|---|---|---|---|
| Google Keyword Planner | https://ads.google.com/aw/keywordplanner | volumes, top-of-page bids, ideas from a URL | Download plan ideas (CSV) |
| Ahrefs Keywords Explorer | https://ahrefs.com/keywords-explorer | volume, difficulty, clicks, CPC, questions | Export CSV |
| Semrush Keyword Magic Tool | https://www.semrush.com/analytics/keywordmagic/ | broad ideation, intent labels, CPC | Export CSV |
| Ubersuggest | https://neilpatel.com/ubersuggest/ | cheap alternative for volume/CPC | Export CSV |
| Google Trends | https://trends.google.com/trends/ | seasonality, rising queries, comparisons | CSV |
| Google Autocomplete / People also ask / Related searches | google.com | real phrasing, long-tail | copy by hand |
| AnswerThePublic | https://answerthepublic.com | questions and prepositions | CSV |
| Ads Transparency Center | https://adstransparency.google.com | competitor ads, messages, themes | screenshots / notes |
| Your account's search terms | via Claude (`search_search`) | proven, real queries | automatic |
| Keyword Planner via API | `scripts/keyword_ideas.py` | same as the UI, scripted | needs developer-token Basic access |

## CSV to bring back
Anything with a header row works. Best columns: `keyword`, `volume` (avg monthly searches), `cpc` (or low/high bid), `competition`. Delimiters `, ; tab` and UTF-8 BOM are fine. One keyword per row. Claude will ask you to confirm the column mapping.

## Tips
- Start from 10-20 seeds: services, problems, locations, brands you can legally use.
- Export wide, clean later; Claude drops junk and shows what it dropped.
- Keep competitors/brand terms in a separate file - they usually deserve their own campaign.
