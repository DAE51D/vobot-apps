---
description: "GitHub Billing Dashboard: Create a real-time view of GitHub spending and Copilot usage in Home Assistant. Use when: building/updating the GitHub billing tab on the office dashboard, displaying current GitHub costs, monitoring subscription status, tracking monthly Copilot usage, calculating net/gross billing with discount breakdowns."
agent: 'agent'
tools:  ['search/changes', 'search', 'edit/editFiles', 'web/fetch', 'github/*', 'read/problems', 'search/usages', 'home-assistant-proxmox/*', ha-mcp/*, 'gitea/*']
context: |
  - GitHub account billing: https://github.com/settings/billing
  - GitHub API docs: https://docs.github.com/en/rest/billing
  - GitHub AI Billing: https://github.com/settings/billing/ai_usage?period=3&group=7&customer=43404083&chart_selection=2&view=time
  - Dashboard location: http://homeassistant.local:8123/dashboard-office#github
  - Home Assistant API: http://homeassistant.local:8123/api/
  - HA Dashboard storage: /homeassistant/.storage/lovelace.* (JSON files) — **DO NOT edit YAML**, use JSON edit via jq or direct file modification when Core is stopped
  - Dashboard editing UI: http://homeassistant.local:8123/config/lovelace/dashboards/Edit
  - HA YAML configs: /root/homeassistant/ (templates.yaml, automations.yaml, groups.yaml, scenes.yaml, scripts.yaml)
  - GitHub API Token (Plan scope, read-only, no expire): github_pat_11AOHA......a33CYn
  - Account: DAE51D (Copilot Pro $10/mo)
---

# GitHub Billing Dashboard Integration — Complete Implementation Guide

## Role

You are an expert Home Assistant specialist and GitHub billing API integration expert. Your task is to build a comprehensive real-time GitHub billing dashboard view that displays subscription costs, usage metrics, and spending forecasts in an intuitive, dashboard-friendly format.

## Goal

Create a "GitHub" tab/view on the office dashboard (http://homeassistant.local:8123/dashboard-office#github) that surfaces key GitHub billing data:
- **Current month metered usage and costs** ($1.14 Copilot premium requests)
- **Copilot usage breakdown** by AI model (Claude Haiku, Claude Sonnet, GPT-5 variants, etc.)
- **Cost before/after discounts** (showing Copilot Pro member discounts)
- **Monthly historical trends** (Jan-April data available)
- **Alert/notification triggers** when spending exceeds thresholds

## Token

I will provide the `github_pat_11AOHAW.......NlCUNMshO` in the app's configuration web page. This is the same one we used here so I know it works.

## Current Reality Check (June 2026)

- GitHub user billing has shifted from premium requests to AI credits for this account.
- Public REST endpoints still provide reliable aggregate totals (`usage/summary`, `usage`) but may not expose the same model/day split rows shown in the web UI AI usage page.
- If model/day table rows are missing from public API responses, treat GitHub UI values as snapshot data and label them clearly as such.
- Keep dashboard KPIs driven by the public API aggregates so cards remain stable even when UI-only breakdown endpoints change.
- The GitHub AI usage summary card is live and volatile while the page is open; do not treat its dollar amount as a fixed target. Capture it as a timestamped snapshot if you need to mirror it.

## Known Repair Warning and Fix

If Home Assistant Repairs (Spook) reports:
- `lovelace_unknown_entity_references_dashboard-office`
- unknown references: `sensor.github_billing_history`, `sensor.github_billing_summary`

Use this fix in `configuration.yaml` on the REST sensors:
- Add `unique_id: github_billing_summary` to "GitHub Billing Summary"
- Add `unique_id: github_billing_history` to "GitHub Billing History"

Then run:
1. `ha core check`
2. `ha core restart` (required for REST sensor registry changes)
3. Verify issue count drops in Repairs

### Your Actual Billing Data (April 2026)
- **Total Copilot cost**: $1.14 (net, after 91% discount!)
- **Copilot premium requests**: 308.99 requests processed
- **Models used this month**:
  - Claude Sonnet 4.6: 51 requests, $0.44 cost
  - Auto: GPT-5.3-Codex: 17.5 requests net, $0.70 cost
  - Auto: Claude Haiku 4.5: 17.1 requests (100% discounted)
  - Auto: Claude Sonnet 4.6: 40.5 requests (100% discounted)
  - Auto: GPT-5.4: 26.1 requests (100% discounted)
- **Base subscription**: Copilot Pro $10/month (so total GitHub spend ≈ $11.14/month)

## Key Resources

### GitHub Billing API Endpoints (User Level)

https://github.com/settings/personal-access-tokens/new

Your GitHub PAT has "`Plan`" user permissions (read-only). **Important**: These endpoints require the correct auth headers and API version. Note the tabs for **Repositories** OR **Account** next to the "Add Permissions" button.

```bash
# Get summary of all billing products and costs for current month
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/users/DAE51D/settings/billing/usage/summary"

# Get detailed monthly breakdown of usage and costs (historical)
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/users/DAE51D/settings/billing/usage"

# Get Copilot premium request usage (by model, quantity, cost) - THIS MONTH
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/users/DAE51D/settings/billing/premium_request/usage"
```

**Key Auth Requirements**:
- Use `Bearer` (not `token`) in Authorization header for GitHub PATs
- Include `X-GitHub-Api-Version: 2022-11-28` header (required!)
- Use `/users/{username}/` endpoint (not `/user/`)

#### Response Example (Summary - Tested ✅):
```json
{
  "timePeriod": {
    "year": 2026,
    "month": 4
  },
  "user": "DAE51D",
  "usageItems": [
    {
      "product": "Copilot",
      "sku": "copilot_premium_request",
      "grossQuantity": 308.999999999,
      "discountQuantity": 280.499999999,
      "netQuantity": 28.5,
      "grossAmount": 12.359999999,
      "discountAmount": 11.219999999,
      "netAmount": 1.14,
      "pricePerUnit": 0.04,
      "unitType": "requests"
    }
  ]
}
```

#### Response Example (Premium Requests by Model - Tested ✅):
Shows Copilot usage broken down by AI model with discounts:
```json
{
  "timePeriod": { "year": 2026, "month": 4 },
  "user": "DAE51D",
  "usageItems": [
    {
      "product": "Copilot",
      "sku": "Copilot Premium Request",
      "model": "Auto: Claude Sonnet 4.6",
      "unitType": "requests",
      "pricePerUnit": 0.04,
      "grossQuantity": 40.5,
      "grossAmount": 1.62,
      "discountQuantity": 40.5,
      "discountAmount": 1.62,
      "netQuantity": 0.0,
      "netAmount": 0.0
    },
    {
      "product": "Copilot",
      "sku": "Copilot Premium Request",
      "model": "Claude Sonnet 4.6",
      "unitType": "requests",
      "pricePerUnit": 0.04,
      "grossQuantity": 11.0,
      "grossAmount": 0.44,
      "discountQuantity": 0.0,
      "discountAmount": 0.0,
      "netQuantity": 11.0,
      "netAmount": 0.44
    }
  ]
}
```

#### Response Example (Usage History - Tested ✅):
Monthly breakdown Jan-April:
```json
{
  "usageItems": [
    {
      "date": "2026-04-01T00:00:00Z",
      "product": "copilot",
      "sku": "Copilot Premium Request",
      "quantity": 308.999999999,
      "unitType": "Requests",
      "pricePerUnit": 0.04,
      "grossAmount": 12.359999999,
      "discountAmount": 11.219999999,
      "netAmount": 1.14,
      "repositoryName": ""
    }
  ]
}
```

**Query Parameters**:
- `year`: YYYY (e.g., 2026)
- `month`: 1-12
- `day`: 1-31 (optional, for daily breakdown)
- `product`: Filter by product name (optional)

**Available Products**: Copilot, Actions, Codespaces, Git LFS, Models, Packages, Spark

### Dashboard Configuration

Dashboards are **NOT YAML files**—they are stored as JSON in `.storage/lovelace.*` files. The office dashboard is located at:
```
/homeassistant/.storage/lovelace.dashboard_office
```

When editing via Home Assistant UI, changes are automatically persisted to JSON. Can also edit JSON directly if stopping Core first (safest approach).

## Home Assistant Integration Approach

### Option A: REST Binary Sensor + Template Sensors (Recommended)
- Use REST integration to fetch GitHub API at intervals
- Parse JSON with template sensors
- Update dashboard cards with rendered data

### Option B: Automation + Script with REST Service
- Trigger automation on schedule (e.g., hourly, daily)
- Call `rest_command` or REST service to GitHub API
- Store results in input helpers or history stats

### Option C: Custom Integration / HACS Package
- Build a dedicated GitHub billing integration (out of scope for this prompt)
- Register sensors automatically
- Handle token refresh and error handling

**We'll use Option A** as it's cleanest and most maintainable.

## Step 1: Configure REST Integration

Add to `configuration.yaml`:

```yaml
rest:
  - resource: "https://api.github.com/users/DAE51D/settings/billing/usage/summary"
    name: "GitHub Billing Summary"
    method: GET
    headers:
      Authorization: !secret github_bearer_token
      Accept: "application/vnd.github+json"
      X-GitHub-Api-Version: "2022-11-28"
    scan_interval: 3600  # Refresh hourly
    json_attributes_path: "$.usageItems"
    json_attributes:
      - usageItems
    value_template: "{{ value_json.usageItems | length }}"
```

Add to `secrets.yaml`:
```yaml
github_bearer_token: "Bearer github_pat_11AOHAW.......foa33CYn"
```

## Step 2: Create Template Sensors

Add to `templates.yaml`:

```yaml
sensor:
  # Total metered usage cost (current month)
  - name: "GitHub Metered Cost"
    unique_id: github_metered_cost
    unit_of_measurement: "$"
    device_class: monetary
    state_class: total_increasing
    state: |
      {% set items = state_attr('sensor.github_billing_summary', 'usageItems') %}
      {% if items %}
        {{ (items | sumattr('netAmount') | round(2)) }}
      {% else %}
        0.00
      {% endif %}

  # Copilot usage cost
  - name: "GitHub Copilot Cost"
    unique_id: github_copilot_cost
    unit_of_measurement: "$"
    device_class: monetary
    value_template: |
      {% set items = state_attr('sensor.github_billing_summary', 'usageItems') %}
      {% if items %}
        {% set copilot = items | selectattr('product', 'equalto', 'Copilot') | list %}
        {% if copilot %}
          {{ (copilot | map(attribute='netAmount') | sum | round(2)) }}
        {% else %}
          0.00
        {% endif %}
      {% else %}
        0.00
      {% endif %}

  # Actions usage cost
  - name: "GitHub Actions Cost"
    unique_id: github_actions_cost
    unit_of_measurement: "$"
    device_class: monetary
    value_template: |
      {% set items = state_attr('sensor.github_billing_summary', 'usageItems') %}
      {% if items %}
        {% set actions = items | selectattr('product', 'equalto', 'Actions') | list %}
        {% if actions %}
          {{ (actions | map(attribute='netAmount') | sum | round(2)) }}
        {% else %}
          0.00
        {% endif %}
      {% else %}
        0.00
      {% endif %}

  # All products (for reference/debugging)
  - name: "GitHub Billing Status"
    unique_id: github_billing_status
    state: |
      {% set items = state_attr('sensor.github_billing_summary', 'usageItems') %}
      {% if items %}
        {{ items | length }} products tracked
      {% else %}
        Unknown
      {% endif %}
```

## Step 3: Dashboard Cards

### Card 1: Current Month Total Spend (Gauge)
```yaml
type: gauge
entity: sensor.github_metered_cost
name: "GitHub Monthly Spend"
unit: "$"
min: 0
max: 50
severity:
  green: 0
  yellow: 20
  red: 40
```

### Card 2: Subscription Overview (Markdown)
```yaml
type: markdown
content: |
  ## GitHub Subscription Status

  ### Active Subscriptions
  - **GitHub Free**: $0/mo
  - **Copilot Pro**: $10/mo
  
  ### This Month's Charges
  - **Metered Usage**: {{ states('sensor.github_metered_cost') }}
  - **Base Subscriptions**: $10.00
  - **Total**: ${{ (states('sensor.github_metered_cost') | float(0) + 10) | round(2) }}
```

### Card 3: Product Breakdown (Entities)
```yaml
type: entities
title: "Metered Usage by Product"
entities:
  - entity: sensor.github_copilot_cost
    name: "Copilot Premium Requests"
  - entity: sensor.github_actions_cost
    name: "Actions Minutes"
```

### Card 4: Detailed Usage (Custom HTML/Markdown)
```yaml
type: markdown
content: |
  {% set items = state_attr('sensor.github_billing_summary', 'usageItems') %}
  {% if items %}
  | Product | Units | Unit Price | Total |
  |---------|-------|------------|-------|
  {% for item in items %}
  | {{ item.product }} | {{ item.grossQuantity ~ " " ~ item.unitType }} | ${{ item.pricePerUnit }} | ${{ item.netAmount }} |
  {% endfor %}
  {% else %}
  No billing data available.
  {% endif %}
```

## Step 4: Optional Automations

### Notify when spending exceeds threshold
```yaml
alias: "GitHub: High Spending Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.github_metered_cost
    above: 30
action:
  - service: notify.notify
    data:
      message: "⚠️ GitHub spending this month: ${{ states('sensor.github_metered_cost') }}"
      title: "GitHub Billing Alert"
```

### Periodic refresh
```yaml
alias: "GitHub: Refresh Billing Data"
trigger:
  - platform: time_pattern
    hours: "/1"  # Every hour
action:
  - service: homeassistant.update_entity
    target:
      entity_id: sensor.github_billing_summary
```

## Available Card Types

### Built-in HA Cards (No Install Needed)
- **Gauge**: Display percentage/cost with severity colors
- **Tile**: Quick stat overview with large number
- **Markdown**: Rich text with Jinja templating for dynamic content
- **Entities**: List multiple entities with state
- **Statistics**: Historical trend line
- **History graph**: Time-series visualization

### HACS Custom Cards (Optional Installs)
- **[ApexCharts Card](https://github.com/RomRider/apexcharts-card)**: Advanced charts, bar/line/area
- **[Simple Statistics Card](https://github.com/thomasloven/lovelace-simple-weather-card)**: Minimal stats display
- **[Leaderboard Card](https://github.com/custom-cards/leaderboard-card)**: Rank-based display (useful if tracking multiple repos)
- **[State Switch Card](https://github.com/thomasloven/lovelace-state-switch-card)**: Conditional card display based on state

**Recommendation**: Start with built-in Gauge, Tile, and Markdown. If you want time-series trends, install **ApexCharts Card** from HACS.

## Troubleshooting

### REST API Returns 404 Not Found
- **Ensure correct auth headers**: Use `Bearer` (not `token`) in Authorization
- **Include API version**: Add header `X-GitHub-Api-Version: 2022-11-28`
- **Use correct endpoint path**: Use `/users/DAE51D/` not `/user/`
- Example curl to test:
  ```bash
  curl -L \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GITHUB_PAT" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/users/DAE51D/settings/billing/usage/summary" | jq .
  ```

### REST API Returns 401 Unauthorized
- Verify token is correct and hasn't been revoked
- Check token has "Plan" user permissions
- Token does NOT expire, so 401 usually means token was revoked

### Sensors Show "Unknown"
- Check HA logs for REST integration errors: 
  ```bash
  tail -f /homeassistant/home-assistant.log | grep -i "rest\|github"
  ```
- Ensure `headers` in REST config includes all three:
  - `Authorization: Bearer <token>`
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2022-11-28`

### Dashboard Cards Not Updating
- Check if REST sensor `scan_interval` is set properly (3600 = 1 hour)
- Manually trigger refresh: https://homeassistant.local:8123/developer-tools/service (call `homeassistant.update_entity`)
- Check REST entity state via API:
  ```bash
  curl -s -H "Authorization: Bearer $HASS_TOKEN" \
    http://homeassistant.local:8123/api/states/sensor.github_billing_summary | jq .
  ```

## Additional References

- GitHub REST API Billing Docs: https://docs.github.com/en/rest/billing
- Home Assistant REST Integration: https://www.home-assistant.io/integrations/rest/
- Home Assistant Template Sensors: https://www.home-assistant.io/integrations/template/
- Home Assistant Dashboard Cards: https://www.home-assistant.io/dashboards/cards/

---

# Implementation Lessons Learned (April 2026)

## ✅ What Worked Perfectly

### 1. REST Integration + Template Sensors Pattern
The traditional REST → Template Sensors approach was cleanest and most reliable:
- **3 REST sensors** polling daily (86400s scan_interval sufficient for billing data)
- **5 Template sensors** deriving calculated metrics (net cost, gross cost, discount, request count, total w/ subscription)
- All sensors ready in `/config/` after restart without additional configuration
- **Key**: Remember `scan_interval: 86400` for billing endpoints (data doesn't change that frequently)

### 2. Dashboard JSON Storage (Not YAML)
**Critical Discovery**: Lovelace dashboards are stored as **JSON in `.storage/lovelace.*` files**, NOT YAML:
- `/homeassistant/.storage/lovelace.dashboard_office` is the office dashboard
- Changes via UI automatically persist to JSON
- Can edit JSON directly with `jq` for rapid prototyping (safer than manual JSON editing)
- When making bulk edits, use `jq` with path selectors (e.g., `.views[3].cards[0].content |= ...`)
- **Safety**: Always backup file before bulk jq operations or stop Core before direct JSON edits

### 3. HTML Tables in Dashboard Cards
Markdown table rendering in HA dashboard cards is **brittle** (gets reformatted as paragraphs):
- **Solution**: Use raw HTML `<table>` structure with Jinja templating
- Wrap money amounts with `'%.2f' | format(state | float(0))` Jinja filter for strict 2-decimal formatting
- Extract table notes into separate `<p>` elements outside `</table>` to avoid row conflicts
- **Example structure**:
  ```html
  | Header 1 | Header 2 |
  <table>
  {%- for item in items -%}
    <tr>
      <td>{{ item.name }}</td>
      <td>${{ '%.2f' | format(item.amount | float(0)) }}</td>
    </tr>
  {%- endfor -%}
  </table>
  
  <p><em>Note about the table contents</em></p>
  ```

### 4. Modern Circular Gauge Cards for KPIs
`modern-circular-gauge` card works excellently for highlighting key metrics:
- Two gauges side-by-side with `columns: 2, square: false` grid layout
- Semantic severity coloring (green → yellow → red at defined thresholds)
- For billing: set `min: 0, max: 20` with thresholds at 10/15 to catch approaching limits
- **Rendering**: Gauges refresh instantly without configuration errors

### 5. Mushroom Template Cards for Pills
Mushroom's `mushroom-template-card` is perfect for quick stat pills:
- Clean, compact display with large icon + number + secondary text
- Supports `tap_action` for interactivity (e.g., refresh button)
- Format money amounts with `'%.2f' | format(...)` same as everywhere else for consistency
- Arrange 4 in a secondary grid row below gauges with proper spacing

### 6. Template Sensor Jinja Filtering
Use `round(2)` in template sensor **state templates** (not state_class):
```yaml
state: |
  {% set items = state_attr('sensor.github_billing_summary', 'usageItems') %}
  {{ (items | sumattr('netAmount') | round(2)) }}
```
This ensures base sensor state matches dashboard display, reducing surprises.

### 7. Config Validation Before Restart
Always run `ha config validate` before restarting:
- Catches YAML syntax errors early without downtime
- REST schema changes (e.g., flat vs nested `sensor:` key) show immediately
- Example error: `invalid option 'rest' under 'sensor'` → add `sensor:` nesting

### 8. Reload Services for Quick Iteration
Use targeted reload services instead of full `ha core restart`:
- `homeassistant.reload_all` → reloads automations, scripts, groups, templates in one call
- Template sensors take ~500ms to recalculate after reload
- Check sensor states via REST API immediately after reload to verify
- **Saves ~40 seconds per iteration** vs full HA restart

### 9. Git Workflow for Dashboard JSON
When dashboard JSON changes are large:
- Commit incrementally (don't batch all UI tweaks into one commit)
- Use `git show <hash>:.storage/lovelace.dashboard_office | jq .` to inspect specific versions
- `git diff` on `.storage` files shows JSON structure changes clearly with context
- Force-push feature branch: `git push --force-with-lease` (safer than `--force`)

---

## ❌ What Didn't Work (And Why)

### 1. ApexCharts Card for Monthly History Line Graph
**Problem**: Limited `data_generator` support in apexcharts-card (both v2.2.3 and current releases have only 2 refs)
- `data_generator` expects a *template string that returns JSON array* of points
- Hard to bind dynamic data from REST responses into apexcharts' consumption model
- Attempted workaround (native timeline) triggered config validation errors
- **Resolution**: Kept as working HTML table instead; acknowledged as future improvement path

### 2. Markdown Tables (Built-in Card Markdown)
**Problem**: HA reformats markdown table syntax into paragraph breaks instead of proper table cells
- Spacing/indentation issues; rows render as text blocks not cells
- CSS problems routing through card-mod
- **Solution**: Switch to HTML `<table>` with Jinja loops (works perfectly)

### 3. REST Schema: Flat vs Nested `sensor:` Key
**Problem**: HA 2025+ changed REST config schema from flat to nested under `sensor:` parent
- Old style: `rest: - resource: ... sensor: ...` (ERROR)
- New style: `sensor: - platform: rest resource: ...` or in REST block: `rest: - resource: ... then use sensor sub-key`
- **Solution**: Check HA docs for your version; run `ha config validate` to catch early

### 4. Template Sensors "Unknown" State After Restart
**Problem**: Bootstrap timing — template platform loads before REST integration has fetched data
- Sensors show "unknown" for ~1 second, then calculate
- **Solution**: Call `homeassistant.reload_all` or `automation/reload` + `group/reload` + custom reload for templates

### 5. Decimal Formatting Inconsistency (1.55 vs 1.6 vs 1.550000)
**Problem**: Template sensors with `round(2)` still vary in display depending on dashboard context
- Float precision varies; some displays show all decimals, others truncate
- **Solution**: Enforce format at dashboard layer with Jinja `'%.2f' | format(state | float(0))` on EVERY money display in cards (not just sensor state)
- Makes all money displays strictly XX.XX format across all cards

---

## 🎯 Practical Build Strategy (From Scratch)

### Phase 1: API Testing (15 minutes)
1. Get GitHub PAT with "Plan" scope from https://github.com/settings/personal-access-tokens
2. Test all 3 endpoints with curl to verify auth headers work:
   ```bash
   export GITHUB_PAT="your_token"
   curl -L \
     -H "Accept: application/vnd.github+json" \
     -H "Authorization: Bearer $GITHUB_PAT" \
     -H "X-GitHub-Api-Version: 2022-11-28" \
     "https://api.github.com/users/YOUR_USERNAME/settings/billing/usage/summary" | jq .
   ```
3. Capture response JSON structure; identify fields you'll display

### Phase 2: REST + Template Sensors (30 minutes)
1. Add 3 REST sensors to `configuration.yaml` with correct headers and `scan_interval: 86400`
2. Add 2-3 template sensors to `templates.yaml` for derived metrics
3. Run `ha config validate` to catch schema issues
4. Restart HA; verify sensors appear in States UI and show real data
5. Use `reload_all` service if templates are "unknown"

### Phase 3: Dashboard Layout (45 minutes)
1. Create 4 markdown/grid sections in lovelace (via UI or JSON edit):
   - **This Month**: 2 gauges + 4 pills grid
   - **By AI Model**: HTML table with row loop
   - **Monthly History**: HTML table with reverse sort
   - **Subscription**: Static info + breakdown table
2. Use HTML `<table>` for all tabular data; Jinja `'%.2f' | format()` on every money value
3. Test rendering; adjust grid columns/spacing as needed

### Phase 4: Polish + Validation (30 minutes)
1. Verify all money displays are strict 2-decimal
2. Add refresh button (mushroom-template-card with `homeassistant.update_entity` action)
3. Check for any rendering warnings/errors in HA logs
4. Commit to feature branch; include test screenshots in commit message

**Total Build Time**: ~2 hours from zero to fully functional dashboard

---

## 📊 Final Dashboard Structure (April 2026 Implementation)

**File**: `/homeassistant/.storage/lovelace.dashboard_office`

### Sections (4 total)
1. **"This Month"** (Grid, 2 cols)
   - `modern-circular-gauge` for Gross Copilot Cost ($0-20 range)
   - `modern-circular-gauge` for Discount/Included Usage ($0-20 range)
   - 4x `mushroom-template-card` pills below:
     - Total GitHub/Month + format
     - Copilot Metered Cost + format
     - Requests Used (count)
     - Refresh Button (action: `homeassistant.update_entity`)

2. **"Copilot by AI Model"** (Markdown card)
   - HTML table: Model name, Gross Req, Net Req, Gross $, Discount, Net $
   - Jinja row loop over REST sensor `usageItems` with `'%.2f' | format()` on money columns
   - Text note below (outside `</table>`): *Copilot Pro included requests appear as 100% discounted.*

3. **"Monthly Spend History"** (Markdown card)
   - HTML table: Month, Requests, Gross $, Discount, Net $
   - Newest-first sort: `sort(attribute='date', reverse=true)`
   - All money with `'%.2f' | format()` filter
   - **Future enhancement**: Replace with line graph card if better chart library found

4. **"Subscription"** (Markdown card)
   - Plan table (GitHub Free $0, Copilot Pro $10)
   - This Month total table ($subscription + $metered = total)
   - All totals with 2-decimal enforcement
   - Footer: Gross/Discount/Applied breakdowns in italics

### Sensors (8 total)
**REST (3)**
- `sensor.github_billing_summary`: Summary + usageItems
- `sensor.github_copilot_models`: Model breakdown + usageItems
- `sensor.github_billing_history`: Monthly data + usageItems

**Template (5)**
- `sensor.github_copilot_net_cost`: Summed netAmount
- `sensor.github_copilot_gross_cost`: Summed grossAmount
- `sensor.github_copilot_discount`: gross - net
- `sensor.github_copilot_requests`: Summed grossQuantity
- `sensor.github_total_monthly_cost`: metered + $10 subscription

---

## 🔧 Common Customizations

### Change Refresh Interval
Edit REST `scan_interval` in `configuration.yaml`:
- Hourly: `scan_interval: 3600`
- Daily: `scan_interval: 86400` (recommended for billing)
- Every 6 hours: `scan_interval: 21600`

### Add Spending Alert
Create automation in `automations.yaml`:
```yaml
alias: "GitHub Spending Alert"
trigger:
  platform: numeric_state
  entity_id: sensor.github_total_monthly_cost
  above: 50  # Alert if over $50
action:
  service: notify.notify
  data:
    message: "GitHub spending: {{ states('sensor.github_total_monthly_cost') }}"
```

### Update Gauge Thresholds
Edit `.storage/lovelace.dashboard_office` section "This Month" → gauge cards:
```json
{
  "type": "custom:modern-circular-gauge",
  "entity": "sensor.github_copilot_gross_cost",
  "min": 0,
  "max": 20,
  "severity": {
    "green": 0,
    "yellow": 10,
    "red": 15
  }
}
```

### Switch to Different Money Format
Replace all `'%.2f' | format(value | float(0))` with:
- `'%,.2f' | format(value | float(0))` for thousands separator ($1,234.56)
- `'${:.2f}' | format(value | float(0))` for explicit $ prefix (varies by Jinja engine)

---

## 📝 Notes for Future Maintainers

- **GitHub API Auth**: All endpoints require `Bearer` + `X-GitHub-Api-Version: 2022-11-28` header; token never expires
- **Billing Data Availability**: Previous 4 months available via history endpoint; current month via summary endpoint
- **Template Reload Timing**: Template sensors may show "unknown" for 1-2 seconds after reload; this is normal
- **Dashboard JSON**: Never create a `lovelace.yaml` file; dashboard changes must be in `.storage/lovelace.dashboard_office` JSON
- **Decimal Formatting**: Always apply `'%.2f' | format()` at display layer (cards), not just in sensor state, for consistency
- **Line Graph Future**: ApexCharts Card `data_generator` support is limited; consider upgrading chart library or using HA's native statistics entities if historical display becomes priority

---

