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

## 3. V2 Get Modules — Custom Field Handling (READ operations)

In Pipedrive V2 API, custom field values are NOT returned by default in GET responses. You must explicitly request them via the `custom_fields` query parameter. This applies to **ALL** V2 get modules:

### Supported V2 Get Modules
```python
V2_GET_MODULES = {
    'pipedrive:getDealV2',
    'pipedrive:getProductV2',
    'pipedrive:getPersonV2',     # Note: also getPersonV2 (auto-injected)
    'pipedrive:GetPersonV2',     # Note: Capital G (Make.com casing)
    'pipedrive:getOrganizationV2',
    'pipedrive:getActivityV2',
}
```

### Fields API Endpoints (for .label lookups)
```python
MODULE_TO_FIELDS_ENDPOINT = {
    'pipedrive:getDealV2':         '/v2/dealFields',
    'pipedrive:getProductV2':      '/v2/productFields',
    'pipedrive:getPersonV2':       '/v2/personFields',
    'pipedrive:GetPersonV2':       '/v2/personFields',
    'pipedrive:getOrganizationV2': '/v2/organizationFields',
    'pipedrive:getActivityV2':     '/v2/activityFields',
}
```

### `include_fields` and `custom_fields` Expect (CRITICAL)
All V2 get modules need both `include_fields` and `custom_fields` in their expect section. The code checks:
```python
v2_get_modules = (
    'pipedrive:getDealV2', 'pipedrive:getProductV2',
    'pipedrive:getPersonV2', 'pipedrive:GetPersonV2',
    'pipedrive:getOrganizationV2', 'pipedrive:getActivityV2',
)
```

### Dynamic ID Field
Each V2 get module gets a dynamic ID field with a human-readable label based on the entity type:
- `getDealV2` → "Deal ID"
- `getProductV2` → "Product ID"
- `GetPersonV2` → "Person ID"
- `getOrganizationV2` → "Organization ID"
- `getActivityV2` → "Activity ID"

### The `fix_getDealV2_custom_fields()` Post-Processing Pipeline

This function (despite its name) handles ALL V2 get modules. It runs in two passes:

**PASS 1: Inject helper modules** for `.label` lookups (one per entity type):
- Each helper calls the fields API (e.g., `GET /v2/dealFields`) and caches field definitions
- Used by the lookup formula to resolve option IDs back to labels

**PASS 2: Rewrite references** (serialized as JSON string manipulation):
1. **Detect object-type fields** from companion fields in interface metadata (see Section 4)
2. **Rewrite companion references** (e.g., `MOD.HASH_currency` → `MOD.custom_fields.HASH.currency`)
3. **Fix `.customRaw.HASH`** → `.custom_fields.HASH`
4. **Fix `.label` suffix** → dynamic lookup formula
5. **Rewrite flat refs** → `MOD.custom_fields.HASH`
6. **Append `.value`** for object-type fields
7. **Handle batching** if >15 custom fields referenced

## 4. Object-Type Custom Fields (V1→V2 Breaking Change) — CRITICAL

In V1, many field types returned plain values. In V2, they return JSON objects. This breaks downstream references.

### Detection via Companion Fields
The script detects object-type fields by scanning the module's V1 `metadata.interface` for companion fields:

| Companion Suffix | Field Type | Detection |
|:---|:---|:---|
| `HASH_currency` | Monetary | `fname.endswith('_currency')` |
| `HASH_timezone_id` | Time | `fname.endswith('_timezone_id')` |
| `HASH_formatted_address` | Address | `fname.endswith('_formatted_address')` |

### V1 → V2 Value Mapping

| Field Type | V1 Output | V2 Output |
|:---|:---|:---|
| **Monetary** | `HASH` = `180`, `HASH_currency` = `"ILS"` | `custom_fields.HASH` = `{"value": 180, "currency": "ILS"}` |
| **Time** | `HASH` = `"15:15:00"`, `HASH_timezone_id` = `240` | `custom_fields.HASH` = `{"value": "15:15:00", "timezone_id": 240, ...}` |
| **Address** | `HASH` = `"בני בנימין 7, נתניה"`, `HASH_locality` = `"Netanya"` | `custom_fields.HASH` = `{"value": "בני...", "locality": "Netanya", ...}` |

### Reference Rewriting Rules

**Step 1 — Companion references** (BEFORE flat→nested rewrite):
```
MOD.HASH_currency         → MOD.custom_fields.`HASH`.currency
MOD.HASH_timezone_id      → MOD.custom_fields.`HASH`.timezone_id
MOD.HASH_timezone_name    → MOD.custom_fields.`HASH`.timezone_name
MOD.HASH_formatted_address → MOD.custom_fields.`HASH`.formatted_address
MOD.HASH_locality          → MOD.custom_fields.`HASH`.locality
MOD.HASH_street_number     → MOD.custom_fields.`HASH`.street_number
(... and all other address sub-fields)
```

