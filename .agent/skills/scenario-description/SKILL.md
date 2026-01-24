---
name: scenario-description
description: Use when adding auto-generated descriptions to Make.com scenario blueprints as embedded notes for better documentation and understanding of workflow purposes.
---

# Scenario Description Tool

## Purpose

Automatically analyze Make.com scenario blueprints and embed human-readable workflow descriptions as notes directly in the JSON. This helps document scenarios and makes them easier to understand when viewing in the Make.com editor.

## Key Component

**Script:** `add_scenario_description.py`

## How It Works

1. **Analyzes** the scenario blueprint JSON structure
2. **Identifies** module types and generates friendly names
3. **Creates** an HTML-formatted description with:
   - Scenario name and module count
   - Workflow steps with contextual emojis
   - Timestamps
4. **Embeds** the description as a note in `metadata.notes[]`
5. **Saves** the updated blueprint JSON

## Usage

```bash
# Create new file with description
python add_scenario_description.py "input.json" "output.json"

# Modify in-place
python add_scenario_description.py "scenario.json"
```

## Note Structure Location

**CRITICAL:** Notes must be added to `metadata.notes` (NOT root-level `notes`):

```json
{
  "name": "Scenario Name",
  "flow": [...],
  "metadata": {
    "notes": [
      {
        "moduleIds": [1],
        "content": "<html>...</html>",
        "isFilterNote": false,
        "metadata": {"color": "#00C853"}
      }
    ]
  }
}
```

## Styling Approach

The tool uses **simple HTML/CSS** compatible with Make.com's note renderer:

### What Works ✅
- Basic HTML tags: `<div>`, `<p>`, `<h4>`, `<b>`, `<br>`
- Inline styles: `margin`, `padding`, `color`, `font-size`, `border`
- Background colors and borders
- Simple layout with line breaks

### What Doesn't Work ❌
- Complex CSS: `flexbox`, `grid`, `gradients`
- Advanced positioning
- CSS animations

## Emoji System

Module types are automatically identified and marked with contextual emojis:

| Emoji | Module Type |
|-------|-------------|
| 🎯 | Triggers/Webhooks |
| 📖 | Read operations (Get, Search, List) |
| ✏️ | Write operations (Update, Create, Delete) |
| 🔀 | Routers |
| 🔁 | Iterators/Feeders |
| 🌐 | HTTP requests |
| ⚙️ | Default/Other |

## Current Styling Features

1. **Compact Spacing** - Tight margins (6-12px) and line-height (1.4-1.8)
2. **Subtle Backgrounds** - Light green header, gray workflow section
3. **Better Typography** - Blue pill badge for module count, bold scenario name
4. **Visual Hierarchy** - Clear sections with proper color contrast

## Module Name Generation

The tool converts Make.com module types to friendly names:

- `gateway:CustomWebHook` → "Webhook: [label]"
- `airtable:ActionGetRecord` → "Get Airtable Record ([table])"
- `builtin:BasicRouter` → "Router"
- `http:ActionSendData` → "HTTP Request"
- etc.

## Integration Options

This tool can be used:

1. **Standalone** - Run manually on exported blueprints
2. **Migration Pipeline** - Add descriptions during Pipedrive v2 migration
3. **Web API** - Integrate into Flask app as `/api/describe` endpoint
4. **Batch Processing** - Process multiple scenarios in a directory

## Testing

Tested successfully with:
- ✅ Simple 3-module scenario (Dashboard start)
- ✅ Make.com note rendering verified
- ✅ HTML styling compatibility confirmed

## Known Limitations

- Make.com strips advanced CSS (gradients, flexbox)
- Background colors may not render in all cases
- Border-radius support is limited
- Emoji rendering depends on Make.com's font stack

## Future Enhancements

Potential improvements:
- Add filter condition descriptions
- Include connection information
- Show module parameter details
- Support for router branch descriptions
- Detailed iterator/aggregator logic
