---
name: make-pipedrive-connection
description: Use when configuring Make.com connection IDs, OAuth requirements, or interacting with the Make.com API for scenario retrieval.
---

# Make.com & Pipedrive Connection Details

This skill covers the authentication and connection settings required for Pipedrive v2 modules.

## 1. Pipedrive OAuth Requirements
Legacy v1 modules use API Key connections. All migrated v2 modules MUST use OAuth (`pipedrive-auth`).

- **Connection ID**: `4683394`
- **Connection Label**: `My Pipedrive OAuth connection (noa benshitrit noabenshi@gmail.com)`

## 2. Make.com API Environment
To interact with the Make.com API (for fetching or updating blueprints), the following environment variables/constants are used:

- **Base URL**: `https://eu1.make.com/api/v2`
- **API Token**: `da4c33f6-42de-4f77-afb7-e7758a8431ca`
- **User Agent**: Should be set to a standard browser string (e.g., Mozilla) to avoid blocks.

## 3. Connection Migration
During transformation, the script must:
1. Identify `pipedrive` modules.
2. Replace the existing `connection` integer with the v2 Connection ID (`4683394`).
3. (Optional) Update the connection label in the blueprint if present.

## 4. Learned Patterns

### Make API Authentication & 403/404 Errors
- **Forbidden (403)**: The Make.com API often returns `403 Forbidden` if a `User-Agent` header is missing or too generic (like `python-requests`). 
- **User-Agent Fix**: Always use a full browser string.
  ```python
  headers = {
      "Authorization": f"Token {API_TOKEN}",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  }
  ```
- **Blueprint JSON Structure**: The `/scenarios/{id}/blueprint` API often returns data wrapped in a `{"response": {"blueprint": {...}}}` object. Scripts must check for the `response` key before accessing the blueprint or flow.
- **Not Found (404)**: If a scenario exists in the UI but returns `404` via API, it's often an Auth token scope issue or an organizational restriction.
- **MCP Limitations**: The `mcp_make_scenarios_get` tool may fail if the organization requires session-based access. Manual scripts with the correct `User-Agent` are the reliable fallback.

## 5. Project Target (Physiogroup Health Care)

| Organization | Org ID | Team ID | Zone |
| :--- | :--- | :--- | :--- |
| Physiogroup Health Care | 8538 | 7616 | eu1 |

**CRITICAL**: All migration activities are strictly restricted to this organization and team. No other organizations should be considered or searched unless explicitly requested.