**Step 2 — Base field `.value` appending** (AFTER flat→nested rewrite):
```
MOD.custom_fields.`HASH`  → MOD.custom_fields.`HASH`.value
```
Uses negative lookahead to avoid double-appending on refs that already have a subfield:
```python
value_pattern = rf'({mod_id}\.custom_fields\.`?{h}`?)(?!\.(value|currency|timezone_id|timezone_name|label|formatted_address|street_number|route|sublocality|locality|admin_area_level_1|admin_area_level_2|country|postal_code|subpremise))'
```

### Address Field Companion Suffixes (Complete List)
```python
ADDRESS_SUFFIXES = [
    '_formatted_address', '_street_number', '_route', '_sublocality',
    '_locality', '_admin_area_level_1', '_admin_area_level_2',
    '_country', '_postal_code', '_subpremise'
]
```

## 5. MakeAPICallV2 Body Construction
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

## 6. Field Renaming
Some modules require specific field key changes:
- **ListActivityDeals → listActivitiesV2**: The `id` field representing the deal ID must be renamed to `deal_id`.
- **Products (POST/PUT/PATCH)**: The field `user_id` must be renamed to `owner_id`.

## 7. Search & Sort Parameter Migration
For `MakeRequest` / `itemSearch` to `MakeAPICallV2` conversion:

### Search
- **Path**: `itemSearch` → `/v2/deals/search` (usually).
- **Exact Match**: `exact_match=true` must be converted to `match=exact`.
- **Pagination**: The `start` parameter is incompatible with V2 cursor pagination and must be removed.

### Sorting
- **V1**: `sort="field ASC"` or `sort="field DESC"`.
- **V2**: Split into `sort_by="field"` and `sort_direction="asc|desc"`.

## 8. Learned Patterns
 
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

## 9. Person Data Injection (V2 Path Breaking Change)
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

## 10. Smart Field Injection (Enum/Set Resolution)
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

## 11. Output Reference Rewriting (Label Recovery)
Pipedrive v2 API returns custom field values as IDs (int) inside the `custom_fields` object, whereas v1 returns the Label (string) or a complex object with `.label` accessor.

### Issue
Downstream modules (e.g., Set Variable, Text Aggregator) often reference the label: `{{4.d1a9bcc2...2.label}}`.
In v2, this reference breaks because:
1. The field is moved to `custom_fields` wrapper.
2. The value is an ID, so `.label` property doesn't exist on it.

### Fix
The migration script detects these references and rewrites them into a dynamic lookup formula using the injected "Get Fields" helper module (which caches field definitions).

**Formula (CORRECT)**:
```
{{get(map(get(map(103.body.data; "options"; "field_code"; "HASH"); 1); "label"; "id"; 4.custom_fields.HASH); 1)}}
```

**Logic**:
1. `map(103.body.data; "options"; "field_code"; "HASH")` -> Finds the field definition that matches the hash.
2. `get(...; 1)` -> Extracts the field definition object (first element from the map array).
3. `map(options; "label"; "id"; VALUE)` -> Maps the option list, finding the "label" where "id" matches the V2 output value.
4. Outer `get(...; 1)` -> Unwraps the single-element array result of `map()`.

**CRITICAL**: 
- Use `"field_code"` (NOT `"key"` or `"field_key"`) to match field definitions by hash
- Both the inner AND outer `map()` calls must be wrapped in `get(...; 1)` to extract single values from the arrays returned by `map()`

## 12. Diagnostic "Compose a String" Module (`inject_field_map_module`)

The migration injects a diagnostic module that shows ALL Pipedrive module outputs for debugging.

### What It Shows
- **All Pipedrive modules** (not just V2 get modules): creates, updates, lists, searches, API calls, auto-injected person modules, and helper API call modules
- For each module: designer name, module type
- **Only referenced fields** — fields actually used downstream in the scenario
- **Standard fields**: mapped as `{{MODULE_ID.field}}`
- **Custom fields**: mapped as `{{MODULE_ID.custom_fields.HASH}}`
- **Companion fields**: correctly mapped (e.g., `{{MODULE_ID.custom_fields.HASH.currency}}`)

### Placement
The diagnostic module is placed after the **last Pipedrive module** with referenced outputs in the scenario flow.

### Key Implementation Detail
The `custom_fields` mapper value is a **dict** for write modules and a **string** for read modules. Must use `isinstance(cf_param, str)` before calling `.split()`:
```python
cf_param = mod.get('mapper', {}).get('custom_fields', '')
if cf_param and isinstance(cf_param, str):
    for h in cf_param.split(','):
        ...
```

## 13. Batching Custom Fields (API Limit: 15)

The Pipedrive V2 API limits `custom_fields` to 15 hashes per request.

### Implementation
1. If ≤15 hashes: set `custom_fields` directly on the module
2. If >15 hashes: split into batches, inject additional V2 get modules
3. **CRITICAL**: Overflow batch modules must use the **original module type** (e.g., `getProductV2`), NOT hardcoded `getDealV2`
```python
new_mod = {
    'module': mod.get('module', 'pipedrive:getDealV2'),  # Use actual module type
    ...
}
```
4. References to batch 2+ hashes are rewritten to point to the new module IDs
