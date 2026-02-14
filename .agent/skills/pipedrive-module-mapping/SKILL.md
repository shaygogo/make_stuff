---
name: pipedrive-module-mapping
description: Use when referencing or updating the dictionary of Pipedrive v1 to v2 module replacements and generic API call substitutions.
---

# Pipedrive Module Mappings

This skill maintains the mapping rules for converting Legacy v1 modules to API v2 or generic `MakeAPICallV2` modules.

## 1. Direct v2 Equivalents (PIPEDRIVE_MODULE_UPGRADES)
| V1 Module Name | V2 Module Name | Notes |
| :--- | :--- | :--- |
| `GetDeal` | `getDealV2` | |
| `UpdateDeal` | `updateDealV2` | **No `include_fields`** — only get modules support it |
| `CreateActivity` | `createActivityV2` | |
| `UpdateActivity` | `updateActivityV2` | |
| `GetActivity` | `getActivityV2` | |
| `SearchDeals` | `searchDealsV2` | |
| `ListDeals` | `listDealsV2` | |
| `SearchOrganizations` | `searchOrganizationsV2` | |
| `GetOrganization` | `getOrganizationV2` | |
| `CreateProduct` | `createProductV2` | |
| `UpdateProduct` | `updateProductV2` | |
| `SearchProducts` | `searchProductsV2` | |
| `GetProduct` | `getProductV2` | |
| `DeleteProduct` | `deleteProductV2` | |
| `DeleteDeal` | `deleteDealV2` | |
| `DeletePerson` | `deletePersonV2` | |
| `DeleteOrganization` | `deleteOrganizationV2` | |
| `DeleteActivity` | `deleteActivityV2` | |
| `DeleteNote` | `deleteNoteV2` | |
| `ListActivityDeals` | `listActivitiesV2` | Rename `id` → `deal_id` |
| `UploadFile` | `uploadFileV2` | |
| `DeleteFile` | `deleteFileV2` | |
| `DownloadFile` | `downloadFileV2` | |
| `MakeAPICall` | `MakeAPICallV2` | |
| `GetPerson` / `getPerson` | `GetPersonV2` | **Direct upgrade** (not generic API) |

### GetPerson Special Handling (CRITICAL)
`GetPerson` and `getPerson` are mapped to **native `GetPersonV2`** module, NOT to a generic `MakeAPICallV2`. This ensures:
- Custom field handling works correctly
- The module appears in the V2_GET_MODULES set for `include_fields`/`custom_fields` processing
- Interface metadata is preserved for companion field detection

## 2. Generic API Call Replacements (MakeAPICallV2)
Modules that do not have a direct V2 equivalent in Make.com are converted to `pipedrive:MakeAPICallV2` using the following routes:

- **Persons**:
  - `CreatePerson` → `POST /v2/persons`
  - `UpdatePerson` → `PATCH /v2/persons/{{id}}`
  - `SearchPersons` → `GET /v2/persons/search` (**no direct v2 module exists**)
- **Notes**:
  - `CreateNote` → `POST /v2/notes`
  - `UpdateNote` → `PATCH /v2/notes/{{id}}`
  - `GetNote` → `GET /v2/notes/{{id}}`

## 3. V2 Get Modules Set (for custom field processing)
These modules are treated as "V2 get modules" that support `include_fields`, `custom_fields`, and need custom field reference rewriting:

```python
V2_GET_MODULES = {
    'pipedrive:getDealV2',
    'pipedrive:getProductV2',
    'pipedrive:getPersonV2',
    'pipedrive:GetPersonV2',      # Capital G (Make.com casing for auto-injected)
    'pipedrive:getOrganizationV2',
    'pipedrive:getActivityV2',
}
```

**CRITICAL**: `GetPersonV2` uses **Capital G** — both `getPersonV2` and `GetPersonV2` must be in the set because auto-injected person modules use `GetPersonV2` while direct upgrades may use either.

