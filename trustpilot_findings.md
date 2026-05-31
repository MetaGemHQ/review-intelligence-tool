# Trustpilot scraping and review extraction: findings

Notes from sourcing real review data for the Review Intelligence Tool. Two topics
were scraped from Trustpilot via Firecrawl and ingested into the tool. This
summarizes what worked, what broke, and the guard the pipeline needs as a result.

## What was scraped

| Topic | Source | Date | Reviews | Rating spread (1 to 5 stars) |
|---|---|---|---|---|
| Volkswagen (US) | trustpilot.com/review/www.vw.com | 2026-05-17 | 20 | almost entirely 1 star |
| Notion | trustpilot.com/review/notion.so | 2026-05-28 | 20 | 14x1, 1x2, 1x3, 2x4, 2x5 |

Both sets are page-1 reviews, stored with `source = "trustpilot"`. The two topics
were chosen to be different on purpose: one automotive company with near-uniform
negative reviews, one SaaS product with a genuinely mixed pile. That contrast is
what makes them useful as a comparison-table test bed rather than two versions of
the same easy case.

## Main finding: silent synthetic data on a blocked page

The most important issue, and the reason this writeup exists.

Firecrawl's JSON-extraction mode, when pointed at a page it could not actually
fetch, **returned fabricated reviews without raising any error**. On the first
Notion attempt it served a cached 403 and, instead of failing, produced five
generic-shaped but entirely invented reviews that looked plausible. Nothing in the
response signalled that the content was not real.

This is the dangerous failure mode for a review-intelligence tool: fake input does
not look like an error, it looks like data, and it would flow straight into the
evaluation and produce a confident but meaningless report.

It was cleared by forcing a real fetch and a human-readable format:
- `proxy: enhanced`
- `maxAge: 0` (bypass the cache)
- markdown output instead of JSON extraction

Once the markdown contained the genuine review text, extraction was reliable.

**Implication for the pipeline:** before trusting any scraped batch, verify that
the fetched markdown contains real, page-specific content. Do not trust a
structured-extraction response on its own. This is a content-authenticity guard at
ingestion time, separate from the prompt-injection hardening discussed earlier.

## Confirming the data was real once ingested

After the scrape was fixed, the evaluations themselves were clean:
- Notion run: sentiment "mixed", rating 2, which matches Trustpilot's own
  algorithmic score of 2.4 for the page. All 7 extracted themes (UI/aesthetics,
  pricing, customer service, functionality, billing, AI features, trust) were
  checked against the source reviews. Zero hallucinated themes.
- VW run: sentiment "negative", rating 1, each theme supported by multiple raw
  reviews.

So the extraction layer is trustworthy once the input is verified real. The risk
sits entirely at the fetch step, not the model step.

## Practical limits observed

- **Scraping is structure-dependent and fragile.** It works while the target
  site's layout holds and breaks when the site changes. Pre-populated HTML is
  straightforward; JavaScript-rendered content needs an intermediate tool. This
  matches the earlier guidance to treat scraping as a proof-of-concept technique,
  not a production data source.
- **Per-review length cap.** The tool caps reviews at 1000 characters. Three
  Notion reviews ran longer and were trimmed at clean sentence boundaries so no
  text was cut mid-thought. Worth knowing that very long reviews lose their tail.
- **Page-1 only.** Both sets are first-page reviews, so they inherit Trustpilot's
  ordering and its general self-selection skew toward people motivated to leave a
  review (often unhappy ones).

## Recommendation

1. Add a content-authenticity check at ingestion: confirm the fetched text is
   real page content before it is allowed into the database.
2. Keep scraping as a proof-of-concept input. For anything beyond that, a proper
   reviews API or an export would be more durable than HTML scraping.
3. Prefer markdown fetches over blind JSON extraction, so a failed fetch is
   visible rather than silently filled in.
