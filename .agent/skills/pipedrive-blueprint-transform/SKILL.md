---
name: pipedrive-blueprint-transform
description: Use when implementing or debugging the JSON transformation logic for Pipedrive modules, specifically regarding nested custom fields, metadata reconstruction, and MakeAPICallV2 body serialization.
---

# Pipedrive Blueprint Transformation Logic

This skill covers the structural transformation of Pipedrive v1 modules to v2 in Make.com blueprints.

## 1. Nested Mapping Structure (CRITICAL)
Pipedrive v2 modules in Make.com use a deeply nested structure for custom fields. If these are not followed, mappings will be **invisible** in the UI.

- **Mapper Object**: All custom fields (identified by 40-character hashes) must be placed inside a `custom_fields` object.
- **Value Wrapping (Conditional)**:
    - **Simple Fields** (Text, Number, Options): Map directly as key-value pairs.
        - *Format*: `"custom_fields": { "hash": "{{val}}" }`
    - **Complex Fields** (Money, Time Range): Must be wrapped in an object containing `value` and additional properties (currency, etc.).
        - *Format*: `"custom_fields": { "hash": { "value": 100, "currency": "USD" } }`
- **Special Fields (Consolidation)**: 
    - Fields with suffixes (e.g., `hash_currency`, `hash_until`) must be grouped with their parent hash.
    - If a group contains *only* the value (no currency), it is treated as a Simple Field and unwrapped to the direct value.

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
- **Products (POST/PUT/PATCH)**: The field `user_id` must be renamed to `owner_id`.

## 5. Search & Sort Parameter Migration
For `MakeRequest` / `itemSearch` to `MakeAPICallV2` conversion:

### Search
- **Path**: `itemSearch` → `/v2/deals/search` (usually).
- **Exact Match**: `exact_match=true` must be converted to `match=exact`.
- **Pagination**: The `start` parameter is incompatible with V2 cursor pagination and must be removed.

### Sorting
- **V1**: `sort="field ASC"` or `sort="field DESC"`.
- **V2**: Split into `sort_by="field"` and `sort_direction="asc|desc"`.

## 6. Learned Patterns
 
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

## 7. Person Data Injection (V2 Path Breaking Change)
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

## 8. Smart Field Injection (Enum/Set Resolution)
Pipedrive v2 requires Option **IDs** (integers) for `enum` (single select) and `set` (multi select) fields. V1 accepted Labels.

### Implementation Strategy
1. **Live Cross-Reference**: 
   - Before migration, the script must fetch all field definitions (`/dealFields`, `/personFields`) from Pipedrive to build a map: `{ "HASH": { "type": "enum", "options": [...] } }`.
2. **Detection**:
   - Check every mapped field hash against this map.
3. **Values Resolution**:
   - **Static Values (Labels)**: If the mapped value is a hardcoded string ("Tariff 2022") that matches a label in the options list, replace it directly with the **ID** (5877).
   - **Dynamic Values (Variables)**: If the mapped value contains `{{...}}`:
     1. **Inject Cache Module**: Provide a `MakeApiCallV2` module at the start of the scenario (only once) that calls `GET /v2/dealFields`.
     2. **Rewrite Mapping**: Wrap the variable in a `map()` function to resolve the ID at runtime.
        ```
        {{get(map(CACHE_MODULE_ID.body.data; "id"; "label"; CURRENT_VALUE); 1)}}
        ```
     *Note*: `CACHE_MODULE_ID` must be the ID of the injected `dealFields` module.

### HTTP Method Serialization
For `pipedrive:MakeAPICallV2` and native `http:MakeRequest` modules:
- **Case Sensitivity**: The `method` field must be **UPPERCASE** (e.g., `"GET"`, `"POST"`). Lowercase values will cause validation errors in Make.com.
- **Conversion**: Always apply `.upper()` to any method string during migration.
- **Cleaning**: Ensure v1 query parameters like `api_token` are stripped from the URL string even if they are hardcoded.

## 9. Output Reference Rewriting (Label Recovery)
Pipedrive v2 API returns custom field values as IDs (int) inside the `custom_fields` object, whereas v1 returns the Label (string) or a complex object with `.label` accessor.

### Issue
Downstream modules (e.g., Set Variable, Text Aggregator) often reference the label: `{{4.d1a9bcc2...2.label}}`.
In v2, this reference breaks because:
1. The field is moved to `custom_fields` wrapper.
2. The value is an ID, so `.label` property doesn't exist on it.

### Fix
The migration script detects these references and rewrites them into a dynamic lookup formula using the injected "Get Fields" helper module (which caches field definitions).

**Formula**:
```
{{map(get(map(103.body.data; "options"; "field_code"; "HASH"); 1); "label"; "id"; 4.custom_fields.HASH)}}
```

**Logic**:
1. `map(103.body.data; "options"; "field_code"; "HASH")` -> Finds the field definition matches the hash.
2. `get(...; 1)` -> Extracts the field definition object.
3. `map(options; "label"; "id"; VALUE)` -> Maps the option list, finding the "label" where "id" matches the V2 output value.