## 4. Parameter Scoping Rules (CRITICAL)

### `include_fields` — Only for V2 Get Modules
The `include_fields` parameter tells Pipedrive which fields to return. It is **ONLY valid for read operations**.

**NEVER add `include_fields` to:**
- `updateDealV2` — causes `400: Parameter 'include_fields' is not allowed`
- `searchDealsV2`
- `listDealsV2`
- Any write/create/delete module

**Implementation rule:**
```python
# Check against the full v2_get_modules tuple
v2_get_modules = (
    'pipedrive:getDealV2', 'pipedrive:getProductV2',
    'pipedrive:getPersonV2', 'pipedrive:GetPersonV2',
    'pipedrive:getOrganizationV2', 'pipedrive:getActivityV2',
)
if new_module in v2_get_modules:  # ✅ Correct
    # Add include_fields and custom_fields to parameters, expect, and restore

if 'Deal' in new_module:  # ❌ WRONG — catches updateDealV2 too!
```

This applies to THREE places in `migrate_pipedrive.py`:
1. `module['parameters']['include_fields']` — the actual parameter
2. `new_restore_expect["include_fields"]` — the restore metadata
3. `new_expect.append(...)` — the expect schema entry

## 5. Learned Patterns

### Renaming Rules

#### Module-Level Renames (in mapper during migration)
- **Activity Deal ID**: When migrating `ListActivityDeals` to `listActivitiesV2`, the filter field `id` MUST be renamed to `deal_id`.
- **Product Owner**: For `createProductV2` or `/v2/products`, `user_id` MUST be renamed to `owner_id`.

#### Entity Field Reference Renames (post-processing on serialized JSON)
All entities automatically rewrite V1→V2 field name changes via `ENTITY_RENAME_CONFIGS`. See `pipedrive-blueprint-transform` skill Section 6 for the full table. Key renames include:
- **All entities**: `active_flag`→`is_deleted`, `label`→`label_ids`
- **Deals/Activities**: `user_id`→`owner_id`
- **Persons**: `phone`→`phones`, `email`→`emails`
- **Activities**: `busy_flag`→`busy`, `created_by_user_id`→`creator_user_id`
- **Products**: `selectable`→`is_linkable`
- **Pipelines**: `selected`→`is_selected`, `deal_probability`→`is_deal_probability_enabled`
- **Stages**: `rotten_flag`→`is_deal_rot_enabled`, `rotten_days`→`days_to_rotten`

#### Structural Mapper Fixes (applied during module upgrade)
- **`visible_to`**: String `"3"` → integer `3` (all entities)
- **`start`**: Removed (V2 uses cursor-based pagination)
- **`sort`**: Split into `sort_by` + `sort_direction`

### Item Search Migration
- **Pattern**: `http:MakeRequest` calls to `/v1/itemSearch` are generally searching for deals.
- **Conversion**: These should be migrated to `GET /v2/deals/search`.
- **Query Params**: `exact_match=true` (V1) must be converted to `match=exact` (V2).
- **Pagination**: Note that V2 search results are wrapped in a `data.items` array. The `start` parameter (offset) is replaced by cursor-based pagination.

### Remaining Known Gaps (NOT automated)
These V2 changes are documented but not automated due to risk/complexity:
- **Multiple-option fields**: Comma-separated string `"123,456"` → integer array `[123,456]`. Requires knowing field type at migration time.
- **Date/time range `_until` companion**: New subfield for date range and time range custom fields.
- **Fields API renames**: `key`→`field_code`, `name`→`field_name`, `edit_flag`→`is_custom_field`. Only matters if scenarios use field management modules.

