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
    - **Simple Fields** (Text, Number, Date, Enum, Set, etc.): Map directly as key-value pairs. The value is **unwrapped** from the v1 `{"value": X}` format.
        - *Format*: `"custom_fields": { "hash": "{{val}}" }`
    - **Complex Fields** (Time, Monetary, Address): MUST remain as objects. These are **NOT unwrapped**.
        - *Time Format*: `"custom_fields": { "hash": { "value": "16:15" } }`
        - *Money Format*: `"custom_fields": { "hash": { "value": 100, "currency": "USD" } }`
        - *Address Format*: `"custom_fields": { "hash": { "value": "123 Main St", ... } }`
- **Special Fields (Consolidation)**: 
    - Fields with suffixes (e.g., `hash_currency`, `hash_until`) must be grouped with their parent hash.
    - If a group contains *only* the value (no currency) AND the field type is NOT time/monetary/address, it is treated as a Simple Field and unwrapped to the direct value.

### Complex Field Types That Must Stay as Objects (CRITICAL)
The following field types MUST be sent as `{"value": ...}` objects, NOT plain values:
- `time` — e.g. `{"value": "16:15"}`
- `monetary` — e.g. `{"value": 100, "currency": "USD"}`
- `address` — e.g. `{"value": "123 Main St"}`

The code identifies these via `field_types` dict built from `old_expect` metadata:
```python
field_types = {f['name']: f.get('type') for f in old_expect if 'name' in f}
is_complex_type = (field_types.get(hash_key) in ['time', 'monetary', 'address'])
```

### Empty Value Filtering
If a time field has an empty or null value (`""`, `None`, `"null"`), it should be **omitted entirely** from `custom_fields` rather than sent as `{"value": ""}`, which causes validation errors.

## 2. Metadata Structure
The `metadata` object must be updated to ensure the UI renders the custom fields correctly:
- **Restore Section**: Custom field IDs must be listed under `metadata.restore.expect.custom_fields.nested`.
- **Expect Array**: The `expect` array must contain a `custom_fields` collection. The `spec` for each custom field **must match its actual type**:
  - **Simple fields** (text, number, enum, set, date): Keep the original `type` from the v1 definition.
  - **Complex fields** (time, monetary, address): Force `type: "collection"` with a `spec` containing a `value` sub-field.
  
  ```python
  complex_types = {'collection', 'monetary', 'address', 'time'}
  if original_type in complex_types or (has multiple spec items):
      f_copy['type'] = 'collection'
      f_copy['spec'] = [{"name": "value", "type": ..., "label": "Value"}]
  # else: keep original type (text, number, date, enum, etc.)
  ```

- **Custom Fields for getDealV2 (CRITICAL)**: In Pipedrive V2 API, custom field values are NOT returned by default. You must explicitly request them via the `custom_fields` query parameter. The migration handles this in `fix_getDealV2_custom_fields()` post-processing:
  1. **Static analysis**: Scans the entire blueprint for `MODULE_ID.HASH` patterns (40-char hex) referencing each getDealV2 module
  2. **Reference rewriting**: Rewrites flat `MODULE_ID.HASH` → `MODULE_ID.custom_fields.HASH` (V2 nests custom fields)
  3. **API limit (15)**: If >15 unique hashes referenced, splits into batches by injecting additional getDealV2 modules (same deal ID, different custom fields)
  4. Sub-fields like `_timezone_id` and `_currency` suffixes don't count as separate custom fields

### getDealV2 Custom Fields (CRITICAL)
```python
# Post-processing in fix_getDealV2_custom_fields():
# 1. Scan blueprint for referenced hashes
# 2. Set custom_fields param with only used hashes (max 15 per module)
# 3. Rewrite flat refs to nested: 2.HASH → 2.custom_fields.HASH
# 4. If >15: inject extra getDealV2 modules for additional batches
#    References to batch 2+ hashes point to the new module IDs

# ❌ WRONG: Don't request ALL custom fields (API limit is 15)
# ❌ WRONG: Don't use flat references (V2 nests under custom_fields)
# ❌ WRONG: Don't put custom field hashes in include_fields (that's for standard fields)
```

## 3. MakeAPICallV2 Body Construction
For modules migrated to `pipedrive:MakeAPICallV2` (e.g., Persons, Notes):
- **Body as String**: The `body` field must be a **stringified JSON string**, NOT a JSON object.
- **Payload Merging**: Static parameters (e.g., `visible_to`, `owner_id`) and dynamic mapper fields must be merged into a single flat object before stringification.
- **Hebrew/Non-ASCII Encoding**: Use `ensure_ascii=False` (or equivalent) to preserve Hebrew characters in the stringified body.
- **Custom Field Wrapping**: 40-character hash keys within the `body` string must also follow the complex/simple field rules above.

### MakeAPICallV2 Metadata Schema (CRITICAL)
When a module is converted to `MakeAPICallV2` via generic configuration, its `expect` metadata must be **entirely replaced** with the MakeAPICallV2 schema. Keeping the old module's expect fields causes "id is missing" errors.

```python
if generic_config:
    new_expect = [
        {"type": "hidden"},
        {"name": "url", "type": "text", "label": "URL", "required": True},
        {"name": "method", "type": "select", "label": "Method"},
        {"name": "headers", "type": "array", "label": "Headers"},
        {"name": "qs", "type": "array", "label": "Query String"},
        {"name": "body", "type": "any", "label": "Body"},
    ]
    # Also clear the old interface
    if 'interface' in module.get('metadata', {}):
        del module['metadata']['interface']
```

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
{{get(map(get(map(103.body.data; "options"; "field_code"; "HASH"); 1); "label"; "id"; 4.custom_fields.HASH); 1)}}
```

**Logic**:
1. `map(103.body.data; "options"; "field_code"; "HASH")` -> Finds the field definition matches the hash.
2. `get(...; 1)` -> Extracts the field definition object.
3. `map(options; "label"; "id"; VALUE)` -> Maps the option list, finding the "label" where "id" matches the V2 output value.
4. Outer `get(...; 1)` -> Unwraps the single-element array result of `map()`.

**CRITICAL**: Both the inner AND outer `map()` calls must be wrapped in `get(...; 1)` to extract single values from the arrays returned by `map()`.
