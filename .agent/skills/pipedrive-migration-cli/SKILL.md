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
3. **Save**: The script writes the new structure to disk.
4. **Manual Upload**: The user must manually upload the migrated blueprint to Make.com.
    - *Note*: Webhook URLs are preserved during manual upload.

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
- **Webhook Reconnection**: After batch API creation, webhook triggers in new scenarios need to be manually reconnected by the user.

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
The `include_fields` parameter was added to a module that doesn't support it (e.g., `updateDealV2`). It should only be added to `getDealV2`.

### "SC400: scheduling is required"
The `scheduling` parameter is missing from the API scenario creation call. It must be a JSON string.

### "The hook already has a scenario assigned"
Webhook bindings must be stripped from the blueprint before creating a new scenario via the API.

## 10. File Naming Conventions
To avoid confusion during batch processing or manual fixes, use the following naming patterns:
- `original_name.json`: The untreated v1 blueprint from Make.com.
- `original_name_v2_migrated.json`: The output of this tool.
- `original_name (before).json`: Often used in local testing to denote the source.
- `original_name (after).json`: Often used in local testing to denote the manually fixed or previously migrated version.
