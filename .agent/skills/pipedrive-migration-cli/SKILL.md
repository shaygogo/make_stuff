---
name: pipedrive-migration-cli
description: Use when running, modifying, or debugging the CLI operations, file I/O, and manual migration workflow steps.
---

# Pipedrive Migration CLI and Operations

This skill covers the project's operational aspects, including script execution and the manual migration workflow.

## 1. CLI Usage (`migrate_pipedrive.py`)
The migration script supports three main input modes:

- **Single Scenario**: Fetch from Make.com API by ID.
  ```powershell
  python migrate_pipedrive.py --id <scenario_id>
  ```
- **Local File**: Process a local blueprint JSON.
  ```powershell
  python migrate_pipedrive.py --file <path_to_json>
  ```
- **Batch Processing**: Automatically process all `.json` files in the `./scenarios` directory.
- **Diagnostic Mode (HTTP Check)**: Scan for HTTP Pipedrive modules without performing migration.
  ```powershell
  python migrate_pipedrive.py --check-http
  ```
  *Note: Combined with `--id` or `--file` to check specific targets. This is critical for discovering which scenarios out of hundreds actually contain v1 API calls.*

## 2. Outputs
Migrated blueprints are saved to the `./migrated_scenarios/` directory with the suffix `_migrated.json`.

## 3. Migration Workflow
1. **Fetch**: The script retrieves the blueprint (API or File).
2. **Transform**: Recursive processing of all modules (including those in Routers) using `PIPEDRIVE_MODULE_UPGRADES`.
   - During transformation, structural mapper fixes are applied: `visible_to` string→int, `start` removal, `sort` splitting.
3. **Post-Processing**: `fix_getDealV2_custom_fields()` handles custom field rewriting, companion field detection, and batching (see `pipedrive-blueprint-transform` skill).
4. **Entity Field Renames**: `rewrite_entity_field_references()` rewrites V1→V2 field name changes across all 8 entity types via `ENTITY_RENAME_CONFIGS` (see `pipedrive-blueprint-transform` skill Section 6).
5. **Diagnostic Injection**: `inject_field_map_module()` adds a "Compose a String" module showing all Pipedrive field mappings.
6. **Save**: The script writes the new structure to disk.
7. **Manual Upload**: The user must manually upload the migrated blueprint to Make.com.
    - *Note*: Webhook URLs are NOT preserved for trigger modules — user must create new webhooks.

### Trigger Module Handling
Trigger modules (polling `watchDeals` and instant `NewDealEvent` etc.) are handled specially:
- **No `__IMTCONN__`**: Triggers use webhook configs, not API connections. The migration only swaps the module name.
- **Webhook re-registration required**: After import, the user must create a new webhook in Make.com and delete the old V1 webhook from Pipedrive Settings → Webhooks.
- **CLI output**: Prints `[!!] TRIGGER WARNING` with instructions.
- **Web UI**: Sends `X-Trigger-Warnings` header → frontend displays 🔔 amber warning with module details.
- **Tracking**: `_trigger_warnings` module-level list, cleared at start of each `migrate_blueprint()` call, included in stats dict.

## 4. Batch Migration (`batch_migrate_customer.py`)
Automates migration across an entire Make.com account using the API.

### Usage
```powershell
# Dry run (scan only, no changes)
python batch_migrate_customer.py --team-id 7616 --dry-run

# Full migration with auto-confirm
python batch_migrate_customer.py --team-id 7616 --yes

# Limited run (test with first N scenarios)
python batch_migrate_customer.py --team-id 7616 --limit 5 --yes

# Local only (no API creation, just save files)
python batch_migrate_customer.py --team-id 7616 --local-only
```

### Architecture
- **Imports `migrate_blueprint` from `migrate_pipedrive.py`** — all transformation logic is shared between the web server, CLI, and batch script.
- Uses `MAKE_API_TOKEN` from `.env` for API authentication.
- Creates scenarios in a dedicated "Pipedrive Migration" folder in Make.com.

### API Scenario Creation Requirements (CRITICAL)
When creating scenarios via `POST /scenarios`, the following are mandatory:

1. **`scheduling` parameter**: Must be a **JSON string** (not a Python dict). Without it, the API returns `SC400`.
   ```python
   "scheduling": json.dumps({
       "type": "indefinitely",
       "interval": 900  # 15 minutes
   })
   ```

