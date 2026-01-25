import json
import os
import sys
import argparse
import urllib.request
import re

# --- Configuration ---
INPUT_FOLDER = './scenarios'
OUTPUT_SUFFIX = '_v2_MIGRATED.json'

# --- Make API Configuration (for CLI mode only) ---
# Note: The web interface doesn't use these credentials
TOKEN = os.getenv('MAKE_API_TOKEN', '')  # Only needed for --id CLI mode
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE_URL = "https://eu1.make.com/api/v2"

# Pipedrive API v2 requires OAuth connections (not API Key)
# Default connection ID - can be overridden when calling migrate_blueprint()
PIPEDRIVE_OAUTH_CONN_ID = int(os.getenv('PIPEDRIVE_OAUTH_CONN_ID', '4683394'))  # Set via environment variable
PIPEDRIVE_OAUTH_CONN_LABEL = os.getenv('PIPEDRIVE_OAUTH_CONN_LABEL', 'Pipedrive OAuth Connection')

# Module mapping: old_module_name -> new_module_name
PIPEDRIVE_MODULE_UPGRADES = {
    # Core / Most Common
    'pipedrive:GetDeal': 'pipedrive:getDealV2',
    'pipedrive:getDeal': 'pipedrive:getDealV2',
    'pipedrive:UpdateDeal': 'pipedrive:updateDealV2',
    'pipedrive:updateDeal': 'pipedrive:updateDealV2',
    'pipedrive:CreateActivity': 'pipedrive:createActivityV2',
    'pipedrive:createActivity': 'pipedrive:createActivityV2',
    'pipedrive:SearchDeals': 'pipedrive:searchDealsV2',
    'pipedrive:searchDeals': 'pipedrive:searchDealsV2',
    'pipedrive:ListDeals': 'pipedrive:listDealsV2',
    'pipedrive:listDeals': 'pipedrive:listDealsV2',
    'pipedrive:SearchOrganizations': 'pipedrive:searchOrganizationsV2',
    'pipedrive:searchOrganizations': 'pipedrive:searchOrganizationsV2',
    'pipedrive:SearchOrganizations': 'pipedrive:searchOrganizationsV2',
    'pipedrive:searchOrganizations': 'pipedrive:searchOrganizationsV2',

    # Specific names from blueprint
    'pipedrive:DeleteDeal': 'pipedrive:DeleteDeal',
    'pipedrive:AddProductToDeal': 'pipedrive:AddProductToDeal',
    'pipedrive:ListDealFiles': 'pipedrive:ListDealFiles',
    'pipedrive:ListDealsForProduct': 'pipedrive:listDealsForProduct',
    'pipedrive:ListDealFields': 'pipedrive:listDealFields',
    'pipedrive:GetADealField': 'pipedrive:getADealField',
    'pipedrive:GetDealsSummary': 'pipedrive:getDealsSummary',
    'pipedrive:CreateADealField': 'pipedrive:createADealField',
    'pipedrive:CreateProduct': 'pipedrive:createProductV2',
    'pipedrive:SearchProducts': 'pipedrive:searchProductsV2',
    'pipedrive:GetProduct': 'pipedrive:getProductV2',
    'pipedrive:MakeAPICall': 'pipedrive:MakeAPICallV2',

    # Inferred / Others
    'pipedrive:UpdateActivity': 'pipedrive:updateActivityV2',
    'pipedrive:ListActivityDeals': 'pipedrive:listActivitiesV2',
    'pipedrive:ListLeadLabels': 'pipedrive:listLeadLabelsV2',
    'pipedrive:ListProductsInDeal': 'pipedrive:listProductsInDealV2',
    'pipedrive:GetOrganization': 'pipedrive:getOrganizationV2',
    'pipedrive:GetActivity': 'pipedrive:getActivityV2',
    'pipedrive:UploadFile': 'pipedrive:uploadFileV2',
    'pipedrive:listDealsForPerson': 'pipedrive:listDealsForPersonV2',
    'pipedrive:searchPersons': 'pipedrive:searchPersonsV2'
}

# Modules that don't have a direct v2 equivalent and must use MakeAPICallV2
PIPEDRIVE_GENERIC_REPLACEMENTS = {
    'pipedrive:CreatePerson': {'url': '/v2/persons', 'method': 'POST'},
    'pipedrive:createPerson': {'url': '/v2/persons', 'method': 'POST'},
    'pipedrive:UpdatePerson': {'url': '/v2/persons/{{id}}', 'method': 'PATCH'},
    'pipedrive:updatePerson': {'url': '/v2/persons/{{id}}', 'method': 'PATCH'},
    'pipedrive:GetPerson': {'url': '/v2/persons/{{id}}', 'method': 'GET'},
    'pipedrive:getPerson': {'url': '/v2/persons/{{id}}', 'method': 'GET'},
    'pipedrive:CreateNote': {'url': '/v2/notes', 'method': 'POST'},
    'pipedrive:createNote': {'url': '/v2/notes', 'method': 'POST'},
    'pipedrive:UpdateNote': {'url': '/v2/notes/{{id}}', 'method': 'PATCH'},
    'pipedrive:updateNote': {'url': '/v2/notes/{{id}}', 'method': 'PATCH'},
    'pipedrive:GetNote': {'url': '/v2/notes/{{id}}', 'method': 'GET'},
    'pipedrive:getNote': {'url': '/v2/notes/{{id}}', 'method': 'GET'},
}

