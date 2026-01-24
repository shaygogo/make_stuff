import urllib.request
import json
import time
import os
import argparse
from migrate_pipedrive import upgrade_pipedrive_connection

TOKEN = "da4c33f6-42de-4f77-afb7-e7758a8431ca"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE_URL = "https://eu1.make.com/api/v2"

def make_request(url, method='GET', data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Token {TOKEN}")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Content-Type", "application/json")
    
    body = None
    if data:
        body = json.dumps(data).encode('utf-8')
    
    try:
        with urllib.request.urlopen(req, data=body) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error on {method} {url}: {e}")
        return None

def migrate_scenario(sid, sname, dry_run=True):
    print(f"\n--- Processing Scenario {sid}: {sname} ---")
    
    # 1. Fetch Blueprint
    url = f"{BASE_URL}/scenarios/{sid}/blueprint"
    blueprint_data = make_request(url)
    if not blueprint_data:
        print(f"[ERROR] Could not fetch blueprint for {sid}")
        return False
    
    blueprint = blueprint_data.get('blueprint', {})
    flow = blueprint.get('flow', [])
    
    # 2. Transform Blueprint
    changed = False
    
    def process_flow(modules):
        nonlocal changed
        for mod in modules:
            if upgrade_pipedrive_connection(mod, f"Scenario:{sid}"):
                changed = True
            
            if 'routes' in mod:
                for route in mod['routes']:
                    process_flow(route.get('flow', []))
            if 'onerror' in mod:
                process_flow(mod['onerror'])

    process_flow(flow)
    
    if not changed:
        print(f"[INFO] No Pipedrive v1 modules found in {sid}. Skipping.")
        return False
    
    # 3. Update Scenario
    if dry_run:
        print(f"[DRY RUN] Would have updated {sid}. Saving transformed blueprint locally.")
        if not os.path.exists('scenarios_v2_transformed'):
            os.makedirs('scenarios_v2_transformed')
        with open(f'scenarios_v2_transformed/{sid}_v2.json', 'w', encoding='utf-8') as f:
            json.dump(blueprint, f, indent=4)
        return True
    else:
        # Backup first
        if not os.path.exists('backups'):
            os.makedirs('backups')
        with open(f'backups/{sid}_original.json', 'w', encoding='utf-8') as f:
            json.dump(blueprint_data, f, indent=4)
        
        # Update
        print(f"[ACTION] Updating scenario {sid} on Make.com...")
        update_url = f"{BASE_URL}/scenarios/{sid}"
        # Make expects the blueprint as a JSON object inside the payload
        # Note: Sometimes Make expects stringified JSON for the blueprint field, 
        # but via API v2 it's usually the object if the endpoint supports it.
        # Actually, the docs for UPDATE SCENARIO show it takes a 'blueprint' field.
        update_payload = {
            "blueprint": blueprint
        }
        
        result = make_request(update_url, method='PATCH', data=update_payload)
        if result:
            print(f"[SUCCESS] Scenario {sid} updated successfully.")
            return True
        else:
            print(f"[FAILED] Failed to update scenario {sid}.")
            return False

def main():
    parser = argparse.ArgumentParser(description='Automate Pipedrive v1 to v2 migration.')
    parser.add_argument('--target-id', type=int, help='Migrate a single specific scenario ID')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of scenarios (default 10)')
    parser.add_argument('--apply', action='store_true', help='Actually apply changes (not a dry run)')
    args = parser.parse_args()
    
    with open('pipedrive_scenarios_7616.json', 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    if args.target_id:
        target = next((s for s in scenarios if s['id'] == args.target_id), None)
        if target:
            migrate_scenario(target['id'], target['name'], dry_run=not args.apply)
        else:
            print(f"[ERROR] Target ID {args.target_id} not found in Pipedrive list.")
    else:
        count = 0
        for s in scenarios:
            if count >= args.limit:
                break
            if migrate_scenario(s['id'], s['name'], dry_run=not args.apply):
                count += 1
            time.sleep(1) # Safety delay

if __name__ == "__main__":
    main()
