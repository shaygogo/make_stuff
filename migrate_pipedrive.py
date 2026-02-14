import json
import os
import sys
import argparse
import urllib.request
import re
from dotenv import load_dotenv

load_dotenv() # Load env vars for CLI usage

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
PIPEDRIVE_API_TOKEN = os.getenv('PIPEDRIVE_API_TOKEN', '') # Needed for smart field resolution


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
    'pipedrive:DeleteDeal': 'pipedrive:deleteDealV2',
    'pipedrive:deleteDeal': 'pipedrive:deleteDealV2',
    'pipedrive:AddProductToDeal': 'pipedrive:AddProductToDeal',
    'pipedrive:ListDealFiles': 'pipedrive:listDealFiles', # Check if V2 exists, often generic list
    'pipedrive:ListDealsForProduct': 'pipedrive:listDealsForProduct',
    'pipedrive:ListDealFields': 'pipedrive:listDealFields',
    'pipedrive:GetADealField': 'pipedrive:getADealField',
    'pipedrive:GetDealsSummary': 'pipedrive:getDealsSummary',
    'pipedrive:CreateADealField': 'pipedrive:createADealField',
    'pipedrive:CreateProduct': 'pipedrive:createProductV2',
    'pipedrive:SearchProducts': 'pipedrive:searchProductsV2',
    'pipedrive:GetProduct': 'pipedrive:getProductV2',
    'pipedrive:MakeAPICall': 'pipedrive:MakeAPICallV2',

    # Delete Modules
    'pipedrive:DeletePerson': 'pipedrive:deletePersonV2',
    'pipedrive:deletePerson': 'pipedrive:deletePersonV2',
    'pipedrive:DeleteOrganization': 'pipedrive:deleteOrganizationV2',
    'pipedrive:deleteOrganization': 'pipedrive:deleteOrganizationV2',
    'pipedrive:DeleteActivity': 'pipedrive:deleteActivityV2',
    'pipedrive:deleteActivity': 'pipedrive:deleteActivityV2',
    'pipedrive:DeleteNote': 'pipedrive:deleteNoteV2',
    'pipedrive:deleteNote': 'pipedrive:deleteNoteV2',
    'pipedrive:DeleteFile': 'pipedrive:deleteFileV2',
    'pipedrive:deleteFile': 'pipedrive:deleteFileV2',
    'pipedrive:DownloadFile': 'pipedrive:downloadFileV2',
    'pipedrive:downloadFile': 'pipedrive:downloadFileV2',

    # Products
    'pipedrive:UpdateProduct': 'pipedrive:updateProductV2',
    'pipedrive:updateProduct': 'pipedrive:updateProductV2',
    'pipedrive:DeleteProduct': 'pipedrive:deleteProductV2',
    'pipedrive:deleteProduct': 'pipedrive:deleteProductV2',

    # Inferred / Others
    'pipedrive:UpdateActivity': 'pipedrive:updateActivityV2',
    'pipedrive:ListActivityDeals': 'pipedrive:listActivitiesV2',
    'pipedrive:ListLeadLabels': 'pipedrive:listLeadLabelsV2',
    'pipedrive:ListProductsInDeal': 'pipedrive:listProductsInDealV2',
    'pipedrive:GetOrganization': 'pipedrive:getOrganizationV2',
    'pipedrive:GetActivity': 'pipedrive:getActivityV2',
    'pipedrive:UploadFile': 'pipedrive:uploadFileV2',
    'pipedrive:listDealsForPerson': 'pipedrive:listDealsForPersonV2',
    'pipedrive:GetPerson': 'pipedrive:GetPersonV2',
    'pipedrive:getPerson': 'pipedrive:GetPersonV2',
}

