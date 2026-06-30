---
name: datawrapper-cfr
description: Create Datawrapper charts that follow CFR.org's data-viz style guide. Invoke when the user asks to create, update, or style a Datawrapper chart, map, or graphic (bar, column, line, area, scatter, arrow, stacked_bar, multiple_column, choropleth). Encodes CFR's palette, typography, and editorial best practices (one clear point, Copper for emphasis, gray for "other", sort bars, direct-label lines, minimal gridlines).
---

# CFR Datawrapper Skill

Use this skill whenever the user wants a chart built, updated, or styled with the `mcp__datawrapper__*` tools. It turns a user request into a chart that matches CFR.org's house style. Always use theme `cfr` in datawrapper.

## Hard rule — Never invent data

Do not call `create_chart` or `update_chart` until the user has provided real data (inline rows, a file path, or a cited dataset). **Never fabricate, estimate, or "fill in plausible" numbers — not even as a placeholder or demo.** If data is missing, stop and ask for it. A chart with made-up numbers is worse than no chart.

## Step 1 — Nail the one point

Before touching a tool, make sure the chart has **one sentence describing what it shows**. If the user hasn't given one, ask. If there are multiple points, propose multiple charts rather than overloading one.

## Step 1b — Confirm the target folder

Always ask the user which folder the chart should live in before calling `create_chart`. Never guess or default silently.

When resolving folder names via `mcp__datawrapper__list_folders`, apply these aliases:
- **"CFR"** → search for team/folder name containing "Council on Foreign Relations" (`team_id: "councilonforeignrelations"`).
- **"TGH"** → search for team/folder name containing "Think Global Health" (`team_id: "thinkglobalhealth"`).

If the user names a subfolder that doesn't exist yet (e.g. "CFR / Examples / mcp"), surface the gap and ask whether to use the nearest existing parent or have them create it in the Datawrapper UI first — the MCP server does not expose a `create_folder` tool.

The one-sentence point drives:
- Chart type
- Which category gets Copper (the emphasis color)
- Title copy (the title should *state the point*, not describe the data)
- Subtitle (defines the data and units)
- Which annotations belong on the chart

## Step 2 — Pick the chart type

| Goal | Type | MCP chart_type |
| --- | --- | --- |
| Compare categories | Horizontal bars, sorted largest→smallest | `bar` |
| Compare categories, short labels | Columns | `column` |
| Trend over time | Line | `line` |
| Magnitude over time | Area | `area` |
| Before / after for each item | Arrow | `arrow` |
| Part-to-whole across categories | Stacked bar | `stacked_bar` |
| Compare several series per category | Grouped columns | `multiple_column` |
| Correlation between two variables | Scatter | `scatter` |
| Regional differences on a map | Choropleth (heatmap) | (use Datawrapper choropleth; MCP may not support directly — confirm with user) |

Use `mcp__datawrapper__list_chart_types` to confirm availability and `mcp__datawrapper__get_chart_schema` to inspect the exact properties for the chosen type before calling `create_chart` / `update_chart`.

## Step 3 — Apply the CFR palette

**Categorical palette (use in this order):**

| # | Name | Hex | Notes |
| - | --- | --- | --- |
| 1 | Data Copper | `#A63D00`| First color, reserve for the most important category |
| 2 | Light Copper | `#EE8244` | |
| 3 | Data Viridian | `#046953` | |
| 4 | Light Viridian | `#85B1A8` | |
| 5 | Dark Brown | `#62512E` | |
| 6 | Light Brown | `#B9AA82` | |
| 7 | Unimportant Gray | `#A4A4A4` | Use for "other," "rest of world," or de-emphasized categories |

Rules:
- **Use color sparingly.** Most charts need one or two colors. If a category is already labeled, don't also color-code it.
- **Copper = emphasis.** The most important category gets Copper. Everything else either follows the palette order, or — better — drops to Unimportant Gray.
- **Gray is a tool.** Pushing non-focus bars/lines to `#A4A4A4` is usually better than assigning them distinct colors.
- **Avoid many categories.** If there are more than ~5, aggregate the long tail into "Other" (gray).

**Sequential palette (choropleths, ordinal data):**
- Default: Copper scale (light→dark copper).
- Alternative: Viridian scale when you need a second scale or cooler tones.

**Divergent palette:** use when there's a meaningful midpoint (e.g., increase vs. decrease) or when more color variation is needed. Anchor one end Copper, the other Viridian.

## Step 4 — Typography and theme

- Typeface: **Season Sans** — Medium for body copy, **Semibold for titles**.
- Season Sans may not be a built-in Datawrapper font. Check if CFR has a custom Datawrapper theme; if so, set `theme` to that theme's id on the chart. If not, tell the user the font requires a custom theme on the Datawrapper account and fall back to the default without pretending otherwise.
- Enable `autoDarkMode: true` unless the user says otherwise — CFR.org renders in both light and dark.

