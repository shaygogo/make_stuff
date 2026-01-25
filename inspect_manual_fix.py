
import json
import os

filename = r"c:\dev\Make_Migration\scenarios\כל הפרטים על המטפלים לפתק בדיל לפי עיר פייפ מכירות והמשך -41d6ivu2dkyuocm9nvg6twlk4ek623q1.blueprint.json"
target_key = "22978b2600c7903dcc36671f870bcf22449a7780"

try:
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    flow = data.get('blueprint', {}).get('flow', [])
    if not flow:
        flow = data.get('flow', []) # Top level flow
    
    print(f"Scanning {len(flow)} modules...")
    
    found = False
    for module in flow:
        mapper = module.get('mapper', {})
        # Check if target key is in mapper or nested in custom_fields
        
        # Check root
        if target_key in mapper:
            print(f"Found in Module {module['id']} ({module['module']}) ROOT:")
            print(json.dumps({target_key: mapper[target_key]}, indent=4))
            found = True
            
        # Check inside custom_fields
        if 'custom_fields' in mapper:
            cf = mapper['custom_fields']
            if target_key in cf:
                print(f"Found in Module {module['id']} ({module['module']}) NESTED in custom_fields:")
                print(json.dumps({target_key: cf[target_key]}, indent=4))
                found = True
        
        if found:
            # Print entire mapper for context
            print("Full Mapper:")
            print(json.dumps(mapper, indent=4))
            break
            
    if not found:
        print("Key not found in any module mapper.")
        
except Exception as e:
    print(f"Error: {e}")