2. **Webhook stripping**: Must remove `hook` bindings from trigger modules before creation. The original scenario's webhook can't be reused ("The hook already has a scenario assigned"). New webhooks are created automatically.
   ```python
   def strip_hook_bindings(modules):
       for module in modules:
           params = module.get('parameters', {})
           if 'hook' in params:
               del params['hook']
           # Recurse into routes
   ```

3. **Blueprint as string**: The blueprint must be serialized via `json.dumps()` with `ensure_ascii=False`.

### Output
- Local files saved to `./batch_migrated/` directory.
- Migration log saved as `migration_log_YYYYMMDD_HHMMSS.json`.
- New scenarios created in Make.com with `[V2]` prefix in the name.

## 5. Known Limitations
- **Manual Step**: Automating the upload back to Make.com is excluded for safety reasons (web server mode).
- **Verification**: Post-migration, the user should open the scenario in the Make.com UI to ensure mappings are visible and valid.
- **Webhook Reconnection**: After migration (manual or batch API), **trigger modules need new webhooks**. The old V1 webhook won't work with V2 triggers. This applies to both polling triggers (`watchDealsV2`) and instant triggers (`watchNewEvents`).
- **Subscription Modules**: 7 deprecated V1 subscription modules have no V2 replacement in Make.com.
- **List Persons in a Deal**: Deprecated V1 module — may need manual migration.

## 6. Learned Patterns

### Windows Console Encoding
Always reconfigure stdout/stderr for UTF-8 on Windows to handle Hebrew scenario names:
```python
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
```

### Hebrew Filename Handling
Hebrew filenames can cause `FileNotFoundError` on Windows due to encoding. Use `glob.glob()` instead of hardcoding filenames:
```python
files = glob.glob("*migrated*.blueprint.json")
```

### GitHub Secret Scanning
Blueprint JSON files contain Pipedrive connection IDs and API tokens. GitHub's secret scanning will **block pushes** containing these files. Always add to `.gitignore`:
```
*.blueprint.json
batch_migrated/
scenarios/
compose_output.txt
```

## 7. Web Interface (`app.py`)
A Flask-based web interface is available for easier use by non-developers.
- **Start**: `python app.py`
- **Access**: `http://localhost:5000`
- **Feature Matching**: The web app uses `migrate_blueprint()`, ensuring it gets the full transformation pipeline, including **GetPersonV2 injection** which may be missed if calling lower-level migration functions directly.
- **Auto-reload**: The Flask server auto-reloads when `migrate_pipedrive.py` is modified.

## 8. Default Connection Handling
For testing, a static Pipedrive OAuth connection ID has been set in `migrate_pipedrive.py`:
- **Default ID**: `4683394`
- **Reasoning**: Pipedrive v2 requires an OAuth connection (v1 used API keys). Since the IDs are incompatible, the script injects this working ID to make scenarios "plug-and-play" on the test team.
- **Overriding**: Both the CLI and Web App support overriding this ID via environment variables or UI inputs.

## 9. Troubleshooting Common Errors

### "'dict' object has no attribute 'split'"
This occurs in the diagnostic module (`inject_field_map_module`) when it encounters a **write module** where `custom_fields` is a dict (collection of values), not a string (comma-separated hashes for read modules). Fix: add `isinstance(cf_param, str)` guard before `.split()`.

### "No Pipedrive v1 modules found in this blueprint. Nothing to migrate."
This error occurs when the migration script scans the blueprint but finds no modules that require a v1 to v2 conversion.

**Common Causes:**
1. **Already Migrated**: The file you are uploading has already been processed and converted to v2. Check for suffixes like `_v2_migrated.json` or `(after).json`.
2. **Incorrect Source File**: In workspaces with multiple versions of the same blueprint (e.g., `(before).json` and `(after).json`), ensure you are selecting the **before** version.
3. **HTTP False Positives**: If you see a Pipedrive module in the Make.com UI but the script says "nothing to migrate", it might be a native HTTP module that doesn't target `pipedrive.com` in a way the script recognizes, or it's already using a v2 endpoint path.

**Verification Step:**
Open the JSON file and search for `"module": "pipedrive:`.
- If you see `pipedrive:getDeal`, it **needs** migration.
- If you see `pipedrive:getDealV2`, it is **already** migrated.

