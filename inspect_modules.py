
import json
import os

filename = r"c:\dev\Make_Migration\migrated_scenarios\כל הפרטים על המטפלים לפתק בדיל לפי עיר פייפ מכירות והמשך -41d6ivu2dkyuocm9nvg6twlk4ek623q1.blueprint_migrated.json"

try:
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    flow = data.get('blueprint', {}).get('flow', [])
    if not flow:
        flow = data.get('flow', []) # Top level flow
    
    print(f"File has {len(flow)} modules:")
    for module in flow:
        print(f"ID: {module['id']} - {module['module']}")
        
except Exception as e:
    print(f"Error: {e}")