# V2 Breaking Change: GetDeal no longer returns embedded person details
# These patterns need to be detected and a GetPersonV2 module injected
# Maps v1 person_id fields to v2 GetPersonV2 output fields
PERSON_FIELD_MAPPINGS = {
    'person_id.name': 'name',
    'person_id.first_name': 'first_name',
    'person_id.last_name': 'last_name',
    'person_id.phone': 'phones',  # Note: array structure changed too
    'person_id.phone[]': 'phones[]',
    'person_id.phone[].value': 'phones[].value',
    'person_id.phone[].primary': 'phones[].primary',
    'person_id.email': 'emails',
    'person_id.email[]': 'emails[]',
    'person_id.email[].value': 'emails[].value',
    'person_id.email[].primary': 'emails[].primary',
    'person_id.value': 'id',  # The numeric ID
}

# Modules that return deal data with embedded person (in v1) - these need person injection
DEAL_MODULES_WITH_PERSON = [
    'pipedrive:GetDeal',
    'pipedrive:getDeal',
    'pipedrive:getDealV2',
    'pipedrive:UpdateDeal',
    'pipedrive:updateDeal',
    'pipedrive:updateDealV2',
    'pipedrive:SearchDeals',
    'pipedrive:searchDeals',
    'pipedrive:searchDealsV2',
    'pipedrive:ListDeals',
    'pipedrive:listDeals',
    'pipedrive:listDealsV2',
]

def is_custom_field(key):
    return len(key) == 40 and all(c in '0123456789abcdef' for c in key)

def find_max_module_id(flow):
    """Recursively find the maximum module ID in a flow."""
    max_id = 0
    for module in flow:
        if 'id' in module:
            max_id = max(max_id, module['id'])
        if 'routes' in module:
            for route in module['routes']:
                if 'flow' in route:
                    max_id = max(max_id, find_max_module_id(route['flow']))
        if 'onerror' in module:
            max_id = max(max_id, find_max_module_id(module['onerror']))
    return max_id

def find_person_field_references(blueprint_json_str, deal_module_id):
    """
    Scan the entire blueprint JSON string for references to person_id embedded fields
    from a specific deal module (e.g., {{2.person_id.phone[].value}}).
    
    Returns a list of patterns found.
    """
    patterns_found = []
    
    # Look for patterns like {{deal_module_id.person_id.X}}
    # The regex needs to catch various forms:
    # {{2.person_id.name}}, {{2.person_id.phone[].value}}, {{2.person_id.email[]}}
    import re
    
    # Pattern to match {{id.person_id.something}}
    pattern = rf'\{{\{{({deal_module_id})\.person_id\.([a-zA-Z_\[\]\.]+)\}}\}}'
    matches = re.findall(pattern, blueprint_json_str)
    
    for match in matches:
        module_id, field_path = match
        patterns_found.append({
            'full_match': f'{{{{{module_id}.person_id.{field_path}}}}}',
            'module_id': int(module_id),
            'field_path': f'person_id.{field_path}'
        })
    
    return patterns_found

def create_get_person_module(new_module_id, deal_module_id, connection_id, x_position):
    """
    Create a GetPersonV2 module that fetches person details using the person_id from a deal.
    
    Args:
        new_module_id: The ID to assign to the new module
        deal_module_id: The ID of the deal module to get person_id from
        connection_id: The Pipedrive OAuth connection ID
        x_position: The x position for the module in the designer
    
    Returns:
        A complete module dict ready to insert into the flow
    """
    return {
        "id": new_module_id,
        "module": "pipedrive:GetPersonV2",
        "version": 2,

        "parameters": {
            "__IMTCONN__": connection_id
        },
        "mapper": {
            "id": f"{{{{{deal_module_id}.person_id}}}}"
        },
        "metadata": {
            "designer": {
                "x": x_position,
                "y": 0,
                "name": "Get Person (Auto-injected for v2 migration)"
            },
            "restore": {
                "expect": {
                    "include_fields": {
                        "mode": "chose"
                    }
                },
                "parameters": {
                    "__IMTCONN__": {
                        "data": {
                            "scoped": "true",
                            "connection": "pipedrive-auth"
                        },
                        "label": PIPEDRIVE_OAUTH_CONN_LABEL
                    }
                }
            },
            "parameters": [
                {
                    "name": "__IMTCONN__",
                    "type": "account:pipedrive-auth",
                    "label": "Connection",
                    "required": True
                }
            ],
            "expect": [
                {
                    "name": "id",
                    "type": "uinteger",
                    "label": "Person ID",
                    "required": True
                },
                {
                    "name": "include_fields",
                    "type": "select",
                    "label": "Include additional fields",
                    "multiple": True,
                    "validate": {
                        "enum": [
                            "next_activity_id",
                            "last_activity_id",
                            "open_deals_count",
                            "related_open_deals_count",
                            "closed_deals_count",
                            "email_messages_count",
                            "activities_count",
                            "done_activities_count",
                            "undone_activities_count",
                            "files_count",
                            "notes_count",
                            "followers_count"
                        ]
                    }
                }
            ],
            "interface": [
                {"name": "id", "type": "number", "label": "ID"},
                {"name": "name", "type": "text", "label": "Name"},
                {"name": "first_name", "type": "text", "label": "First Name"},
                {"name": "last_name", "type": "text", "label": "Last Name"},
                {"name": "add_time", "type": "date", "label": "Add Time"},
                {"name": "update_time", "type": "date", "label": "Update Time"},
                {"name": "visible_to", "type": "number", "label": "Visible To"},
                {"name": "owner_id", "type": "number", "label": "Owner ID"},
                {"name": "label_ids", "type": "array", "label": "Label IDs"},
                {"name": "org_id", "type": "text", "label": "Org ID"},
                {"name": "is_deleted", "type": "boolean", "label": "Is Deleted"},
                {
                    "name": "phones",
                    "spec": {
                        "spec": [
                            {"name": "label", "type": "text", "label": "Label"},
                            {"name": "value", "type": "text", "label": "Value"},
                            {"name": "primary", "type": "boolean", "label": "Primary"}
                        ],
                        "type": "collection"
                    },
                    "type": "array",
                    "label": "Phones"
                },
                {
                    "name": "emails",
                    "spec": {
                        "spec": [
                            {"name": "label", "type": "text", "label": "Label"},
                            {"name": "value", "type": "text", "label": "Value"},
                            {"name": "primary", "type": "boolean", "label": "Primary"}
                        ],
                        "type": "collection"
                    },
                    "type": "array",
                    "label": "Emails"
                }
            ]
        }
    }

