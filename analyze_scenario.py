import json

with open('scenario_343993_blueprint.json', encoding='utf-8') as f:
    data = json.load(f)

blueprint = data['response']['blueprint']
modules = blueprint['flow']

print(f"Total modules in scenario: {len(modules)}")
print("\nModule Sequence:")
print("=" * 80)

for i, module in enumerate(modules, 1):
    module_type = module.get('module', 'unknown')
    module_id = module.get('id')
    
    # Get filter name if exists
    filter_info = module.get('filter', {})
    filter_name = filter_info.get('name', '')
    
    # Determine module name
    if module_type == 'gateway:CustomWebHook':
        name = "Webhook Trigger"
    elif module_type == 'airtable:ActionGetRecord':
        name = "Get Airtable Record"
    elif module_type == 'builtin:BasicRouter':
        name = "Router (splits into routes)"
    elif module_type == 'http:ActionSendData':
        url = module.get('mapper', {}).get('url', '')
        if 'pipedrive' in url:
            name = "HTTP Request to Pipedrive"
        else:
            name = "HTTP Request"
    elif module_type == 'builtin:BasicFeeder':
        name = "Iterator (loops through array)"
    elif module_type == 'airtable:ActionUpdateRecords':
        name = "Update Airtable Record"
    else:
        name = module_type
    
    print(f"{i}. [{module_id}] {name}")
    if filter_name:
        print(f"   Filter: '{filter_name}'")