### GET-based Generic Replacements (CRITICAL)
- When a module is converted to `MakeAPICallV2` with method `GET`, the **original mapper parameters must be preserved as query string (`qs`)** items.
- `MakeAPICallV2` expects `qs` as an array of `{"key": "param_name", "value": "val"}` objects. (**NOT** `"name"` — must be `"key"`!)
- Without this, search terms, filters, and limits are silently lost.
- **Example**: `searchPersons` with `term: {{3.value}}, fields: ["phone"], exact_match: true` must become:
  ```json
  {"qs": [{"key": "term", "value": "{{3.value}}"}, {"key": "fields", "value": "phone"}, {"key": "match", "value": "exact"}]}
  ```

### Custom Field Types in V2 (CRITICAL)
Understanding which field types require object wrapping vs plain values is essential:

| Field Type | V2 Mapper Format (WRITE) | V2 Output Format (READ) | Unwrap on write? |
| :--- | :--- | :--- | :--- |
| `text` | `"hash": "value"` | `"value"` (string) | ✅ Yes |
| `number` | `"hash": 123` | `123` (number) | ✅ Yes |
| `date` | `"hash": "2026-01-15"` | `"2026-01-15"` (string) | ✅ Yes |
| `enum` | `"hash": 5877` (ID) | `5877` (integer) | ✅ Yes |
| `set` | `"hash": "1,2,3"` | `"1,2,3"` (string) | ✅ Yes |
| `time` | `"hash": {"value": "16:15"}` | `{"value": "15:15:00", "timezone_id": 240, ...}` | ❌ No |
| `monetary` | `"hash": {"value": 100, "currency": "USD"}` | `{"value": 180, "currency": "ILS"}` | ❌ No |
| `address` | `"hash": {"value": "123 Main", ...}` | `{"value": "addr text", "locality": "City", ...}` | ❌ No |

**Sending a plain string for a `time` field causes:** `400: Time custom field value expected 'object'`
**Sending an object for a `text` field causes:** `400: Invalid collection`

### V2 READ output — Object fields need `.value` (CRITICAL)
When READING object-type fields, V2 returns JSON objects. Downstream references must use `.value`:
- `{{MOD.custom_fields.HASH}}` for monetary → gives `{"value": 180, "currency": "ILS"}` ❌
- `{{MOD.custom_fields.HASH.value}}` for monetary → gives `180` ✅
- `{{MOD.custom_fields.HASH.currency}}` for monetary → gives `"ILS"` ✅

Same applies to time (`.value`, `.timezone_id`) and address (`.value`, `.locality`, `.formatted_address`, etc.)

## 6. Case Sensitivity Warning (CRITICAL)
Make.com is case-sensitive for module identifiers. 
- **Correct**: `pipedrive:GetPersonV2` (Capital **G**)
- **Incorrect**: `pipedrive:getPersonV2` (Results in "Module Not Found")
*Note: Interestingly, `getDealV2` and `updateDealV2` start with lowercase `g`, but `GetPersonV2` and `MakeAPICallV2` use uppercase.*

### Legacy Module Case Sensitivity
The migration script is designed to handle both TitleCase (e.g., `GetDeal`) and camelCase (e.g., `getDeal`) versions of v1 Pipedrive modules, as both are found in older blueprints.


## 7. HTTP Module Conversion
Native HTTP modules (`http:MakeRequest`, `http:ActionSendData`) targeting `pipedrive.com` must be converted:
- **Target**: `pipedrive:MakeAPICallV2`
- **Path Transformation**: Remove protocol/domain and force `/v2/` prefix (e.g., `https://api.pipedrive.com/v1/deals` → `/v2/deals`).
- **Token Striping**: Search for and remove `api_token` from both the URL string and the query string parameters.
- **Method Case**: Ensure the `method` is UPPERCASE.

## 8. Fields API — `field_code` (CRITICAL)
The Pipedrive V2 fields API (`/v2/dealFields`, etc.) returns field definitions with a `field_code` property that corresponds to the 40-char hash used in custom field names. When building lookup formulas:

- **Use `field_code`** to match field definitions by hash
- **NOT `key`** or `field_key` — these are different properties in the V2 API
- Example: `map(HELPER.body.data; "options"; "field_code"; "HASH")`