def rewrite_person_references(blueprint_json_str, deal_module_id, person_module_id):
    """
    Rewrite all references from deal's embedded person fields to the new GetPersonV2 module.
    
    Transforms:
        {{deal_id.person_id.name}} -> {{person_id.name}}
        {{deal_id.person_id.phone[].value}} -> {{person_id.phones[].value}}
        {{deal_id.person_id.email[].value}} -> {{person_id.emails[].value}}
    
    Args:
        blueprint_json_str: The blueprint as a JSON string
        deal_module_id: The original deal module ID
        person_module_id: The new GetPersonV2 module ID
    
    Returns:
        The modified JSON string with rewritten references
    """
    import re
    
    # Define the transformation rules
    transformations = [
        # phone -> phones (v1 uses phone, v2 uses phones)
        (rf'\{{\{{{deal_module_id}\.person_id\.phone(\[\])?\.value\}}\}}',
         f'{{{{{person_module_id}.phones[].value}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.phone(\[\])?\.primary\}}\}}',
         f'{{{{{person_module_id}.phones[].primary}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.phone(\[\])?\}}\}}',
         f'{{{{{person_module_id}.phones[]}}}}'),
         
        # email -> emails (v1 uses email, v2 uses emails)
        (rf'\{{\{{{deal_module_id}\.person_id\.email(\[\])?\.value\}}\}}',
         f'{{{{{person_module_id}.emails[].value}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.email(\[\])?\.primary\}}\}}',
         f'{{{{{person_module_id}.emails[].primary}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.email(\[\])?\}}\}}',
         f'{{{{{person_module_id}.emails[]}}}}'),
        
        # Direct field mappings (name, first_name, last_name, etc.)
        (rf'\{{\{{{deal_module_id}\.person_id\.name\}}\}}',
         f'{{{{{person_module_id}.name}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.first_name\}}\}}',
         f'{{{{{person_module_id}.first_name}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.last_name\}}\}}',
         f'{{{{{person_module_id}.last_name}}}}'),
        (rf'\{{\{{{deal_module_id}\.person_id\.value\}}\}}',
         f'{{{{{person_module_id}.id}}}}'),
        
        # Catch-all for any remaining person_id.X patterns
        (rf'\{{\{{{deal_module_id}\.person_id\.([a-zA-Z_]+)\}}\}}',
         lambda m: f'{{{{{person_module_id}.{m.group(1)}}}}}'),
    ]
    
    result = blueprint_json_str
    for pattern, replacement in transformations:
        if callable(replacement):
            result = re.sub(pattern, replacement, result)
        else:
            result = re.sub(pattern, replacement, result)
    
    return result