## Step 5 — Titles, labels, annotations, gridlines

- **Title** states the main message ("Copper exports have tripled since 2010"), not the variable name.
- **Intro / subtitle** defines the data and units ("Refined copper, thousands of metric tons, 2010–2024").
- **Column names** shown on the chart (legend entries, axis labels, tooltip keys, direct labels, arrow keys) must be human-readable. Rename raw field names like `trust_2015_pct` → `2015`, `gdp_per_cap_usd` → `GDP per capita (USD)`, `co2_mt` → `CO₂ (metric tons)` before the chart is published. If the right label isn't obvious (ambiguous abbreviation, unclear units, unclear time period), ask the user rather than guessing. Rename via the data payload keys passed to `create_chart`/`update_chart` when feasible, otherwise via `column-format` / axis label fields.
- **Direct-label lines** where possible (`label-colors: true`, hide the legend). Legends are the fallback, not the default.
- **Sort bar charts** largest→smallest unless there's an inherent order (time, ranking).
- **Units on the axis.** Whenever values carry a unit (%, $, °F, metric tons, etc.), the axis tick labels themselves must show the unit — not just the subtitle. Use `y_grid_format` / `x_grid_format` (and `tooltip-number-format` for hover) with d3-format strings: `"0'%'"` for percent-as-integer (e.g. `74%`), `"$,d"` for whole-dollar amounts, `"$,.2f"` for dollars with cents. Don't use bare `"%"` — that multiplies by 100. The subtitle still defines the data, but readers should be able to read a tick and know the unit without looking elsewhere.
- **Remove gridlines** that aren't doing work. In the schema that usually means `x_grid: "off"` or `y_grid: "off"` — check the schema for the exact enum.
- **Annotations > gridlines** for storytelling. Add `text-annotations` for context (events, thresholds, callouts) especially on time series.
- **Notes** must start with `Note:` (single note) or `Notes:` (multiple). If the `notes` field is used, it should always open with one of those prefixes.
- **Source is required, never guessed.** If the user hasn't provided a source, ask before creating the chart. Do not fill in a plausible-sounding dataset name as a placeholder — a wrong source is worse than a blank one. `source-url` is optional; `source-name` is not.
- **No byline.** Leave `byline` empty. Do not put "CFR" or any author name in the byline field.
- Always provide `aria-description` for accessibility.

## Step 6 — Build the chart

Typical flow:

1. `mcp__datawrapper__list_chart_types` (only if unsure).
2. `mcp__datawrapper__get_chart_schema(chart_type=...)` to see exact property names/enums for the chosen type. **Do this before every create/update** — schemas differ per type and are the source of truth for names like `base-color`, `color-category`, `x_grid`, etc.
3. `mcp__datawrapper__create_chart` with the config. Pass data as an array of rows.
4. **ALWAYS confirm with the user before publishing.** After `create_chart`, share the edit URL (and preview if available) and explicitly ask for approval. Never call `mcp__datawrapper__publish_chart` without a clear go-ahead from the user in this turn — a prior "go ahead and build it" does not carry over to publishing.
5. `mcp__datawrapper__publish_chart` only after the user confirms.
6. Offer `mcp__datawrapper__export_chart_png` if the user wants a static asset.

For iteration, use `mcp__datawrapper__get_chart` + `mcp__datawrapper__update_chart` rather than re-creating.

When reporting a chart's folder location (e.g. after `get_chart`), always call `mcp__datawrapper__list_folders` and match the `folder_id` to a human-readable name. If the folder ID isn't in the list (e.g. it belongs to a team or is inaccessible), report the numeric ID and note that the name couldn't be resolved.

## Step 7 — Self-check before publishing

Before calling `publish_chart`, verify:

- [ ] Data came from the user (never fabricated or estimated).
- [ ] Title states the point, not the variable.
- [ ] Subtitle names the units.
- [ ] Axis tick labels show the unit (%, $, etc.) — not just the subtitle.
- [ ] No more than ~5 colored categories; rest are gray or aggregated.
- [ ] Copper is on the category the chart is *about*.
- [ ] Bars sorted (unless time/ranking dictates order).
- [ ] Gridlines minimized; annotations added if they earn their space.
- [ ] Source cited (asked the user if not provided — never guessed). Aria description set.
- [ ] Byline left empty.
- [ ] Notes (if any) start with `Note:` or `Notes:`.
- [ ] Column/axis/legend labels are human-readable (no raw field names like `trust_2015_pct`); asked if unsure.
- [ ] Dark mode handled.
