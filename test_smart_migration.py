
import os
import json
from dotenv import load_dotenv
from migrate_pipedrive import migrate_blueprint, fetch_pipedrive_fields

# Load environment variables
load_dotenv()

def test_migration():
    input_file = 'scenarios/shay migration test.blueprint.json'
    
    print(f"Loading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"PIPEDRIVE_API_TOKEN from env: {os.getenv('PIPEDRIVE_API_TOKEN')}")
    
    print("Running migration with smart_fields=True...")
    modified, transformed, stats = migrate_blueprint(data, smart_fields=True)
    
    print("Migration complete.")
    print(f"Stats: {stats}")
    
    # Check if helper module was injected (first module)
    flow = transformed.get('blueprint', transformed).get('flow', [])
    if flow and flow[0].get('metadata', {}).get('designer', {}).get('name') == "Get Fields (Smart Cache)":
        print("[SUCCESS] Helper module injected.")
    else:
        print("[FAIL] Helper module NOT injected.")

if __name__ == "__main__":
    test_migration()