def check_http_pipedrive_modules(modules, filename, results=None):
    """
    Scans modules for HTTP calls targeting Pipedrive API and checks if they use v2 endpoints.
    Returns a list of findings with module info and API version status.
    """
    if results is None:
        results = []

    
    for module in modules:
        # Recurse into routers
        if 'routes' in module:
            for route in module['routes']:
                if 'flow' in route:
                    check_http_pipedrive_modules(route['flow'], filename, results)
        
        # Recurse into error handlers
        if 'onerror' in module:
            check_http_pipedrive_modules(module['onerror'], filename, results)
        
        module_type = module.get('module', '')
        
        # Check HTTP modules
        if module_type in ['http:MakeRequest', 'http:ActionSendData']:
            # URL can be in parameters or mapper
            url = module.get('parameters', {}).get('url', '') or module.get('mapper', {}).get('url', '')
            
            # Check if it targets Pipedrive
            if 'pipedrive.com' in url.lower():
                uses_v2 = '/v2/' in url or '/api/v2/' in url
                results.append({
                    'module_id': module.get('id'),
                    'module_type': module_type,
                    'url': url,
                    'uses_v2': uses_v2,
                    'filename': filename
                })
        
        # Check pipedrive:MakeRequest / pipedrive:MakeAPICall (legacy)
        elif module_type in ['pipedrive:MakeRequest', 'pipedrive:MakeAPICall']:
            url = module.get('parameters', {}).get('url', '') or module.get('mapper', {}).get('url', '')
            uses_v2 = '/v2/' in url
            results.append({
                'module_id': module.get('id'),
                'module_type': module_type,
                'url': url,
                'uses_v2': uses_v2,
                'filename': filename
            })
    
    return results

def print_http_check_report(results):
    """Prints a formatted report of HTTP Pipedrive API findings."""
    if not results:
        print("\n[OK] No HTTP modules calling Pipedrive API found.")
        return
    
    print("\n" + "=" * 60)
    print("HTTP PIPEDRIVE API CHECK REPORT")
    print("=" * 60)
    
    v1_count = 0
    v2_count = 0
    
    for r in results:
        status = "[OK] v2" if r['uses_v2'] else "[!!] v1 - NEEDS MIGRATION"
        if r['uses_v2']:
            v2_count += 1
        else:
            v1_count += 1
        
        print(f"\n[{r['filename']}] Module {r['module_id']} ({r['module_type']})")
        print(f"  URL: {r['url'][:80]}{'...' if len(r['url']) > 80 else ''}")
        print(f"  Status: {status}")
    
    print("\n" + "-" * 60)
    print(f"SUMMARY: {len(results)} HTTP->Pipedrive calls found")
    print(f"  [OK] Using v2: {v2_count}")
    print(f"  [!!] Using v1 (needs migration): {v1_count}")
    print("=" * 60)

def fetch_blueprint(scenario_id):
    """Fetch blueprint from Make.com API (CLI mode only)"""
    if not TOKEN:
        print("[ERROR] MAKE_API_TOKEN environment variable not set.")
        print("Set it with: $env:MAKE_API_TOKEN='your-token-here'")
        return None
    
    url = f"{BASE_URL}/scenarios/{scenario_id}/blueprint"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Token {TOKEN}")
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[ERROR] Could not fetch scenario {scenario_id}: {e}")
        return None

