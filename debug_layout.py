import json
import os

try:
    with open(r'c:\dev\Make_Migration\position\after.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if 'response' in data:
        data = data['response']
    
    blueprint = data.get('blueprint', data)
    flow = blueprint.get('flow', [])
    
    print(f"Total Top-Level Modules: {len(flow)}")
    
    print("--- First 5 Modules ---")
    for i, m in enumerate(flow[:5]):
        mid = m.get('id')
        designer = m.get('metadata', {}).get('designer', {})
        print(f"Index {i}: ID {mid} @ ({designer.get('x')}, {designer.get('y')}) Name: {designer.get('name', 'N/A')}")

    # Check for Router
    for m in flow:
        if m.get('module') == 'router':
            print(f"Router found: ID {m.get('id')}")

except Exception as e:
    print(f"Error: {e}")