### "400: Validation failed: custom_fields: Invalid collection"
This means a simple field (text, number, enum) is being sent as an object `{"value": "X"}` when V2 expects a plain value. Check the metadata `expect` type — it should NOT be `collection` for simple fields.

### "400: Validation failed: custom_fields: Time custom field value expected 'object'"
This means a time field is being sent as a plain string `"16:15"` when V2 expects `{"value": "16:15"}`. The metadata `expect` type should be `collection` for time fields.

### "400: Parameter 'include_fields' is not allowed"
The `include_fields` parameter was added to a module that doesn't support it (e.g., `updateDealV2`). It should only be added to V2 get modules.

### "SC400: scheduling is required"
The `scheduling` parameter is missing from the API scenario creation call. It must be a JSON string.

### "The hook already has a scenario assigned"
Webhook bindings must be stripped from the blueprint before creating a new scenario via the API.

### Object fields showing JSON objects instead of values
When a monetary/time/address field shows `{"value": 180, "currency": "ILS"}` instead of `180`, the `.value` suffix is missing from the reference. Check that the companion field detection (via interface metadata) is working correctly for that module. The `monetary_hashes`, `time_hashes`, and `address_hashes` sets should contain the field's hash.

## 10. File Naming Conventions
To avoid confusion during batch processing or manual fixes, use the following naming patterns:
- `original_name.json`: The untreated v1 blueprint from Make.com.
- `original_name_v2_migrated.json`: The output of this tool.
- `original_name (before).json`: Often used in local testing to denote the source.
- `original_name (after).json`: Often used in local testing to denote the manually fixed or previously migrated version.

## 11. Agent Operational Gotchas (Windows/PowerShell)

These are recurring pitfalls when working on this codebase. Read these BEFORE starting work.

### PowerShell Inline Python Escaping
PowerShell mangles quotes, backslashes, and special chars in `python -c "..."` one-liners. **Write a temp `.py` script file instead** whenever the code contains:
- Backslashes (regex patterns, file paths)
- Nested quotes (JSON strings, f-strings)
- Hebrew/Unicode characters
- Multi-line logic

```powershell
# ❌ BAD — will break on backslashes and quotes
python -c "import re; print(re.sub(r'\\d+', 'X', 'abc123'))"

# ✅ GOOD — write to file, run, delete
# 1. Write script with write_to_file tool
# 2. python temp_script.py
# 3. Remove-Item temp_script.py
```

### Grep/Search Encoding Issues
Blueprint files contain **Hebrew text and escaped Unicode**. `grep_search` and `ripgrep` may return no results on files that clearly contain the search term. When this happens:
- **Use `view_file`** to read the file directly and search visually
- **Use Python** to search: `python -c "print('term' in open('file.json', encoding='utf-8').read())"`
- The issue is usually BOM markers or mixed encoding in the JSON files

### File Editing with Escaped Characters
`replace_file_content` and `multi_replace_file_content` require **exact string matching**. This fails on lines containing:
- Unicode escapes (`\u003c`, `\u003e` displayed by the viewer but stored as `<`, `>`)
- Heavy backslash escaping (regex patterns)
- Hebrew characters that the viewer renders differently

**Workaround**: Use a Python script to do the replacement:
```python
with open('file.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('old_exact_string', 'new_string', 1)
with open('file.py', 'w', encoding='utf-8') as f:
    f.write(content)
```

### PowerShell Output Truncation
Long output from `python migrate_pipedrive.py` gets garbled in PowerShell due to overlapping stderr/stdout streams. To capture clean output:
- **Pipe through `Select-Object`**: `python script.py 2>&1 | Select-Object -First 30`
- **Use `Select-String`** to filter specific lines: `python script.py 2>&1 | Select-String "WARNING|ERROR"`
- **Redirect to file**: `python script.py > output.txt 2>&1` then read the file

### Blueprint JSON Files Are Large
`migrate_pipedrive.py` is ~3300 lines and blueprint JSON files can be 10K+ lines. When exploring:
- Use `view_file_outline` first to get the structure
- Use `grep_search` to find specific functions/patterns
- Use `view_code_item` for individual functions
- Don't try to `view_file` the entire file — use line ranges

### Flask Dev Server Auto-Reload
The Flask app runs with `debug=True`, so it auto-reloads when `migrate_pipedrive.py` or `app.py` changes. No need to restart manually. But if the server is NOT running, you must start it with `python app.py` before testing the web UI.