def upgrade_pipedrive_connection(module, filename, override_connection_id=None):
    """
    Upgrades a Pipedrive module's connection from API Key to OAuth.
    Handles the new v2 nested structure for custom fields and collections.
    
    Args:
        module: Module dict to upgrade
        filename: Source filename for logging
        override_connection_id: If provided, use this instead of PIPEDRIVE_OAUTH_CONN_ID
    """
    module_id = module['id']
    old_module = module.get('module', '')
    
    # Allow override of connection ID
    target_connection_id = override_connection_id if override_connection_id is not None else PIPEDRIVE_OAUTH_CONN_ID
    
    new_module = PIPEDRIVE_MODULE_UPGRADES.get(old_module)
    generic_config = PIPEDRIVE_GENERIC_REPLACEMENTS.get(old_module)
    
    if not new_module and not generic_config:
        return False
    
    if generic_config:
        new_module = 'pipedrive:MakeAPICallV2'
    
    conn_id = module.get('parameters', {}).get('__IMTCONN__')
    if not conn_id:
        print(f"[WARNING] [{filename}] Module {module_id} ({old_module}): No connection ID found! Skipping.")
        return False
    
    print(f"[{filename}] Module {module_id}: {old_module} -> {new_module}")
    
    # 1. Basic Upgrades
    module['module'] = new_module
    module['version'] = 2
    
    old_metadata = module.get('metadata', {})
    old_expect = old_metadata.get('expect', [])
    
    # Identify field types from old expect to know which need wrapping
    field_types = {f['name']: f.get('type') for f in old_expect if 'name' in f}
    
    # 2. Transform Mapper
    old_mapper = module.get('mapper', {})
    
    if generic_config:
        # Special transformation to MakeAPICallV2
        url = generic_config['url']
        method = generic_config['method']
        
        # Extract ID and inject into URL if needed
        obj_id = old_mapper.get('id')
        if obj_id:
            url = url.replace('{{id}}', str(obj_id))
            # Remote id from body if it was used in URL
            if method in ['PATCH', 'GET']:
                old_mapper.pop('id', None)

        new_mapper = {
            "url": url,
            "method": method
        }
        
        if method in ['POST', 'PATCH']:
            # Transform the remaining fields for the body
            body = {}
            custom_fields = {}
            
            # Merge parameters and mapper, prioritizing mapper
            # Skip technical parameters
            TECHNICAL_PARAMS = ['__IMTCONN__', '__IMTENV__', 'handleErrors', 'useNewZLibDeCompress']
            merged_data = module.get('parameters', {}).copy()
            for tp in TECHNICAL_PARAMS:
                merged_data.pop(tp, None)
            merged_data.update(old_mapper)
            
            for key, value in merged_data.items():
                if is_custom_field(key):
                     custom_fields[key] = {"value": value}
                else:
                     body[key] = value
            
            if custom_fields:
                body["custom_fields"] = custom_fields
            
            new_mapper["body"] = json.dumps(body, indent=4, ensure_ascii=False)
        
        module['mapper'] = new_mapper
    else:
        # Standard Module Transformation
        new_mapper = {}
        custom_fields_mapper = {}
        
        for key, value in old_mapper.items():
            if is_custom_field(key):
                # v2 custom fields need wrapping
                custom_fields_mapper[key] = {"value": value}
            else:
                # Special handling for ListActivityDeals: rename 'id' to 'deal_id'
                if old_module == 'pipedrive:ListActivityDeals' and key == 'id':
                    new_mapper['deal_id'] = value
                else:
                    new_mapper[key] = value

        if custom_fields_mapper:
            new_mapper["custom_fields"] = custom_fields_mapper
            
        module['mapper'] = new_mapper

    # 3. Transform Metadata Restore
    new_restore_expect = {}
    custom_fields_restore = {}
    
    # We don't necessarily have a restore object in all cases, ensure safety
    old_restore = old_metadata.get('restore', {})
    old_restore_expect = old_restore.get('expect', {})
    
    for key, val in old_restore_expect.items():
        if is_custom_field(key):
            custom_fields_restore[key] = val
        else:
            new_restore_expect[key] = val
            
    if custom_fields_restore:
        new_restore_expect["custom_fields"] = {"nested": custom_fields_restore}
        
    if 'Deal' in new_module:
        new_restore_expect["include_fields"] = {"mode": "chose"}

    if 'metadata' not in module:
        module['metadata'] = {}

    module['metadata']['restore'] = {
        "parameters": {
            "__IMTCONN__": {
                "label": PIPEDRIVE_OAUTH_CONN_LABEL,
                "data": {
                    "scoped": "true",
                    "connection": "pipedrive-auth"
                }
            }
        },
        "expect": new_restore_expect
    }

    # 4. Transform Expect Array
    new_expect = []
    custom_fields_spec = []
    
    found_id = False
    found_include_fields = False
    
    for field in old_expect:
        name = field.get('name')
        if is_custom_field(name):
            # v2 usually makes these collections in the spec too
            f_copy = field.copy()
            f_copy['type'] = 'collection' # Most are collections in v2 spec
            f_copy['spec'] = [{"name": "value", "type": field.get('type', 'text'), "label": "Value"}]
            custom_fields_spec.append(f_copy)
        elif name == 'id' and 'Deal' in new_module:
            f_copy = field.copy()
            f_copy['type'] = 'integer'
            new_expect.append(f_copy)
            found_id = True
        elif name == 'include_fields':
            found_include_fields = True
            new_expect.append(field)
        else:
            new_expect.append(field)

    if custom_fields_spec:
        new_expect.append({
            "name": "custom_fields",
            "type": "collection",
            "label": "Custom Fields",
            "spec": custom_fields_spec
        })

    if 'Deal' in new_module:
        if not found_id:
            new_expect.insert(0, {"name": "id", "type": "integer", "label": "Deal ID", "required": True})
        if not found_include_fields:
            new_expect.append({"name": "include_fields", "type": "select", "label": "Include fields", "multiple": True})

    module['metadata']['expect'] = new_expect
    
    # 5. Parameters
    module['parameters'] = {
        "__IMTCONN__": target_connection_id
    }
    if 'custom_fields' in new_mapper and 'Deal' in new_module:
        module['parameters']['include_fields'] = list(new_mapper['custom_fields'].keys())
        
    return True

