---
description: "Vobot Copilot Spend App: Build/update the 'copilot' Vobot Mini Dock app that graphs GitHub Copilot / billing spend on-device. Use when: building or refining the copilot app screens, wiring the GitHub Billing REST API, tuning gauge/chart ranges, or debugging the device-side fetch."
agent: 'agent'
tools: ['search/changes', 'search', 'edit/editFiles', 'execute/runInTerminal', 'github/*']
context: |
  - GitHub account billing (web UI, human-only reference): https://github.com/settings/billing
  - GitHub REST Billing API docs: https://docs.github.com/en/rest/billing
  - GitHub AI Billing (authenticated web UI, not an API): https://github.com/settings/billing/ai_usage
  - App source: D:\daevid\Code\Vobot\copilot\apps\copilot\__init__.py
  - App manifest: D:\daevid\Code\Vobot\copilot\apps\copilot\manifest.yml
  - Vobot platform conventions: see .github/copilot-instructions.md (lifecycle, LVGL, web settings, upload/debug workflow)
  - Reference dashboard this app is modeled after: http://homeassistant.local:8123/dashboard-office/github (HA dashboard, not part of this app — visual reference only)
  - GitHub API Token (Plan scope, read-only, no expire) — user supplies via the app's own web config page at http://192.168.1.32/apps, NOT hardcoded in source
  - Account: DAE51D (Copilot Pro $10/mo)
---

# Copilot Spend App — Vobot Mini Dock

## Role

You are an expert MicroPython/LVGL developer building Vobot Mini Dock apps (see `.github/copilot-instructions.md` for the full platform guide — lifecycle hooks, LVGL widget patterns, web settings form, upload/debug workflow). This prompt is scoped to the **`copilot` app**: an on-device monitor for GitHub Copilot/billing spend, modeled visually on an existing Home Assistant dashboard but implemented natively against the GitHub REST API — no HA dependency.

## Goal

A 4-screen app (scroll wheel cycles pages, ENTER forces a refresh) showing:
1. Four arc gauges — Credit Value Used $, Included Savings $, Credits/Requests Used, Net Billed Cost $
2. Two chart panels — daily + cumulative credits, daily + cumulative $ value
3. Countdown to next billing reset + reset date
4. Scrollable usage-by-product/day table

## Current Reality Check (as of mid-2026)

- GitHub billing has shifted from "premium requests" to "AI credits" for Copilot accounts. The public REST endpoints below still return reliable **aggregate totals** (dollar amounts, quantities) but the plan's **hard caps/allowances** (e.g. "9000 credits included", "$70 included savings") are **not exposed by any public API** — they only render on the authenticated `billing/ai_usage` web page, which this device cannot scrape (no browser, PAT-only auth).
- **Design decision**: gauge/chart max-ranges and the billing reset day/hour are user-configurable settings with sane defaults, not derived values. Treat anything that looks like a "plan limit" as config, not API data.
- If a model/day breakdown endpoint 404s (deprecated by the credits migration), fall back to the plain per-item usage rows from `/settings/billing/usage` rather than failing the whole screen.

## GitHub REST Billing API (User Level)

Auth requirements (all endpoints):
- `Authorization: Bearer <PAT>` (not `token`)
- `Accept: application/vnd.github+json`
- `X-GitHub-Api-Version: 2022-11-28` (docs now show `2026-03-10` as the current example version; `2022-11-28` remains valid/back-compat and is what this account's PAT has been tested against — bump only if a real breaking change is hit)
- Path uses `/users/{username}/...` (not `/user/...`)
- PAT needs "Plan" user permission (read-only, no expiry): https://github.com/settings/personal-access-tokens/new

```bash
# Current month aggregate summary (drives the 4 gauges)
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/users/DAE51D/settings/billing/usage/summary"

# Daily-granularity usage (drives the history charts + table)
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/users/DAE51D/settings/billing/usage?year=2026&month=7"
```

### Response shape — Summary
```json
{
  "timePeriod": { "year": 2026, "month": 7 },
  "user": "DAE51D",
  "usageItems": [
    {
      "product": "Copilot",
      "sku": "copilot_premium_request",
      "grossQuantity": 4445.0,
      "discountQuantity": 3500.0,
      "netQuantity": 945.0,
      "grossAmount": 44.45,
      "discountAmount": 35.0,
      "netAmount": 9.45,
      "pricePerUnit": 0.01,
      "unitType": "credits"
    }
  ]
}
```

### Response shape — Usage (daily rows, used for charts/table)
```json
{
  "usageItems": [
    {
      "date": "2026-07-14T00:00:00Z",
      "product": "Copilot",
      "sku": "Copilot Premium Request",
      "quantity": 692.0,
      "unitType": "credits",
      "pricePerUnit": 0.01,
      "grossAmount": 6.92,
      "discountAmount": 5.0,
      "netAmount": 1.92,
      "repositoryName": ""
    }
  ]
}
```

**Query params**: `year` (YYYY), `month` (1–12), `day` (1–31, optional — daily breakdown), `product` (optional filter). **Products**: Copilot, Actions, Codespaces, Git LFS, Models, Packages, Spark.

## Device-Side Fetch Pattern

Follow the proxmox app's pattern (`proxmox/apps/proxmox/__init__.py`) for `urequests`-based fetch: minimal headers, `Connection: close`, always `resp.close()` in a `finally`, wrap in try/except and set an error flag the UI can render instead of crashing. Throttle fetches in `on_running_foreground()` against a configurable poll interval (default 30 min — billing data doesn't change fast enough to justify more, and this keeps well under GitHub's rate limits); do the first fetch during `on_start()` so the UI isn't empty on entry.

Aggregate the daily usage rows client-side into two small parallel arrays (daily values + running cumulative) capped at ~31 points — do **not** hold onto the full raw JSON longer than needed; the device has limited RAM.

## LVGL Notes Specific to This App

- Device runs **LVGL 9.1** (confirmed via Vobot forum: chart ticks moved from `set_axis_tick()` to a `scale`-based API in 9.x).
- `lv.chart` type (`lv.chart.TYPE.LINE` / `.BAR`) is set **per chart object, not per series** — a single chart can't mix a bar series and a line series. To get the "daily bars + cumulative line" look from the reference dashboard, **stack two `lv.chart` widgets** at the same position/size: a BAR chart behind for daily values, a LINE chart on top with a transparent background (`set_style_bg_opa(0, lv.PART.MAIN)`) and its own independent axis range for the cumulative series.
- Reuse the arc-gauge pattern already proven in the proxmox app (rotation 270, bg angles 0–360, hidden knob) for the 4 gauge screen — don't reinvent it.
- Reuse the ntfy app's page-caching approach (build all screens once in `on_start`, toggle `HIDDEN` flag on scroll instead of `scr.clean()` + rebuild) for snappy scroll-wheel paging.

## Additional References

- GitHub REST API Billing Docs: https://docs.github.com/en/rest/billing
- GitHub REST API Billing Usage: https://docs.github.com/en/rest/billing/usage
- LVGL 9 Chart widget docs: https://lvgl.io/docs/open/widgets/chart
- Vobot Mini Dock developer reference: https://dock.myvobot.com/developer/reference/
