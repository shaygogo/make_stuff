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

## 4. Known Limitations
- **Manual Step**: Automating the upload back to Make.com is excluded for safety reasons.
- **Verification**: Post-migration, the user should open the scenario in the Make.com UI to ensure mappings are visible and valid.

## 5. Learned Patterns

### Windows Console Encoding
## 6. Web Interface (`app.py`)
A Flask-based web interface is available for easier use by non-developers.
- **Start**: `python app.py`
- **Access**: `http://localhost:5000`
- **Feature Matching**: The web app uses `migrate_blueprint()`, ensuring it gets the full transformation pipeline, including **GetPersonV2 injection** which may be missed if calling lower-level migration functions directly.

## 7. Default Connection Handling
For testing, a static Pipedrive OAuth connection ID has been set in `migrate_pipedrive.py`:
- **Default ID**: `4683394`
- **Reasoning**: Pipedrive v2 requires an OAuth connection (v1 used API keys). Since the IDs are incompatible, the script injects this working ID to make scenarios "plug-and-play" on the test team.
- **Overriding**: Both the CLI and Web App support overriding this ID via environment variables or UI inputs.

