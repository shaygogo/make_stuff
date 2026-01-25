---
name: pipedrive-blueprint-transform
description: Use when implementing or debugging the JSON transformation logic for Pipedrive modules, specifically regarding nested custom fields, metadata reconstruction, and MakeAPICallV2 body serialization.
---

# Pipedrive Blueprint Transformation Logic

This skill covers the structural transformation of Pipedrive v1 modules to v2 in Make.com blueprints.

## 1. Nested Mapping Structure (CRITICAL)
Pipedrive v2 modules in Make.com use a deeply nested structure for custom fields. If these are not followed, mappings will be **invisible** in the UI.

- **Mapper Object**: All custom fields (identified by 40-character hashes) must be placed inside a `custom_fields` object.
- **Value Wrapping**: Every custom field mapping must be wrapped in a `{"value": ...}` object.
    - *V1 Format*: `"hash": "{{val}}"`
    - *V2 Format*: `"custom_fields": { "hash": { "value": "{{val}}" } }`
- **Special Fields**: 
    - Monetary fields often require both `value` and `currency`.
    - Time fields are treated as collections.

## 2. Metadata Structure
The `metadata` object must be updated to ensure the UI renders the custom fields correctly:
- **Restore Section**: Custom field IDs must be listed under `metadata.restore.expect.custom_fields.nested`.
- **Expect Array**: The `expect` array must contain a `custom_fields` collection. The `spec` for each custom field should define it as a collection with a `value` key.
- **Include Fields**: The `parameters` object MUST include `include_fields`, which is an array of all custom field hashes mapped in that module.

## 3. MakeAPICallV2 Body Construction
For modules migrated to `pipedrive:MakeAPICallV2` (e.g., Persons, Notes):
- **Body as String**: The `body` field must be a **stringified JSON string**, NOT a JSON object.
- **Payload Merging**: Static parameters (e.g., `visible_to`, `owner_id`) and dynamic mapper fields must be merged into a single flat object before stringification.
- **Hebrew/Non-ASCII Encoding**: Use `ensure_ascii=False` (or equivalent) to preserve Hebrew characters in the stringified body.
- **Custom Field Wrapping**: 40-character hash keys within the `body` string must also be wrapped with `{"value": ...}`.

## 4. Field Renaming
Some modules require specific field key changes:
- **ListActivityDeals → listActivitiesV2**: The `id` field representing the deal ID must be renamed to `deal_id`.

## 5. Learned Patterns
 
### Identifying "Real" Pipedrive Calls
- **False Positives**: Pipedrive URLs found in `metadata.restore` or field definitions (e.g., a link to a Pipedrive deal for a user) are NOT API calls and should not be migrated.
- **Valid Targets**: Only URLs found within `module.mapper.url` or `module.parameters.url` (HTTP modules) should be flagged for HTTP-to-Pipedrive migration.

### Preserving Hebrew/Unicode in Bodies
- **Issue**: When stringifying a JSON body for `MakeAPICallV2`, standard `json.dumps()` escapes Hebrew characters (e.g., `\u05d0`).
- **Fix**: Always use `ensure_ascii=False` when generating the `body` string to ensure Hebrew content is readable and correctly processed by the Make.com execution engine.
  ```python
  m['mapper']['body'] = json.dumps(body_obj, ensure_ascii=False)
  ```

### Recursive Router Handling
- **Pattern**: Scenarios often have Pipedrive modules nested inside multiple layers of Routers.
- **Fix**: Ensure the migration script uses a recursive `process_blueprint` function that looks specifically for common container keys like `modules`, `elements`, and `routes`.

## 6. Person Data Injection (V2 Path Breaking Change)
In Pipedrive v2, `GetDeal` no longer returns embedded person data. Scenarios that rely on `{{X.person_id.phone}}` or `{{2.person_id.email}}` will break.

### Injection Logic
- **Detection**: Scan for `{{X.person_id.Y}}` references where `X` is a Deal-related module.
- **Action**: Inject a `pipedrive:GetPersonV2` module immediately after the Deal module.
- **Naming (CRITICAL)**: The module must be named `pipedrive:GetPersonV2` (Capital **G**). Using `getPersonV2` will result in "Module Not Found".

### Reference Rewriting (Pluralization)
V2 Person modules use different field names for contact info:
- **Phone**: `{{X.person_id.phone[].value}}` (V1) → `{{Y.phones[].value}}` (V2)
- **Email**: `{{X.person_id.email[].value}}` (V1) → `{{Y.emails[].value}}` (V2)
- **Name**: `{{X.person_id.name}}` (V1) → `{{Y.name}}` (V2)
*Note: `X` is the original Deal module ID; `Y` is the new injected Person module ID.*

## 7. HTTP Method Serialization
For `pipedrive:MakeAPICallV2` and native `http:MakeRequest` modules:
- **Case Sensitivity**: The `method` field must be **UPPERCASE** (e.g., `"GET"`, `"POST"`). Lowercase values will cause validation errors in Make.com.
- **Conversion**: Always apply `.upper()` to any method string during migration.
- **Cleaning**: Ensure v1 query parameters like `api_token` are stripped from the URL string even if they are hardcoded.


