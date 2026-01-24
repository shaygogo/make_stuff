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
| `UpdateDeal` | `updateDealV2` | |
| `CreateActivity` | `createActivityV2` | |
| `UpdateActivity` | `updateActivityV2` | |
| `GetActivity` | `getActivityV2` | |
| `SearchDeals` | `searchDealsV2` | |
| `ListDeals` | `listDealsV2` | |
| `SearchOrganizations` | `searchOrganizationsV2` | |
| `GetOrganization` | `getOrganizationV2` | |
| `CreateProduct` | `createProductV2` | |
| `SearchProducts` | `searchProductsV2` | |
| `GetProduct` | `getProductV2` | |
| `ListActivityDeals` | `listActivitiesV2` | Rename `id` → `deal_id` |
| `searchPersons` | `searchPersonsV2` | |
| `listDealsForPerson` | `listDealsForPersonV2` | |
| `ListProductsInDeal` | `listProductsInDealV2` | |
| `UploadFile` | `uploadFileV2` | |
| `MakeAPICall` | `MakeAPICallV2` | |

## 2. Generic API Call Replacements (MakeAPICallV2)
Modules that do not have a direct V2 equivalent in Make.com are converted to `pipedrive:MakeAPICallV2` using the following routes:

- **Persons**:
  - `CreatePerson` → `POST /v2/persons`
  - `UpdatePerson` → `PATCH /v2/persons/{{id}}`
  - `GetPerson` → `GET /v2/persons/{{id}}`
- **Notes**:
  - `CreateNote` → `POST /v2/notes`
  - `UpdateNote` → `PATCH /v2/notes/{{id}}`
  - `GetNote` → `GET /v2/notes/{{id}}`

## 4. Learned Patterns

### Renaming Rules
- **Activity Deal ID**: When migrating `ListActivityDeals` to `listActivitiesV2`, the filter field `id` (which represented the Deal ID in V1) MUST be renamed to `deal_id` in the v2 mapper to maintain functionality.

### Item Search Migration
- **Pattern**: `http:MakeRequest` calls to `/v1/itemSearch` are generally searching for deals.
- **Conversion**: These should be migrated to `GET /v2/deals/search`.
- **Query Params**: Ensure `exact_match=true` is used if the original search was intended to find a specific record (e.g., by custom field hash).
- **Pagination**: Note that V2 search results are wrapped in a `data.items` array, whereas V1 results might have had a different structure.