# Modules that don't have a direct v2 equivalent and must use MakeAPICallV2
PIPEDRIVE_GENERIC_REPLACEMENTS = {
    'pipedrive:CreatePerson': {'url': '/v2/persons', 'method': 'POST'},
    'pipedrive:createPerson': {'url': '/v2/persons', 'method': 'POST'},
    'pipedrive:UpdatePerson': {'url': '/v2/persons/{{id}}', 'method': 'PATCH'},
    'pipedrive:updatePerson': {'url': '/v2/persons/{{id}}', 'method': 'PATCH'},
    'pipedrive:CreateNote': {'url': '/v2/notes', 'method': 'POST'},
    'pipedrive:createNote': {'url': '/v2/notes', 'method': 'POST'},
    'pipedrive:UpdateNote': {'url': '/v2/notes/{{id}}', 'method': 'PATCH'},
    'pipedrive:updateNote': {'url': '/v2/notes/{{id}}', 'method': 'PATCH'},
    'pipedrive:GetNote': {'url': '/v2/notes/{{id}}', 'method': 'GET'},
    'pipedrive:getNote': {'url': '/v2/notes/{{id}}', 'method': 'GET'},
    # Search Persons - no direct v2 module exists in Make.com
    'pipedrive:searchPersons': {'url': '/v2/persons/search', 'method': 'GET'},
    'pipedrive:SearchPersons': {'url': '/v2/persons/search', 'method': 'GET'},
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
    if not isinstance(key, str):
        return False
    return len(key) == 40 and all(c in '0123456789abcdef' for c in key)

    return len(key) == 40 and all(c in '0123456789abcdef' for c in key)

def shift_modules_visual_position(flow, min_val, shift_amount, axis='x'):
    """
    Recursively shift modules' coordinate if they are to the right/below a threshold.
    axis: 'x' or 'y'
    """
    for module in flow:
        # Check current module
        if 'metadata' in module and 'designer' in module['metadata']:
            val = module['metadata']['designer'].get(axis, 0)
            if val >= min_val:
                module['metadata']['designer'][axis] = val + shift_amount
        
        # Recurse into routers
        if 'routes' in module:
            for route in module['routes']:
                if 'flow' in route:
                    shift_modules_visual_position(route['flow'], min_val, shift_amount, axis)
                    
        # Recurse into error handlers
        if 'onerror' in module:
            shift_modules_visual_position(module['onerror'], min_val, shift_amount, axis)

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

# --- Smart Field Mapping Helpers ---

def fetch_pipedrive_fields(api_token):
    """
    Fetches field definitions from Pipedrive API (v1 endpoints) to build a map of enum/set fields.
    Returns: dict { 'field_hash': { 'type': 'enum', 'options': [{'id':1, 'label':'A'}] } }
    """
    if not api_token:
        print("[WARNING] PIPEDRIVE_API_TOKEN not set. Smart field mapping will check static known fields only.")
        return {}

    field_map = {}
    endpoints = ['dealFields', 'personFields', 'organizationFields']
    
    print("[INFO] Fetching Pipedrive field definitions for smart mapping...")
    
    for ep in endpoints:
        url = f"https://api.pipedrive.com/v1/{ep}?api_token={api_token}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('success'):
                    for field in data.get('data', []):
                        # We only care about fields that need ID resolution (enum/set)
                        if field.get('field_type') in ['enum', 'set']:
                            key = field.get('key') # The 40-char hash
                            field_map[key] = {
                                'name': field.get('name'),
                                'type': field.get('field_type'),
                                'options': field.get('options', [])
                            }
        except Exception as e:
            print(f"[ERROR] Failed to fetch {ep}: {e}")
            
    print(f"[INFO] Loaded {len(field_map)} smart field definitions.")
    return field_map

def is_dynamic_value(value):
    """Check if value contains Make variable syntax {{...}}"""
    return isinstance(value, str) and "{{" in value

def get_option_id_by_label(field_def, label_value):
    """Lookup ID for a given label in the field definition"""
    for opt in field_def.get('options', []):
        if opt['label'] == label_value:
            return opt['id']
    return None

def create_get_fields_module(module_id, connection_id, x_pos, y_pos):
    """Creates a MakeApiCallV2 module to fetch deal fields for dynamic resolution."""
    return {
        "id": module_id,
        "module": "pipedrive:MakeAPICallV2",
        "version": 2,
        "parameters": {
            "__IMTCONN__": connection_id
        },
        "mapper": {
            "url": "/v2/dealFields", # We assume dealFields covers most use cases. Could need others.
            "method": "GET"
        },
        "metadata": {
            "designer": {
                "x": x_pos,
                "y": y_pos,
                "name": "Get Fields (Smart Cache)"
            },
            "restore": { 
                "expect": {
                    "url": "/v2/dealFields",
                    "method": "GET"
                },
                "parameters": {
                     "__IMTCONN__": {
                        "label": PIPEDRIVE_OAUTH_CONN_LABEL,
                        "data": { "scoped": "true", "connection": "pipedrive-auth" }
                    }
                }
            },
             "expect": [
                {"name": "url", "type": "text", "label": "URL", "required": True},
                {"name": "method", "type": "select", "label": "Method", "required": True}
            ]
        }
    }


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

def create_get_person_module(new_module_id, deal_module_id, connection_id, x_position, y_position=0):
    """
    Create a GetPersonV2 module that fetches person details using the person_id from a deal.
    
    Args:
        new_module_id: The ID to assign to the new module
        deal_module_id: The ID of the deal module to get person_id from
        connection_id: The Pipedrive OAuth connection ID
        x_position: The x position for the module in the designer
        y_position: The y position (optional, default 0)
    
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
                "y": y_position,
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

def group_custom_fields(mapper_dict):
    """
    Identifies and groups custom field keys (primary hash + suffixes) from a mapper dict.
    Returns:
        tuple: (clean_mapper: dict, custom_fields_groups: dict)
    """
    clean_mapper = {}
    custom_fields = {} # { hash: { 'value': val, ...extras } }
    
    # Identify primary hashes first
    primary_hashes = set()
    for key in mapper_dict:
        if is_custom_field(key):
            primary_hashes.add(key)
            
    # Process all keys
    for key, value in mapper_dict.items():
        if key in primary_hashes:
            if key not in custom_fields: custom_fields[key] = {}
            custom_fields[key]['value'] = value
            continue
            
        # Check if it's a suffix of a known hash
        matched_hash = None
        for h in primary_hashes:
            if key.startswith(h + '_'):
                matched_hash = h
                break
        
        if matched_hash:
            suffix = key[len(matched_hash)+1:]
            if matched_hash not in custom_fields: custom_fields[matched_hash] = {}
            custom_fields[matched_hash][suffix] = value
        else:
            clean_mapper[key] = value
            
    return clean_mapper, custom_fields

    return clean_mapper, custom_fields

def upgrade_pipedrive_connection(module, filename, override_connection_id=None, smart_fields_map=None, injection_helper_id=None):
    """
    Upgrades a Pipedrive module's connection from API Key to OAuth.
    Handles the new v2 nested structure for custom fields and collections.
    
    Args:
        module: Module dict to upgrade
        filename: Source filename for logging
        override_connection_id: If provided, use this instead of PIPEDRIVE_OAUTH_CONN_ID
        smart_fields_map: Dict of field definitions for smart mapping (if enabled)
        injection_helper_id: ID of the injected 'Get Fields' module (if enabled)
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
    
    # Collect custom field hashes for getDealV2 custom_fields API parameter
    custom_field_hashes = [f['name'] for f in old_expect if is_custom_field(f.get('name', ''))]
    # Also check old interface for additional custom fields not in expect
    old_interface = old_metadata.get('interface', [])
    if isinstance(old_interface, list):
        for f in old_interface:
            name = f.get('name', '')
            if is_custom_field(name) and name not in custom_field_hashes:
                custom_field_hashes.append(name)
    
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
            
            # Merge parameters and mapper, prioritizing mapper
            # Skip technical parameters
            TECHNICAL_PARAMS = ['__IMTCONN__', '__IMTENV__', 'handleErrors', 'useNewZLibDeCompress']
            merged_data = module.get('parameters', {}).copy()
            for tp in TECHNICAL_PARAMS:
                merged_data.pop(tp, None)
            merged_data.update(old_mapper)
            
            # Use helper to group custom fields
            clean_data, custom_field_groups = group_custom_fields(merged_data)
            
            # Handle product owner renaming
            if '/products' in url:
                 if 'user_id' in clean_data:
                      clean_data['owner_id'] = clean_data.pop('user_id')
            
            body = clean_data
            
            if custom_field_groups:
                processed_groups = {}
                for hash_key, data in custom_field_groups.items():
                    # Types that MUST be objects in V2 (Time, Monetary, Address)
                    is_complex_type = (field_types.get(hash_key) in ['time', 'monetary', 'address'])
                    
                    if not is_complex_type and len(data) == 1 and 'value' in data:
                        val = data['value']
                        # Filter empty strings
                        if val in [None, '', 'null'] and field_types.get(hash_key) == 'time':
                             continue
                        processed_groups[hash_key] = val
                    else:
                        processed_groups[hash_key] = data
                body["custom_fields"] = processed_groups
            
            new_mapper["body"] = json.dumps(body, indent=4, ensure_ascii=False)
        
        elif method == 'GET' and old_mapper:
            # For GET requests, convert old mapper params to query string (qs)
            # MakeAPICallV2 expects: qs = [{"key": "param_name", "value": "val"}, ...]
            qs_items = []
            for key, value in old_mapper.items():
                if key in ['__IMTCONN__', '__IMTENV__', 'handleErrors']:
                    continue
                
                if isinstance(value, list):
                    # Array values (like fields: ["phone"]) -> comma-separated
                    str_val = ",".join(str(v) for v in value)
                elif isinstance(value, bool):
                    str_val = "true" if value else "false"
                else:
                    str_val = str(value) if value is not None else ""
                
                # v2 search API uses 'match' instead of 'exact_match'
                if key == 'exact_match':
                    qs_items.append({"key": "match", "value": "exact" if value else "fuzzy"})
                else:
                    qs_items.append({"key": key, "value": str_val})
            
            if qs_items:
                new_mapper["qs"] = qs_items
                print(f"[{filename}] Preserved {len(qs_items)} params as query string for GET request")
        
        module['mapper'] = new_mapper
    else:
        # Standard Module Transformation
        new_mapper = {}
        custom_fields_mapper = {}
        
        # Use helper to group custom fields
        clean_data, custom_field_groups = group_custom_fields(old_mapper)
        
        for key, value in clean_data.items():
            # Special handling for ListActivityDeals: rename 'id' to 'deal_id'
            if old_module == 'pipedrive:ListActivityDeals' and key == 'id':
                new_mapper['deal_id'] = value
            else:
                new_mapper[key] = value

        for hash_key, data in custom_field_groups.items():
             # Types that MUST be objects in V2 (Time, Monetary, Address)
             is_complex_type = (field_types.get(hash_key) in ['time', 'monetary', 'address'])
             
             if not is_complex_type and len(data) == 1 and 'value' in data:
                 val = data['value']
                 
                 # Filter empty time values
                 if val in [None, '', 'null'] and field_types.get(hash_key) == 'time':
                     continue
                 
                 # --- SMART MAPPING LOGIC START ---
                 if smart_fields_map and hash_key in smart_fields_map:
                     field_def = smart_fields_map[hash_key]
                     
                     if is_dynamic_value(val):
                         # Dynamic Value: Wrap in map() logic if we have a helper
                         if injection_helper_id:
                             # Logic: {{get(map(HELPER.body.data; 'id'; 'label'; VAL); 1)}}
                             # Note: MakeApiCallV2 return structure needs careful pathing.
                             # Assuming /v2/dealFields returns { "data": [ { "key": "HASH", "options": [...] } ] }
                             # This is complex in Make formulas without arrays manipulation.
                             # Simplified Assumption: User needs to map against the options.
                             # If we use a DataStore or Variable, it's cleaner. 
                             # Here we construct the formula best-effort.
                             
                             # Actually, mapping from the big Response Array is hard in one line.
                             # A safer bet is just warning the user, OR assumes a specific path.
                             
                             # Let's insert a simpler "Warning/Note" into the value if we can't perfectly automate it
                             # OR try the map formula:
                             # map(get(map(999.body.data; "options"; "key"; "HASH"); 1); "id"; "label"; VALUE)
                             
                             transformed_val = (
                                 f"{{{{get(map(get(map({injection_helper_id}.body.data; 'options'; 'key'; '{hash_key}'); 1); 'id'; 'label'; {val.replace('{{','').replace('}}','')}); 1)}}}}"
                             )
                             val = transformed_val
                             print(f"[{filename}] SmartMapped Dynamic Field {hash_key} ({field_def['name']})")
                             
                     else:
                         # Static Label: Resolve to ID
                         found_id = get_option_id_by_label(field_def, val)
                         if found_id:
                             print(f"[{filename}] SmartMapped Static Field {hash_key} ({field_def['name']}): '{val}' -> {found_id}")
                             val = found_id
                         else:
                             print(f"[{filename}] WARNING: Could not resolve label '{val}' for field {field_def['name']}")
                             
                 # --- SMART MAPPING LOGIC END ---
                 
                 custom_fields_mapper[hash_key] = val
             else:
                 custom_fields_mapper[hash_key] = data
            
        if custom_fields_mapper:
            new_mapper["custom_fields"] = custom_fields_mapper
            
        module['mapper'] = new_mapper

        # getDealV2 custom_fields are set in post-processing by fix_getDealV2_custom_fields()
        # (scans the full blueprint for actually-referenced hashes, respects 15-field API limit)

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
        
    if new_module in ('pipedrive:getDealV2', 'pipedrive:getProductV2', 'pipedrive:getPersonV2', 'pipedrive:GetPersonV2', 'pipedrive:getOrganizationV2', 'pipedrive:getActivityV2'):
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
    if generic_config:
        # MakeAPICallV2 has its own fixed expect schema - replace entirely
        new_expect = [
            {"type": "hidden"},
            {"name": "url", "type": "text", "label": "URL", "required": True},
            {"name": "method", "type": "select", "label": "Method", "required": True,
             "validate": {"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]}},
            {"name": "headers", "type": "array", "label": "Headers",
             "spec": [{"name": "key", "type": "text", "label": "Key"},
                      {"name": "value", "type": "text", "label": "Value"}]},
            {"name": "qs", "type": "array", "label": "Query String",
             "spec": [{"name": "key", "type": "text", "label": "Key"},
                      {"name": "value", "type": "text", "label": "Value"}]},
            {"name": "body", "type": "any", "label": "Body"}
        ]
        # Also clear the old interface since MakeAPICallV2 output is dynamic
        if 'interface' in module.get('metadata', {}):
            del module['metadata']['interface']
    else:
        new_expect = []
        custom_fields_spec = []
        
        found_id = False
        found_include_fields = False
        
        for field in old_expect:
            name = field.get('name')
            if is_custom_field(name):
                f_copy = field.copy()
                original_type = field.get('type', 'text')
                # Complex multi-value fields (monetary, address, time) need collection wrapping in V2.
                complex_types = {'collection', 'monetary', 'address', 'time'}
                if original_type in complex_types or (isinstance(field.get('spec'), list) and len(field.get('spec', [])) > 1):
                    # Multi-property field - keep as collection
                    f_copy['type'] = 'collection'
                    if 'spec' not in f_copy:
                        f_copy['spec'] = [{"name": "value", "type": original_type if original_type != 'monetary' else 'number', "label": "Value"}]
                # else: keep the original type (text, number, date, enum, etc.)
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
            if new_module == 'pipedrive:getDealV2':
                # getDealV2 is a READ module — custom_fields is a text query param
                # listing which hashes to fetch, NOT a collection of values to write
                pass  # custom_fields text field added below
            else:
                # WRITE modules: custom_fields is a collection of field values
                new_expect.append({
                    "name": "custom_fields",
                    "type": "collection",
                    "label": "Custom Fields",
                    "spec": custom_fields_spec
                })

        # Add ID field if missing — but ONLY for single-entity modules (get/update/delete),
        # NOT for list/search modules which don't require an entity ID
        mod_action = new_module.split(':')[-1].lower()
        is_list_or_search = mod_action.startswith('list') or mod_action.startswith('search')
        if not found_id and not is_list_or_search:
            entity_label = new_module.split(':')[-1].replace('V2', '').replace('get', '').strip()
            if not entity_label:
                entity_label = 'Item'
            new_expect.insert(0, {"name": "id", "type": "integer", "label": f"{entity_label} ID", "required": True})
        # All V2 get modules support include_fields and custom_fields
        v2_get_modules = ('pipedrive:getDealV2', 'pipedrive:getProductV2', 'pipedrive:getPersonV2', 'pipedrive:GetPersonV2', 'pipedrive:getOrganizationV2', 'pipedrive:getActivityV2')
        if not found_include_fields and new_module in v2_get_modules:
            new_expect.append({"name": "include_fields", "type": "select", "label": "Include fields", "multiple": True})
            new_expect.append({"name": "custom_fields", "type": "text", "label": "Custom fields"})

    module['metadata']['expect'] = new_expect
    
    # 5. Parameters
    module['parameters'] = {
        "__IMTCONN__": target_connection_id
    }
    # custom_fields for getDealV2 is now set directly in the mapper (see above)
    
    return True

def process_modules(modules, filename, override_connection_id=None, smart_fields_map=None, injection_helper_id=None):
    """Recursively processes modules, including those inside routers."""
    modified = False
    migration_count = 0
    for module in modules:

        # Recurse into any nested routes (for Routers)
        if 'routes' in module:
            for route in module['routes']:
                if 'flow' in route:
                    nested_modified, nested_count = process_modules(route['flow'], filename, override_connection_id, smart_fields_map, injection_helper_id)
                    if nested_modified:
                        modified = True
                        migration_count += nested_count
        
        # Recurse into error handlers (onerror)
        if 'onerror' in module:
            nested_modified, nested_count = process_modules(module['onerror'], filename, override_connection_id, smart_fields_map, injection_helper_id)
            if nested_modified:
                modified = True
                migration_count += nested_count
        
        if module.get('module') in PIPEDRIVE_MODULE_UPGRADES or module.get('module') in PIPEDRIVE_GENERIC_REPLACEMENTS:
            if upgrade_pipedrive_connection(module, filename, override_connection_id, smart_fields_map, injection_helper_id):
                modified = True
                migration_count += 1

        # getDealV2 custom_fields are handled by fix_getDealV2_custom_fields() post-processing

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
                if 'deals/search' in path or 'itemSearch' in url:
                    found_match = False
                    for item in new_qs:
                        if isinstance(item, dict) and item.get('name') == 'match':
                            found_match = True
                            
                        # Convert exact_match to match=exact
                        if isinstance(item, dict) and item.get('name') == 'exact_match':
                             val = item.get('value')
                             if str(val).lower() in ['true', '1']:
                                  item['name'] = 'match'
                                  item['value'] = 'exact'
                                  found_match = True
                             else:
                                  # If exact_match is false, usage of 'middle' is implied (V1 behavior)
                                  # but we better just remove it and rely on default or set match=middle
                                  # Changing key to REMOVE to filter it out next pass? 
                                  # Easier to just reconstruct new_qs properly above.
                                  pass 
                    
                    found_exact_in_source = any(q.get('name') == 'exact_match' and str(q.get('value')).lower() in ['true', '1'] for q in qs if isinstance(q, dict))
                    
                    if found_exact_in_source and not any(q.get('name') == 'match' for q in new_qs):
                         new_qs.append({"name": "match", "value": "exact"})

                # Handle sorting (sort -> sort_by, sort_direction)
                # Filter out 'sort' from new_qs and parse it
                final_qs = []
                for item in new_qs:
                    if item.get('name') == 'sort':
                        val = item.get('value', '').strip()
                        if ' ' in val:
                            parts = val.split(' ')
                            sort_by = parts[0]
                            sort_dir = parts[1].lower() # ASC/DESC
                        else:
                            sort_by = val
                            sort_dir = 'asc'
                        
                        final_qs.append({"name": "sort_by", "value": sort_by})
                        final_qs.append({"name": "sort_direction", "value": sort_dir})
                    elif item.get('name') == 'start':
                         print(f"[{filename}] WARNING: Removing incompatible 'start' pagination parameter. Check module {module['id']}.")
                         continue
                    else:
                        final_qs.append(item)
                new_qs = final_qs

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
                body_content = mapper.get('body') or params.get('body', '')
                
                # Ensure method is uppercase (required by Pipedrive v2)
                if isinstance(method, str):
                    method = method.upper()

                body = body_content
                if method in ['POST', 'PUT', 'PATCH']:
                    # Ensure body is stringified and check specific renaming
                    if isinstance(body_content, dict):
                         # Handle rewrites
                         if 'products' in path and 'user_id' in body_content:
                              body_content['owner_id'] = body_content.pop('user_id')
                         
                         # Stringify
                         body = json.dumps(body_content, indent=4, ensure_ascii=False)
                    elif isinstance(body_content, str) and body_content.strip().startswith('{'):
                         # Try to parse, fix, re-dump if it looks like JSON
                         try:
                              body_json = json.loads(body_content)
                              if 'products' in path and 'user_id' in body_json:
                                   body_json['owner_id'] = body_json.pop('user_id')
                                   body = json.dumps(body_json, indent=4, ensure_ascii=False)
                              else:
                                   # Ensure valid JSON string
                                   body = body_content
                         except:
                              # Parse error, leave as is
                              body = body_content
                
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
                    # Found the deal module!
                    # Calculate dynamic position based on current state (layout might have shifted)
                    designer = module.get('metadata', {}).get('designer', {})
                    deal_x = designer.get('x', 0)
                    deal_y = designer.get('y', 0)
                    
                    person_x = deal_x + 300
                    person_y = deal_y
                    axis = 'x'
                    threshold = deal_x + 290
                    
                    # Detect layout direction by looking at the next module
                    if idx + 1 < len(flow):
                        next_mod = flow[idx + 1]
                        next_designer = next_mod.get('metadata', {}).get('designer', {})
                        next_x = next_designer.get('x', 0)
                        next_y = next_designer.get('y', 0)
                        
                        dx = abs(next_x - deal_x)
                        dy = abs(next_y - deal_y)
                        
                        if dy > dx:
                            # Vertical Layout
                            person_x = deal_x
                            person_y = deal_y + 300
                            axis = 'y'
                            threshold = deal_y + 290
                    
                    # Shift visual layout globally to make space
                    # We reference blueprint_data['flow'] to ensure global shifting (recursive)
                    shift_modules_visual_position(blueprint_data['flow'], threshold, 300, axis)
                    
                    # Create the GetPersonV2 module
                    person_module = create_get_person_module(
                        injection['person_module_id'],
                        deal_id,
                        injection['connection_id'],
                        person_x,
                        person_y
                    )
                    
                    # Insert after the deal module
                    flow.insert(idx + 1, person_module)
                    
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

def find_pipedrive_module_ids(flow):
    """Recursively find all Pipedrive module IDs in a flow."""
    ids = set()
    for module in flow:
        if module.get('module', '').startswith('pipedrive:'):
            ids.add(module.get('id'))
        
        if 'routes' in module:
            for route in module['routes']:
                if 'flow' in route:
                    ids.update(find_pipedrive_module_ids(route['flow']))
        
        if 'onerror' in module:
            ids.update(find_pipedrive_module_ids(module['onerror']))
    return ids

def rewrite_custom_field_label_references(blueprint_data, helper_id):
    """
    Scans the blueprint for references to Pipedrive custom field labels:
    {{MODULE_ID.HASH.label}}
    
    And replaces them with a dynamic lookup formula using the injected 'Get Fields' helper:
    {{map(get(map(HELPER.body.data; "options"; "key"; "HASH"); 1); "label"; "id"; MODULE_ID.custom_fields.HASH)}}
    
    This fixes the issue where V2 modules return IDs but downstream logic expects Labels.
    """
    if 'flow' not in blueprint_data:
        return False, blueprint_data

    # 1. Identify Pipedrive Modules (to only target their outputs)
    pd_ids = find_pipedrive_module_ids(blueprint_data['flow'])
    if not pd_ids:
        return False, blueprint_data

    blueprint_json = json.dumps(blueprint_data, ensure_ascii=False)
    
    # Regex to find {{ID.HASH.label}}
    # Group 1: ID
    # Group 2: HASH (40 chars hex)
    pattern = r'\{\{(\d+)\.([a-f0-9]{40})\.label\}\}'
    
    def replacement_func(match):
        mod_id = int(match.group(1))
        field_hash = match.group(2)
        
        if mod_id in pd_ids:
            # Construct the lookup formula
            # Note: We must escape double quotes \" because we are inserting into a JSON string value.
            # Python string: \\\" -> Result: \"
            formula = (
                f"{{{{get(map(get(map({helper_id}.body.data; \\\"options\\\"; \\\"field_code\\\"; \\\"{field_hash}\\\"); 1); "
                f"\\\"label\\\"; \\\"id\\\"; {mod_id}.custom_fields.{field_hash}); 1)}}}}"
            )
            return formula
        else:
            return match.group(0) # No change

    new_json = re.sub(pattern, replacement_func, blueprint_json)
    
    if new_json != blueprint_json:
        print(f"[INFO] Rewrote custom field label references using Helper Module {helper_id}")
        return True, json.loads(new_json)
    
    return False, blueprint_data

def fix_getDealV2_custom_fields(blueprint_data, injection_helper_id=None):
    """
    Post-processing: Fix Pipedrive V2 get modules for custom field compatibility.
    
    Applies to: getDealV2, getProductV2, getPersonV2, getOrganizationV2
    
    Fixes applied:
    1. Rewrite flat MODULE_ID.HASH -> MODULE_ID.custom_fields.HASH
    2. Rewrite MODULE_ID.customRaw.HASH -> MODULE_ID.custom_fields.HASH
    3. Rewrite .label suffix on enum fields to use Get Fields helper lookup formula
    4. Set custom_fields mapper param with only the referenced hashes
    5. If >15 custom fields referenced, split into batches by injecting additional modules
    """
    import re
    
    BATCH_SIZE = 15
    
    # All V2 "get" modules that return custom fields nested under custom_fields
    V2_GET_MODULES = {
        'pipedrive:getDealV2',
        'pipedrive:getProductV2',
        'pipedrive:getPersonV2',
        'pipedrive:GetPersonV2',
        'pipedrive:getOrganizationV2',
        'pipedrive:getActivityV2',
    }
    
    def find_v2_get_modules(flow):
        results = []
        for m in flow:
            if m.get('module') in V2_GET_MODULES:
                results.append(m)
            if 'routes' in m:
                for route in m.get('routes', []):
                    if 'flow' in route:
                        results.extend(find_v2_get_modules(route['flow']))
            if 'onerror' in m:
                results.extend(find_v2_get_modules(m['onerror']))
        return results
    
    def insert_after_module(flow, target_id, new_module):
        """Insert new_module right after the module with target_id in the flow."""
        for i, m in enumerate(flow):
            if m.get('id') == target_id:
                flow.insert(i + 1, new_module)
                return True
            if 'routes' in m:
                for route in m.get('routes', []):
                    if 'flow' in route:
                        if insert_after_module(route['flow'], target_id, new_module):
                            return True
            if 'onerror' in m:
                if insert_after_module(m['onerror'], target_id, new_module):
                    return True
        return False
    
    v2_modules = find_v2_get_modules(blueprint_data.get('flow', []))
    if not v2_modules:
        return False
    
    # Serialize blueprint for reference scanning
    blueprint_str = json.dumps(blueprint_data, ensure_ascii=False)
    fixed_any = False
    max_id = find_max_module_id(blueprint_data.get('flow', []))
    modules_to_inject = []  # list of (original_mod_id, new_module_dict)
    # Track custom_fields to set per module ID (applied after string rewrite)
    custom_fields_to_set = {}  # mod_id -> comma-separated hashes
    # Pre-processing: Fix .label suffix and .customRaw references for ALL V2 modules
    
    # Map module types to their fields API endpoint
    MODULE_TO_FIELDS_ENDPOINT = {
        'pipedrive:getDealV2': '/v2/dealFields',
        'pipedrive:getProductV2': '/v2/productFields',
        'pipedrive:getPersonV2': '/v2/personFields',
        'pipedrive:GetPersonV2': '/v2/personFields',
        'pipedrive:getOrganizationV2': '/v2/organizationFields',
        'pipedrive:getActivityV2': '/v2/activityFields',
    }
    
    # Track injected helpers per entity type: endpoint -> helper_module_id
    entity_helpers = {}
    entity_helper_count = 0  # Track how many extra helpers we've added (for y-offset)
    if injection_helper_id:
        # The existing helper is for dealFields
        entity_helpers['/v2/dealFields'] = injection_helper_id
    
    # Find the existing deal fields helper position for relative placement
    def find_module_position(flow, target_id):
        """Find the designer position of a module by its ID."""
        for m in flow:
            if m.get('id') == target_id:
                designer = m.get('metadata', {}).get('designer', {})
                return designer.get('x', 0), designer.get('y', 0)
            if 'routes' in m:
                for route in m.get('routes', []):
                    if 'flow' in route:
                        result = find_module_position(route['flow'], target_id)
                        if result:
                            return result
            if 'onerror' in m:
                result = find_module_position(m['onerror'], target_id)
                if result:
                    return result
        return None
    
    # PASS 1: Inject any missing entity-type helpers (modifies blueprint_data structure)
    for mod in v2_modules:
        mod_id = mod.get('id')
        mod_type = mod.get('module', '')
        if not mod_id:
            continue
        
        # Check if this module has .label references that need a helper
        label_pattern = rf'{mod_id}\.(?:custom_fields\.)?(?:customRaw\.)?`?([a-f0-9]{{40}})`?\.label'
        temp_str = json.dumps(blueprint_data, ensure_ascii=False)
        label_matches = re.findall(label_pattern, temp_str)
        
        if not label_matches:
            continue
        
        fields_endpoint = MODULE_TO_FIELDS_ENDPOINT.get(mod_type, '/v2/dealFields')
        
        # Skip if helper already exists for this endpoint
        if fields_endpoint in entity_helpers:
            continue
        
        if not injection_helper_id:
            print(f"[WARNING] Module {mod_id}: Cannot rewrite .label - no helper available for {fields_endpoint}")
            continue
        
        # Inject a new helper for this entity type
        max_id += 1
        helper_id = max_id
        entity_helpers[fields_endpoint] = helper_id
        entity_helper_count += 1
        
        conn_id = mod.get('parameters', {}).get('__IMTCONN__', '')
        entity_name = fields_endpoint.split('/')[-1]
        
        # Position relative to the existing deal fields helper, inline with the flow
        helper_pos = find_module_position(blueprint_data.get('flow', []), injection_helper_id)
        if helper_pos:
            base_x, base_y = helper_pos
        else:
            base_x, base_y = 300, 0
        
        # Detect layout direction by checking the module after the deal fields helper
        # to determine if the flow is horizontal or vertical
        layout_axis = 'x'  # default horizontal
        next_mod_pos = None
        
        def find_module_after(flow, target_id):
            """Find the module that comes right after target_id in the flow."""
            for i, m in enumerate(flow):
                if m.get('id') == target_id and i + 1 < len(flow):
                    next_m = flow[i + 1]
                    d = next_m.get('metadata', {}).get('designer', {})
                    return d.get('x', 0), d.get('y', 0)
                if 'routes' in m:
                    for route in m.get('routes', []):
                        if 'flow' in route:
                            result = find_module_after(route['flow'], target_id)
                            if result:
                                return result
                if 'onerror' in m:
                    result = find_module_after(m['onerror'], target_id)
                    if result:
                        return result
            return None
        
        next_mod_pos = find_module_after(blueprint_data.get('flow', []), injection_helper_id)
        if next_mod_pos:
            nx, ny = next_mod_pos
            if abs(ny - base_y) > abs(nx - base_x):
                layout_axis = 'y'
        
        # Place each additional helper inline, offset by 300px per helper in the flow direction
        if layout_axis == 'x':
            new_helper_x = base_x + (300 * entity_helper_count)
            new_helper_y = base_y
            # Shift all modules to the right to make room
            shift_modules_visual_position(blueprint_data['flow'], new_helper_x - 10, 300, axis='x')
        else:
            new_helper_x = base_x
            new_helper_y = base_y + (300 * entity_helper_count)
            # Shift all modules below to make room
            shift_modules_visual_position(blueprint_data['flow'], new_helper_y - 10, 300, axis='y')
        
        helper_mod = {
            'id': helper_id,
            'module': 'pipedrive:MakeAPICallV2',
            'version': 2,
            'parameters': {'__IMTCONN__': conn_id},
            'mapper': {'url': fields_endpoint, 'method': 'GET'},
            'metadata': {
                'designer': {'x': new_helper_x, 'y': new_helper_y, 'name': f'Get {entity_name} (Smart Cache)'},
                'restore': {
                    'expect': {'url': fields_endpoint, 'method': 'GET'},
                    'parameters': {
                        '__IMTCONN__': {
                            'label': PIPEDRIVE_OAUTH_CONN_LABEL,
                            'data': {'scoped': 'true', 'connection': 'pipedrive-auth'}
                        }
                    }
                },
                'expect': [
                    {'name': 'url', 'type': 'text', 'label': 'URL', 'required': True},
                    {'name': 'method', 'type': 'select', 'label': 'Method', 'required': True}
                ]
            }
        }
        
        if insert_after_module(blueprint_data['flow'], injection_helper_id, helper_mod):
            print(f"[INFO] Injected '{entity_name}' helper (ID: {helper_id}) at x={new_helper_x}, y={new_helper_y} ({layout_axis}-flow)")
            fixed_any = True
        else:
            blueprint_data['flow'].insert(2, helper_mod)
            print(f"[INFO] Inserted '{entity_name}' helper (ID: {helper_id}) at position 2")
            fixed_any = True
    
    # PASS 2: Re-serialize ONCE after all helpers injected, then do ALL string replacements
    blueprint_str = json.dumps(blueprint_data, ensure_ascii=False)
    
    for mod in v2_modules:
        mod_id = mod.get('id')
        mod_type = mod.get('module', '')
        if not mod_id:
            continue
        
        # Fix .customRaw.HASH -> .custom_fields.HASH  (customRaw was a V1 accessor)
        blueprint_str = re.sub(
            rf'(?<!\w){mod_id}\.customRaw\.(`?)([a-f0-9]{{40}})(`?)',
            rf'{mod_id}.custom_fields.\g<1>\g<2>\g<3>',
            blueprint_str
        )
        
        # Fix .label suffix on custom fields
        fields_endpoint = MODULE_TO_FIELDS_ENDPOINT.get(mod_type, '/v2/dealFields')
        helper_id = entity_helpers.get(fields_endpoint)
        
        if not helper_id:
            continue
        
        label_pattern = rf'{mod_id}\.(?:custom_fields\.)?`?([a-f0-9]{{40}})`?\.label'
        label_matches = re.findall(label_pattern, blueprint_str)
        
        for hash_key in set(label_matches):
            lookup_formula = (
                f'get(map(get(map({helper_id}.body.data; '
                f'\\\"options\\\"; \\\"field_code\\\"; \\\"{hash_key}\\\"); 1); '
                f'\\\"label\\\"; \\\"id\\\"; {mod_id}.custom_fields.`{hash_key}`); 1)'
            )
            
            for old_pattern in [
                f'{mod_id}.custom_fields.`{hash_key}`.label',
                f'{mod_id}.custom_fields.{hash_key}.label',
                f'{mod_id}.`{hash_key}`.label',
                f'{mod_id}.{hash_key}.label',
                f'{mod_id}.customRaw.`{hash_key}`.label',
                f'{mod_id}.customRaw.{hash_key}.label',
            ]:
                if old_pattern in blueprint_str:
                    blueprint_str = blueprint_str.replace(old_pattern, lookup_formula)
                    print(f"[INFO] Module {mod_id}: Rewrote .label on {hash_key[:12]}... using {fields_endpoint.split('/')[-1]} helper")
                    fixed_any = True
    
    for mod in v2_modules:
        mod_id = mod.get('id')
        if not mod_id:
            continue
        
        # Detect monetary and time custom fields from companion fields in interface
        # V1 had: HASH (value), HASH_currency (currency) for monetary
        #         HASH (value), HASH_timezone_id for time fields
        #         HASH (value), HASH_formatted_address, HASH_locality, etc. for address fields
        # V2 returns: custom_fields.HASH = {"value": N, "currency": "C"} for monetary
        #             custom_fields.HASH = {"value": "HH:MM:SS", "timezone_id": N} for time
        #             custom_fields.HASH = {"value": "addr text", "locality": "City", ...} for address
        monetary_hashes = set()
        time_hashes = set()
        address_hashes = set()
        interface = mod.get('metadata', {}).get('interface', [])
        if isinstance(interface, list):
            for field in interface:
                fname = field.get('name', '')
                if fname.endswith('_currency'):
                    base_hash = fname[:-len('_currency')]
                    if re.match(r'^[a-f0-9]{40}$', base_hash):
                        monetary_hashes.add(base_hash)
                elif fname.endswith('_timezone_id'):
                    base_hash = fname[:-len('_timezone_id')]
                    if re.match(r'^[a-f0-9]{40}$', base_hash):
                        time_hashes.add(base_hash)
                elif fname.endswith('_formatted_address'):
                    base_hash = fname[:-len('_formatted_address')]
                    if re.match(r'^[a-f0-9]{40}$', base_hash):
                        address_hashes.add(base_hash)
        
        # Rewrite companion references BEFORE flat-to-nested rewrite
        # Monetary: MOD.HASH_currency -> MOD.custom_fields.HASH.currency
        for h in monetary_hashes:
            for old in [f'{mod_id}.`{h}_currency`', f'{mod_id}.{h}_currency',
                        f'{mod_id}.customRaw.`{h}_currency`', f'{mod_id}.customRaw.{h}_currency',
                        f'{mod_id}.custom_fields.`{h}_currency`', f'{mod_id}.custom_fields.{h}_currency']:
                if old in blueprint_str:
                    blueprint_str = blueprint_str.replace(old, f'{mod_id}.custom_fields.`{h}`.currency')
                    print(f"[INFO] Module {mod_id}: Rewrote monetary _currency companion for {h[:12]}...")
                    fixed_any = True
        
        # Time: MOD.HASH_timezone_id -> MOD.custom_fields.HASH.timezone_id
        for h in time_hashes:
            for suffix in ['_timezone_id', '_timezone_name']:
                v2_suffix = suffix[1:]  # remove leading underscore
                for old in [f'{mod_id}.`{h}{suffix}`', f'{mod_id}.{h}{suffix}',
                            f'{mod_id}.customRaw.`{h}{suffix}`', f'{mod_id}.customRaw.{h}{suffix}',
                            f'{mod_id}.custom_fields.`{h}{suffix}`', f'{mod_id}.custom_fields.{h}{suffix}']:
                    if old in blueprint_str:
                        blueprint_str = blueprint_str.replace(old, f'{mod_id}.custom_fields.`{h}`.{v2_suffix}')
                        print(f"[INFO] Module {mod_id}: Rewrote time {suffix} companion for {h[:12]}...")
                        fixed_any = True
        
        # Address: MOD.HASH_locality -> MOD.custom_fields.HASH.locality, etc.
        ADDRESS_SUFFIXES = [
            '_formatted_address', '_street_number', '_route', '_sublocality',
            '_locality', '_admin_area_level_1', '_admin_area_level_2',
            '_country', '_postal_code', '_subpremise'
        ]
        for h in address_hashes:
            for suffix in ADDRESS_SUFFIXES:
                v2_suffix = suffix[1:]  # remove leading underscore
                for old in [f'{mod_id}.`{h}{suffix}`', f'{mod_id}.{h}{suffix}',
                            f'{mod_id}.customRaw.`{h}{suffix}`', f'{mod_id}.customRaw.{h}{suffix}',
                            f'{mod_id}.custom_fields.`{h}{suffix}`', f'{mod_id}.custom_fields.{h}{suffix}']:
                    if old in blueprint_str:
                        blueprint_str = blueprint_str.replace(old, f'{mod_id}.custom_fields.`{h}`.{v2_suffix}')
                        print(f"[INFO] Module {mod_id}: Rewrote address {suffix} companion for {h[:12]}...")
                        fixed_any = True
        
        # Find all 40-char hex hashes referenced from this module (flat refs)
        pattern = rf'(?<!\w){mod_id}\.(?!custom_fields\.)(`?)([a-f0-9]{{40}})(`?)'
        flat_matches = re.findall(pattern, blueprint_str)
        
        # Also find already-correct nested references
        nested_pattern = rf'{mod_id}\.custom_fields\.`?([a-f0-9]{{40}})`?'
        nested_matches = re.findall(nested_pattern, blueprint_str)
        
        all_hashes = list(set(m[1] for m in flat_matches) | set(nested_matches))
        
        if not all_hashes:
            print(f"[INFO] getDealV2 Module {mod_id}: No custom field references found downstream")
            continue
        
        fixed_any = True
        
        if len(all_hashes) <= BATCH_SIZE:
            # Simple case: all fit in one request
            custom_fields_to_set[mod_id] = ','.join(all_hashes)
            print(f"[INFO] getDealV2 Module {mod_id}: Set {len(all_hashes)} referenced custom fields")
            
            # Rewrite flat references to nested
            if flat_matches:
                rewrite_pattern = rf'(?<!\w)({mod_id})\.(?!custom_fields\.)(`?)([a-f0-9]{{40}})(`?)'
                blueprint_str = re.sub(rewrite_pattern, rf'\g<1>.custom_fields.\g<2>\g<3>\g<4>', blueprint_str)
                print(f"[INFO] getDealV2 Module {mod_id}: Rewrote {len(flat_matches)} flat references to custom_fields.HASH")
            
            # Now append .value for monetary/time/address fields (only on standalone refs)
            object_hashes = monetary_hashes | time_hashes | address_hashes
            for h in object_hashes:
                if h in all_hashes:
                    # Match: MOD.custom_fields.`HASH` or MOD.custom_fields.HASH 
                    # but NOT already followed by a known subfield
                    value_pattern = rf'({mod_id}\.custom_fields\.`?{h}`?)(?!\.(value|currency|timezone_id|timezone_name|label|formatted_address|street_number|route|sublocality|locality|admin_area_level_1|admin_area_level_2|country|postal_code|subpremise))'
                    blueprint_str = re.sub(value_pattern, rf'\g<1>.value', blueprint_str)
                    field_type = "monetary" if h in monetary_hashes else ("time" if h in time_hashes else "address")
                    print(f"[INFO] Module {mod_id}: Appended .value for {field_type} field {h[:12]}...")
        else:
            # Batch case: split into groups of BATCH_SIZE
            batches = [all_hashes[i:i+BATCH_SIZE] for i in range(0, len(all_hashes), BATCH_SIZE)]
            print(f"[INFO] getDealV2 Module {mod_id}: {len(all_hashes)} custom fields -> {len(batches)} batches of <={BATCH_SIZE}")
            
            # First batch stays on original module
            custom_fields_to_set[mod_id] = ','.join(batches[0])
            
            # Build hash -> target module ID mapping
            hash_to_target = {}
            for h in batches[0]:
                hash_to_target[h] = mod_id
            
            # Additional batches: create new getDealV2 modules
            mod_designer = mod.get('metadata', {}).get('designer', {})
            mod_x = mod_designer.get('x', 0)
            mod_y = mod_designer.get('y', 0)
            
            for batch_idx, batch in enumerate(batches[1:], 1):
                max_id += 1
                new_mod_id = max_id
                
                for h in batch:
                    hash_to_target[h] = new_mod_id
                
                new_mod = {
                    'id': new_mod_id,
                    'module': mod.get('module', 'pipedrive:getDealV2'),
                    'version': mod.get('version', 2),
                    'mapper': {
                        'id': mod.get('mapper', {}).get('id', ''),
                        'custom_fields': ','.join(batch)
                    },
                    'parameters': mod.get('parameters', {}).copy(),
                    'metadata': {
                        'expect': mod.get('metadata', {}).get('expect', []),
                        'designer': {
                            'x': mod_x,
                            'y': mod_y + 150 * batch_idx
                        }
                    }
                }
                
                modules_to_inject.append((mod_id, new_mod))
                print(f"[INFO] getDealV2 Module {mod_id}: Created batch {batch_idx+1} as Module {new_mod_id} ({len(batch)} fields)")
            
            # Rewrite ALL references for this module
            for hash_key in all_hashes:
                target = hash_to_target[hash_key]
                
                # Rewrite flat: MOD_ID.HASH -> TARGET.custom_fields.HASH
                blueprint_str = re.sub(
                    rf'(?<!\w){mod_id}\.(?!custom_fields\.)(`?){hash_key}(`?)',
                    rf'{target}.custom_fields.\g<1>{hash_key}\g<2>',
                    blueprint_str
                )
                
                # Rewrite nested (if target changed): MOD_ID.custom_fields.HASH -> TARGET.custom_fields.HASH
                if target != mod_id:
                    blueprint_str = blueprint_str.replace(
                        f'{mod_id}.custom_fields.{hash_key}',
                        f'{target}.custom_fields.{hash_key}'
                    )
                    blueprint_str = blueprint_str.replace(
                        f'{mod_id}.custom_fields.`{hash_key}`',
                        f'{target}.custom_fields.`{hash_key}`'
                    )
            
            # Append .value for monetary/time/address fields in batch case
            object_hashes = monetary_hashes | time_hashes | address_hashes
            for h in object_hashes:
                if h in all_hashes:
                    target = hash_to_target[h]
                    value_pattern = rf'({target}\.custom_fields\.`?{h}`?)(?!\.(value|currency|timezone_id|timezone_name|label|formatted_address|street_number|route|sublocality|locality|admin_area_level_1|admin_area_level_2|country|postal_code|subpremise))'
                    blueprint_str = re.sub(value_pattern, rf'\g<1>.value', blueprint_str)
                    field_type = "monetary" if h in monetary_hashes else ("time" if h in time_hashes else "address")
                    print(f"[INFO] Module {mod_id}: Appended .value for {field_type} field {h[:12]}... (batch target: {target})")
    
    if fixed_any:
        # Parse the rewritten blueprint back
        updated = json.loads(blueprint_str)
        blueprint_data.update(updated)
        
        # Now apply custom_fields to the actual module objects
        def apply_custom_fields(flow):
            for m in flow:
                mid = m.get('id')
                if mid in custom_fields_to_set:
                    m.setdefault('mapper', {})['custom_fields'] = custom_fields_to_set[mid]
                if 'routes' in m:
                    for route in m.get('routes', []):
                        if 'flow' in route:
                            apply_custom_fields(route['flow'])
                if 'onerror' in m:
                    apply_custom_fields(m['onerror'])
        
        apply_custom_fields(blueprint_data['flow'])
        
        # Inject additional modules
        for original_id, new_mod in modules_to_inject:
            if insert_after_module(blueprint_data['flow'], original_id, new_mod):
                print(f"[INFO] Injected getDealV2 batch Module {new_mod['id']} after Module {original_id}")
    
    return fixed_any


def inject_field_map_module(blueprint_data):
    """
    Inject a 'Compose a String' module that lists ALL Pipedrive module outputs
    with live {{...}} references for debugging/verification.
    
    Covers: V2 get/update/create/list/search modules, auto-injected person modules,
    helper API call modules, and generic API call replacements.
    """
    import re
    
    # All Pipedrive module prefixes we care about
    def is_pipedrive_module(mod):
        module_name = mod.get('module', '')
        return module_name.startswith('pipedrive:') or (
            module_name == 'pipedrive:MakeAPICallV2'
        )
    
    def find_all_pipedrive_modules(flow):
        results = []
        for m in flow:
            mod_name = m.get('module', '')
            if mod_name.startswith('pipedrive:'):
                results.append(m)
            # Also pick up auto-injected helper modules (MakeAPICallV2 used for field lookups)
            elif mod_name == 'pipedrive:MakeAPICallV2':
                results.append(m)
            if 'routes' in m:
                for route in m.get('routes', []):
                    if 'flow' in route:
                        results.extend(find_all_pipedrive_modules(route['flow']))
            if 'onerror' in m:
                results.extend(find_all_pipedrive_modules(m['onerror']))
        return results
    
    all_pd_modules = find_all_pipedrive_modules(blueprint_data.get('flow', []))
    if not all_pd_modules:
        return False
    
    # Serialize the blueprint once for scanning references
    blueprint_str = json.dumps(blueprint_data, ensure_ascii=False)
    
    # Build the diagnostic text
    text_parts = ["=== Pipedrive V2 Migration Map ==="]
    
    for mod in all_pd_modules:
        mod_id = mod.get('id')
        mod_type = mod.get('module', '')
        mod_short = mod_type.split(':')[-1]
        designer_name = mod.get('metadata', {}).get('designer', {}).get('name', '')
        
        # Skip "Get Fields" helper modules (Smart Cache) — they're internal helpers
        if 'Smart Cache' in designer_name:
            continue
        
        # Check if this module's output is actually referenced anywhere
        ref_pattern = f'{mod_id}.'
        if ref_pattern not in blueprint_str:
            continue
        
        # Build field label map from interface metadata
        interface = mod.get('metadata', {}).get('interface', [])
        field_map = {}  # name -> {label, type, is_custom}
        custom_field_names = set()
        
        if isinstance(interface, list):
            for field in interface:
                fname = field.get('name', '')
                flabel = field.get('label', '')
                ftype = field.get('type', '')
                if not fname:
                    continue
                is_custom = bool(re.match(r'^[a-f0-9]{40}$', fname))
                if is_custom:
                    custom_field_names.add(fname)
                field_map[fname] = {
                    'label': flabel or fname,
                    'type': ftype,
                    'is_custom': is_custom
                }
        
        # Find which fields from this module are actually referenced in the blueprint
        # Pattern: MODULE_ID.FIELD_NAME (possibly with backticks for custom fields)
        referenced_fields = set()
        
        # Standard fields: "MOD_ID.field_name"
        std_refs = re.findall(rf'(?<!\d){mod_id}\.([a-zA-Z_][a-zA-Z0-9_]*)', blueprint_str)
        for f in std_refs:
            if f not in ('custom_fields',):  # skip the container itself
                referenced_fields.add(f)
        
        # Custom fields: "MOD_ID.custom_fields.`HASH`" or "MOD_ID.custom_fields.HASH"
        cf_refs = re.findall(rf'{mod_id}\.custom_fields\.`?([a-f0-9]{{40}})`?', blueprint_str)
        for h in cf_refs:
            referenced_fields.add(h)
        
        # Also check the custom_fields parameter (requested hashes)
        cf_param = mod.get('mapper', {}).get('custom_fields', '')
        if cf_param and isinstance(cf_param, str):
            for h in cf_param.split(','):
                h = h.strip()
                if h:
                    referenced_fields.add(h)
        
        if not referenced_fields:
            continue
        
        # Build the section header
        header = f"\n--- Module {mod_id}: {mod_short}"
        if designer_name:
            header += f" ({designer_name})"
        header += " ---"
        text_parts.append(header)
        
        # Standard fields first
        std_fields = sorted([f for f in referenced_fields if f not in custom_field_names and not re.match(r'^[a-f0-9]{40}$', f)])
        for fname in std_fields:
            info = field_map.get(fname, {})
            label = info.get('label', fname)
            ref = "{{" + f"{mod_id}.{fname}" + "}}"
            text_parts.append(f"  {label}: {ref}")
        
        # Custom fields
        custom_fields = sorted([f for f in referenced_fields if re.match(r'^[a-f0-9]{40}$', f)])
        if custom_fields:
            text_parts.append("  -- Custom Fields --")
            for h in custom_fields:
                info = field_map.get(h, {})
                label = info.get('label', h[:16] + '...')
                ref = "{{" + f"{mod_id}.custom_fields.`{h}`" + "}}"
                text_parts.append(f"  {label}: {ref}")
    
    if len(text_parts) <= 1:
        return False
    
    diagnostic_text = "\n".join(text_parts)
    
    # Find max module ID for the new Compose module
    max_id = find_max_module_id(blueprint_data.get('flow', []))
    new_id = max_id + 1
    
    # Place after the last Pipedrive module that has referenced outputs
    last_pd_mod = all_pd_modules[-1]
    last_mod_id = last_pd_mod.get('id')
    last_designer = last_pd_mod.get('metadata', {}).get('designer', {})
    last_x = last_designer.get('x', 0)
    last_y = last_designer.get('y', 0)
    
    compose_module = {
        'id': new_id,
        'module': 'util:ComposeTransformer',
        'version': 1,
        'parameters': {},
        'mapper': {
            'value': diagnostic_text
        },
        'metadata': {
            'expect': [
                {
                    'name': 'value',
                    'type': 'text',
                    'label': 'Text'
                }
            ],
            'restore': {},
            'designer': {
                'x': last_x + 300,
                'y': last_y,
                'name': 'Pipedrive Migration Map'
            }
        }
    }
    
    # Insert after the last Pipedrive module (recursive search through routes)
    def insert_after(flow, target_id, new_mod):
        for i, m in enumerate(flow):
            if m.get('id') == target_id:
                flow.insert(i + 1, new_mod)
                return True
            if 'routes' in m:
                for route in m.get('routes', []):
                    if 'flow' in route:
                        if insert_after(route['flow'], target_id, new_mod):
                            return True
            if 'onerror' in m:
                if insert_after(m['onerror'], target_id, new_mod):
                    return True
        return False
    
    if insert_after(blueprint_data['flow'], last_mod_id, compose_module):
        print(f"[INFO] Injected 'Pipedrive Migration Map' Compose module (ID: {new_id}) after module {last_mod_id}")
    else:
        # Fallback: append to main flow
        blueprint_data['flow'].append(compose_module)
        print(f"[INFO] Injected 'Pipedrive Migration Map' Compose module (ID: {new_id}) at end of flow")
    
    return True

def migrate_scenario_object(data, scenario_info, override_connection_id=None, smart_fields_enabled=True):
    modified = False
    migration_count = 0
    
    smart_fields_map = {}
    injection_helper_id = None
    
    if smart_fields_enabled:
        # 1. Fetch Field Defs
        smart_fields_map = fetch_pipedrive_fields(PIPEDRIVE_API_TOKEN)
        
        # 2. Logic to inject "Get Fields" module at the very start
        if 'flow' in data and len(data['flow']) > 0:
            # We insert it at the beginning
            # Find a safe ID (max + 1) NO, we should probably do MAX + 100 to avoid conflicts
            # Or just MAX + 1
            max_id = find_max_module_id(data['flow'])
            injection_helper_id = max_id + 99 # High number to stand out
            
            # Determine connection to use
            conn_id = override_connection_id if override_connection_id else PIPEDRIVE_OAUTH_CONN_ID
            
            # Position logic: User requests it NOT be first.
            # We will insert at index 1 (second module).
            
            first_mod = data['flow'][0]
            first_x = first_mod.get('metadata', {}).get('designer', {}).get('x', 0)
            first_y = first_mod.get('metadata', {}).get('designer', {}).get('y', 0)
            
            # Default placement: to the right
            helper_x = first_x + 300
            helper_y = first_y
            
            # Check 2nd module (if exists) to detect layout direction
            if len(data['flow']) > 1:
                second_mod = data['flow'][1]
                second_x = second_mod.get('metadata', {}).get('designer', {}).get('x', 0)
                second_y = second_mod.get('metadata', {}).get('designer', {}).get('y', 0)
                
                dx = abs(second_x - first_x)
                dy = abs(second_y - first_y)
                
                if dy > dx:
                    # Vertical Layout dominant
                    helper_x = first_x
                    helper_y = first_y + 300
                    # Shift everything below
                    shift_modules_visual_position(data['flow'], helper_y - 10, 300, axis='y')
                    
                else:
                    # Horizontal Layout (or single module, or messy)
                    # We ensure we are inserting visually "between" 0 and 1
                    # But simpler is to assume standard right-flow unless vertical is proven.
                    # Shift everything to the right
                    shift_modules_visual_position(data['flow'], helper_x - 10, 300, axis='x')
            
            else:
                 # Only 1 module. Just place to the right. No shifting needed (no subsequent modules).
                 pass
            
            # Create the helper module
            helper_mod = create_get_fields_module(injection_helper_id, conn_id, helper_x, helper_y)
            
            # Insert at index 1
            data['flow'].insert(1, helper_mod)
            
            print(f"[INFO] Injected 'Get Fields' Smart Cache module (ID: {injection_helper_id}) at position 2")
    
    if 'flow' in data:
        modified, migration_count = process_modules(data['flow'], scenario_info, override_connection_id, smart_fields_map, injection_helper_id)
        
    if smart_fields_enabled and injection_helper_id:
        modified = True # We definitely modified it by adding the module
        
        # New Step: Rewrite Output References (Label -> Formula)
        rewritten, new_data = rewrite_custom_field_label_references(data, injection_helper_id)
        if rewritten:
            data = new_data
    
    # Post-processing: Set custom_fields on getDealV2 modules
    # Must happen after all transformations so we can scan final references
    if 'flow' in data:
        cf_fixed = fix_getDealV2_custom_fields(data, injection_helper_id)
        if cf_fixed:
            modified = True
        
        # Inject diagnostic "Compose a String" module with all custom field mappings
        if inject_field_map_module(data):
            modified = True
        
    return modified, data, migration_count

def migrate_blueprint(blueprint_data, connection_id=None, smart_fields=True):
    """
    Programmatic interface for migrating a blueprint.
    
    Args:
        blueprint_data: The blueprint JSON object (dict)
        connection_id: Optional connection ID to use. If None, preserves original connections.
        smart_fields: Boolean, whether to enable smart field mapping (enum ID resolution)
    
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
        override_connection_id=connection_id,
        smart_fields_enabled=smart_fields
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
    parser.add_argument('--smart-fields', action='store_true', help='Enable smart resolution of enum/set fields (requires PIPEDRIVE_API_TOKEN)')
    
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
            modified, transformed, stats = migrate_blueprint(data, smart_fields=args.smart_fields)
            
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
        modified, transformed, stats = migrate_blueprint(data, smart_fields=args.smart_fields)
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
                        modified, transformed, stats = migrate_blueprint(data, smart_fields=args.smart_fields)
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