def process_modules(modules, filename, override_connection_id=None):
    """Recursively processes modules, including those inside routers."""
    modified = False
    migration_count = 0
    for module in modules:

        # Recurse into any nested routes (for Routers)
        if 'routes' in module:
            for route in module['routes']:
                if 'flow' in route:
                    nested_modified, nested_count = process_modules(route['flow'], filename, override_connection_id)
                    if nested_modified:
                        modified = True
                        migration_count += nested_count
        
        # Recurse into error handlers (onerror)
        if 'onerror' in module:
            nested_modified, nested_count = process_modules(module['onerror'], filename, override_connection_id)
            if nested_modified:
                modified = True
                migration_count += nested_count
        
        if module.get('module') in PIPEDRIVE_MODULE_UPGRADES or module.get('module') in PIPEDRIVE_GENERIC_REPLACEMENTS:
            if upgrade_pipedrive_connection(module, filename, override_connection_id):
                modified = True
                migration_count += 1

        # Handle generic HTTP calls to Pipedrive (both http:MakeRequest and pipedrive:MakeRequest)
        if module.get('module') in ['http:MakeRequest', 'http:ActionSendData', 'pipedrive:MakeRequest']:
            params = module.get('parameters', {})
            mapper = module.get('mapper', {})
            
            # URL can be in parameters or mapper
            url = params.get('url', '') or mapper.get('url', '')
            
            # Identify if it's Pipedrive (either the module itself is pipedrive, or the URL targets pipedrive)
            is_pd = False
            if isinstance(url, str):
                is_pd = 'pipedrive.com' in url.lower() or module.get('module') == 'pipedrive:MakeRequest'
            
            if is_pd:

                print(f"[{filename}] Module {module['id']}: Upgrading to pipedrive:MakeAPICallV2...")
                
                # Determine the path
                if 'pipedrive.com' in url:
                    # Extract path from full URL: remove protocol/domain
                    path = re.sub(r'https?://[^/]+', '', url)
                else:
                    path = url # Already a path/partial URL in pipedrive:MakeRequest
                
                # Normalize path: remove various prefixes that might exist
                path = re.sub(r'^/(v1|api/v1|api/v2)', '', path)
                
                # Strip api_token and item_types from the path string itself (if stayed in URL)
                path = re.sub(r'[?&](api_token|item_types)=[^&]+', '', path)
                
                # Special case for itemSearch (V1) -> deals/search (V2)
                if 'itemSearch' in path:
                    path = '/v2/deals/search'
                
                # Ensure it starts with /v2/
                if not path.startswith('/v2/'):
                    path = '/v2/' + path.lstrip('/')
                
                # Clean up Query String
                qs = mapper.get('qs') or params.get('qs', [])
                if isinstance(qs, list):
                    # Filter out V1 specific parameters
                    new_qs = [item for item in qs if isinstance(item, dict) and item.get('name') not in ['api_token', 'item_types']]
                else:
                    new_qs = []
                
                # Handle exact_match for search
                if 'deals/search' in path:
                    found_exact = False
                    for item in new_qs:
                        if isinstance(item, dict) and item.get('name') == 'exact_match':
                            item['value'] = 'true'
                            found_exact = True
                            break
                    if not found_exact:
                        new_qs.append({"name": "exact_match", "value": "true"})

                # Clean up Headers
                headers = mapper.get('headers') or params.get('headers', [])
                if isinstance(headers, list):
                    new_headers = [h for h in headers if isinstance(h, dict) and h.get('name', '').lower() not in ['authorization', 'api_token', 'api-token']]
                else:
                    new_headers = []


                # Update Module Identity
                module['module'] = 'pipedrive:MakeAPICallV2'
                module['version'] = 2
                
                # Set OAuth Connection
                target_connection_id = override_connection_id if override_connection_id is not None else PIPEDRIVE_OAUTH_CONN_ID
                module['parameters'] = {
                    "__IMTCONN__": target_connection_id
                }
                
                # Set Mapper (MakeAPICallV2 uses mapper for request details)
                # Pick values from mapper first if they exist (dynamic), then parameters (static)
                method = mapper.get('method') or params.get('method', 'GET')
                body = mapper.get('body') or params.get('body', '')
                
                # Ensure method is uppercase (required by Pipedrive v2)
                if isinstance(method, str):
                    method = method.upper()
                
                module['mapper'] = {
                    "url": path,
                    "method": method,
                    "headers": new_headers,
                    "qs": new_qs,
                    "body": body
                }

                
                # Inject Metadata for UI to render correctly
                module['metadata'] = {
                    "restore": {
                        "parameters": {
                            "__IMTCONN__": {
                                "label": PIPEDRIVE_OAUTH_CONN_LABEL,
                                "data": { "scoped": "true", "connection": "pipedrive-auth" }
                            }
                        },
                        "expect": {
                            "url": path,
                            "method": params.get('method', 'GET')
                        }
                    },
                    "expect": [
                        {"name": "url", "type": "text", "label": "URL", "required": True},
                        {"name": "method", "type": "select", "label": "Method", "required": True, "validate": {"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]}},
                        {"name": "headers", "type": "array", "label": "Headers", "spec": [
                            {"name": "name", "type": "text", "label": "Name"},
                            {"name": "value", "type": "text", "label": "Value"}
                        ]},
                        {"name": "qs", "type": "array", "label": "Query String", "spec": [
                            {"name": "name", "type": "text", "label": "Name"},
                            {"name": "value", "type": "text", "label": "Value"}
                        ]},
                        {"name": "body", "type": "text", "label": "Body"}
                    ]
                }
                modified = True
                migration_count += 1
                
    return modified, migration_count

def inject_get_person_modules(blueprint_data, filename, override_connection_id=None):
    """
    Detects Deal modules that have downstream person_id.X references and injects
    GetPersonV2 modules to handle the v2 breaking change.
    
    This function:
    1. Serializes the blueprint to JSON string to find all references
    2. Finds all Deal modules (GetDeal, UpdateDeal, etc.)
    3. For each Deal module, checks if person_id.X fields are used downstream
    4. If so, creates a GetPersonV2 module and inserts it after the Deal module
    5. Rewrites all person_id references to point to the new module
    6. Returns the modified blueprint
    
    Args:
        blueprint_data: The blueprint dict
        filename: For logging
        override_connection_id: Connection ID for the new modules
    
    Returns:
        tuple: (modified: bool, blueprint_data: dict, injection_count: int)
    """
    if 'flow' not in blueprint_data:
        return False, blueprint_data, 0
    
    # Serialize to find references
    blueprint_json = json.dumps(blueprint_data, ensure_ascii=False)
    
    # Find all Deal modules in the flow
    deal_modules = []
    
    def find_deal_modules_in_flow(flow, parent_flow=None, parent_index=None):
        """Recursively find all deal modules and their positions."""
        for idx, module in enumerate(flow):
            module_type = module.get('module', '')
            if module_type in DEAL_MODULES_WITH_PERSON:
                deal_modules.append({
                    'module': module,
                    'flow': flow,
                    'index': idx,
                    'id': module.get('id')
                })
            
            # Recurse into routers
            if 'routes' in module:
                for route in module['routes']:
                    if 'flow' in route:
                        find_deal_modules_in_flow(route['flow'])
            
            # Recurse into error handlers
            if 'onerror' in module:
                find_deal_modules_in_flow(module['onerror'])
    
    find_deal_modules_in_flow(blueprint_data['flow'])
    
    if not deal_modules:
        return False, blueprint_data, 0
    
    # Find max module ID for new modules
    max_id = find_max_module_id(blueprint_data['flow'])
    next_id = max_id + 1
    
    modified = False
    injection_count = 0
    injections_to_perform = []  # Collect all injections first, then apply
    
    # For each deal module, check if person fields are referenced
    for deal_info in deal_modules:
        deal_module = deal_info['module']
        deal_id = deal_info['id']
        
        # Check for person_id.X references in the blueprint
        references = find_person_field_references(blueprint_json, deal_id)
        
        if references:
            print(f"[{filename}] Module {deal_id} ({deal_module.get('module')}): Found {len(references)} person_id references")
            for ref in references[:3]:  # Show first 3
                print(f"    - {ref['full_match']}")
            if len(references) > 3:
                print(f"    ... and {len(references) - 3} more")
            
            # Determine connection ID (use the deal module's connection or override)
            conn_id = override_connection_id
            if not conn_id:
                conn_id = deal_module.get('parameters', {}).get('__IMTCONN__', PIPEDRIVE_OAUTH_CONN_ID)
            
            # Get the deal module's x position to place the person module after it
            designer = deal_module.get('metadata', {}).get('designer', {})
            deal_x = designer.get('x', 0)
            person_x = deal_x + 300  # Standard module spacing
            
            # Create the injection record
            injections_to_perform.append({
                'deal_info': deal_info,
                'deal_id': deal_id,
                'person_module_id': next_id,
                'connection_id': conn_id,
                'x_position': person_x
            })
            
            next_id += 1
    
    if not injections_to_perform:
        return False, blueprint_data, 0
    
    # Apply all reference rewrites first (on the JSON string)
    for injection in injections_to_perform:
        blueprint_json = rewrite_person_references(
            blueprint_json,
            injection['deal_id'],
            injection['person_module_id']
        )
        print(f"[{filename}] Rewrote person_id references: {{{{...{injection['deal_id']}.person_id.X}}}} -> {{{{...{injection['person_module_id']}.X}}}}")
    
    # Parse the modified JSON back to dict
    blueprint_data = json.loads(blueprint_json)
    
    # Now insert the new modules into the flow
    # We need to re-find the deal modules after JSON round-trip
    for injection in injections_to_perform:
        deal_id = injection['deal_id']
        
        # Find the deal module in the (potentially modified) flow
        def find_and_insert(flow):
            for idx, module in enumerate(flow):
                if module.get('id') == deal_id:
                    # Create the GetPersonV2 module
                    person_module = create_get_person_module(
                        injection['person_module_id'],
                        deal_id,
                        injection['connection_id'],
                        injection['x_position']
                    )
                    
                    # Insert after the deal module
                    flow.insert(idx + 1, person_module)
                    
                    # Shift x positions of all subsequent modules
                    for i in range(idx + 2, len(flow)):
                        if 'metadata' in flow[i] and 'designer' in flow[i]['metadata']:
                            flow[i]['metadata']['designer']['x'] = flow[i]['metadata']['designer'].get('x', 0) + 300
                    
                    return True
                
                # Recurse into routers
                if 'routes' in module:
                    for route in module['routes']:
                        if 'flow' in route:
                            if find_and_insert(route['flow']):
                                return True
                
                # Recurse into error handlers
                if 'onerror' in module:
                    if find_and_insert(module['onerror']):
                        return True
            
            return False
        
        if find_and_insert(blueprint_data['flow']):
            print(f"[{filename}] Injected GetPersonV2 module (ID: {injection['person_module_id']}) after Deal module {deal_id}")
            modified = True
            injection_count += 1
    
    return modified, blueprint_data, injection_count

def migrate_scenario_object(data, scenario_info, override_connection_id=None):
    modified = False
    migration_count = 0
    if 'flow' in data:
        modified, migration_count = process_modules(data['flow'], scenario_info, override_connection_id)
    return modified, data, migration_count

def migrate_blueprint(blueprint_data, connection_id=None):
    """
    Programmatic interface for migrating a blueprint.
    
    Args:
        blueprint_data: The blueprint JSON object (dict)
        connection_id: Optional connection ID to use. If None, preserves original connections.
    
    Returns:
        tuple: (modified: bool, migrated_data: dict, stats: dict)
    """
    # Handle both raw blueprint and wrapped response format
    if 'response' in blueprint_data:
        blueprint_data = blueprint_data['response']
    
    blueprint = blueprint_data.get('blueprint', blueprint_data)
    
    # Step 1: Standard module migration (v1 -> v2)
    modified, transformed, count = migrate_scenario_object(
        blueprint, 
        'API_Request',
        override_connection_id=connection_id
    )
    
    # Step 2: Inject GetPersonV2 modules for v2 breaking change
    # (GetDeal no longer returns embedded person details)
    person_modified, transformed, person_count = inject_get_person_modules(
        transformed,
        'API_Request',
        override_connection_id=connection_id
    )
    
    if person_modified:
        modified = True
    
    stats = {
        'modules_migrated': count,
        'person_modules_injected': person_count,
        'connection_id': connection_id if connection_id else 'preserved'
    }
    
    return modified, transformed, stats


def main():
    parser = argparse.ArgumentParser(description='Pipedrive v1 to v2 Blueprint Transform Tool')
    parser.add_argument('--id', type=int, help='Scenario ID to fetch and transform')
    parser.add_argument('--file', type=str, help='Local JSON file to transform')
    parser.add_argument('--output-dir', type=str, default='./migrated_scenarios', help='Directory for migrated files')
    parser.add_argument('--check-http', action='store_true', help='Check HTTP modules for Pipedrive v2 endpoint usage (no migration)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if args.id:
        print(f"--- Fetching Scenario {args.id} ---")
        data = fetch_blueprint(args.id)
        if data:
            if 'response' in data:
                 data = data['response']
            
            blueprint = data.get('blueprint', {})
            
            # HTTP Check Mode
            if args.check_http:
                results = []
                if 'flow' in blueprint:
                    check_http_pipedrive_modules(blueprint['flow'], f"ID:{args.id}", results)
                print_http_check_report(results)
                return
            
            # Normal Migration Mode - use migrate_blueprint for full migration including person injection
            modified, transformed, stats = migrate_blueprint(data)
            
            if modified:
                out_path = os.path.join(args.output_dir, f"{args.id}_migrated.json")
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(transformed, f, indent=4, ensure_ascii=False)
                print(f"[OK] Migrated blueprint saved to: {out_path}")
                print(f"    Modules migrated: {stats.get('modules_migrated', 0)}")
                print(f"    Person modules injected: {stats.get('person_modules_injected', 0)}")
                print("You can now upload this file to Make.com.")
            else:
                print("No Pipedrive v1 modules found to migrate.")
                
    elif args.file:
        if not os.path.exists(args.file):
            print(f"[ERROR] File not found: {args.file}")
            return
            
        with open(args.file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # HTTP Check Mode
        if args.check_http:
            results = []
            if 'flow' in data:
                check_http_pipedrive_modules(data['flow'], os.path.basename(args.file), results)
            print_http_check_report(results)
            return
            
        # Use migrate_blueprint for full migration including person injection
        modified, transformed, stats = migrate_blueprint(data)
        if modified:
            out_path = os.path.join(args.output_dir, os.path.basename(args.file).replace('.json', '_migrated.json'))
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(transformed, f, indent=4, ensure_ascii=False)
            print(f"[OK] Migrated file saved to: {out_path}")
            print(f"    Modules migrated: {stats.get('modules_migrated', 0)}")
            print(f"    Person modules injected: {stats.get('person_modules_injected', 0)}")
        else:
            print("No Pipedrive v1 modules found in file.")
    else:
        # Default behavior: process everything in ./scenarios
        if os.path.exists(INPUT_FOLDER):
            print(f"\n--- Scanning folder: {INPUT_FOLDER} ---\n")
            all_results = []
            for filename in os.listdir(INPUT_FOLDER):
                if filename.endswith(".json") and not filename.endswith(OUTPUT_SUFFIX):
                    input_path = os.path.join(INPUT_FOLDER, filename)
                    with open(input_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if args.check_http:
                        # In check mode, just accumulate results
                        blueprint = data.get('blueprint', data) if isinstance(data, dict) else {}
                        if 'flow' in blueprint:
                            check_http_pipedrive_modules(blueprint['flow'], filename, all_results)
                    else:
                        # In migration mode, use migrate_blueprint for full migration
                        modified, transformed, stats = migrate_blueprint(data)
                        if modified:
                            out_path = os.path.join(args.output_dir, filename.replace('.json', '_migrated.json'))
                            with open(out_path, 'w', encoding='utf-8') as f:
                                json.dump(transformed, f, indent=4, ensure_ascii=False)
                            print(f"[OK] Migrated: {filename} -> {out_path}")
                            print(f"    Modules: {stats.get('modules_migrated', 0)}, Person injections: {stats.get('person_modules_injected', 0)}")
            
            if args.check_http:
                print_http_check_report(all_results)
        else:
            parser.print_help()

if __name__ == "__main__":
    main()