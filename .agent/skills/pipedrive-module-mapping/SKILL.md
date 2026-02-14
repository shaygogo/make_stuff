---
name: pipedrive-module-mapping
description: Use when referencing or updating the dictionary of Pipedrive v1 to v2 module replacements and generic API call substitutions.
---

# Pipedrive Module Mappings

This skill maintains the mapping rules for converting Legacy v1 modules to API v2 or generic `MakeAPICallV2` modules.

## 1. Direct v2 Equivalents
| V1 Module Name | V2 Module Name | Notes |
| :--- | :--- | :--- |
| `GetDeal` | `getDealV2` | |
| `UpdateDeal` | `updateDealV2` | **No `include_fields`** — only getDealV2 supports it |
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

## 2. Generic API Call Replacements (MakeAPICallV2)
Modules that do not have a direct V2 equivalent in Make.com are converted to `pipedrive:MakeAPICallV2` using the following routes:

- **Persons**:
  - `CreatePerson` → `POST /v2/persons`
  - `UpdatePerson` → `PATCH /v2/persons/{{id}}`
  - `GetPerson` → `GET /v2/persons/{{id}}`
  - `SearchPersons` → `GET /v2/persons/search` (**no direct v2 module exists**)
- **Notes**:
  - `CreateNote` → `POST /v2/notes`
  - `UpdateNote` → `PATCH /v2/notes/{{id}}`
  - `GetNote` → `GET /v2/notes/{{id}}`

## 3. Parameter Scoping Rules (CRITICAL)

### `include_fields` — Only for `getDealV2`
The `include_fields` parameter tells Pipedrive which custom fields to return. It is **ONLY valid for read operations** like `getDealV2`.

**NEVER add `include_fields` to:**
- `updateDealV2` — causes `400: Parameter 'include_fields' is not allowed`
- `searchDealsV2`
- `listDealsV2`
- Any write/create/delete module

**Implementation rule:**
```python
# Use exact module name match, NOT substring match
if new_module == 'pipedrive:getDealV2':  # ✅ Correct
    # Add include_fields to parameters, expect, and restore

if 'Deal' in new_module:  # ❌ WRONG — catches updateDealV2 too!
```

This applies to THREE places in `migrate_pipedrive.py`:
1. `module['parameters']['include_fields']` — the actual parameter
2. `new_restore_expect["include_fields"]` — the restore metadata
3. `new_expect.append(...)` — the expect schema entry

## 4. Learned Patterns

### Renaming Rules
- **Activity Deal ID**: When migrating `ListActivityDeals` to `listActivitiesV2`, the filter field `id` (which represented the Deal ID in V1) MUST be renamed to `deal_id` in the v2 mapper to maintain functionality.
- **Product Owner**: For `createProductV2` or usage of `/v2/products`, `user_id` MUST be renamed to `owner_id`.

### Item Search Migration
- **Pattern**: `http:MakeRequest` calls to `/v1/itemSearch` are generally searching for deals.
- **Conversion**: These should be migrated to `GET /v2/deals/search`.
- **Query Params**: `exact_match=true` (V1) must be converted to `match=exact` (V2).
- **Pagination**: Note that V2 search results are wrapped in a `data.items` array. The `start` parameter (offset) is replaced by cursor-based pagination.

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

| Field Type | V2 Mapper Format | V2 Expect Type | Unwrap? |
| :--- | :--- | :--- | :--- |
| `text` | `"hash": "value"` | Keep original | ✅ Yes |
| `number` | `"hash": 123` | Keep original | ✅ Yes |
| `date` | `"hash": "2026-01-15"` | Keep original | ✅ Yes |
| `enum` | `"hash": 5877` (ID) | Keep original | ✅ Yes |
| `set` | `"hash": "1,2,3"` | Keep original | ✅ Yes |
| `time` | `"hash": {"value": "16:15"}` | `collection` | ❌ No |
| `monetary` | `"hash": {"value": 100, "currency": "USD"}` | `collection` | ❌ No |
| `address` | `"hash": {"value": "123 Main", ...}` | `collection` | ❌ No |

**Sending a plain string for a `time` field causes:** `400: Time custom field value expected 'object'`
**Sending an object for a `text` field causes:** `400: Invalid collection`

## 5. Case Sensitivity Warning (CRITICAL)
Make.com is case-sensitive for module identifiers. 
- **Correct**: `pipedrive:GetPersonV2` (Capital **G**)
- **Incorrect**: `pipedrive:getPersonV2` (Results in "Module Not Found")
*Note: Interestingly, `getDealV2` and `updateDealV2` start with lowercase `g`, but `GetPersonV2` and `MakeAPICallV2` use uppercase.*

### Legacy Module Case Sensitivity
The migration script is designed to handle both TitleCase (e.g., `GetDeal`) and camelCase (e.g., `getDeal`) versions of v1 Pipedrive modules, as both are found in older blueprints.


## 6. HTTP Module Conversion
Native HTTP modules (`http:MakeRequest`, `http:ActionSendData`) targeting `pipedrive.com` must be converted:
- **Target**: `pipedrive:MakeAPICallV2`
- **Path Transformation**: Remove protocol/domain and force `/v2/` prefix (e.g., `https://api.pipedrive.com/v1/deals` → `/v2/deals`).
- **Token Striping**: Search for and remove `api_token` from both the URL string and the query string parameters.
- **Method Case**: Ensure the `method` is UPPERCASE.
