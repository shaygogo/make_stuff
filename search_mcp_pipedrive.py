import json
import urllib.request
import time
import os

TOKEN = "da4c33f6-42de-4f77-afb7-e7758a8431ca"
TOKEN = os.getenv("MAKE_API_TOKEN")
if not TOKEN:
    print("[ERROR] MAKE_API_TOKEN environment variable is not set.")
    exit(1)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE_URL = "https://eu1.make.com/api/v2"
TEAM_ID = 7616

def fetch_all_scenarios(team_id):
    scenarios = []
    offset = 0
    limit = 100
    while True:
        url = f"{BASE_URL}/scenarios?teamId={team_id}&pg[limit]={limit}&pg[offset]={offset}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Token {TOKEN}")
        req.add_header("User-Agent", USER_AGENT)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                page = data.get('scenarios', [])
                if not page:
                    break
                scenarios.extend(page)
                offset += limit
                print(f"Fetched {len(scenarios)} scenario headers so far...")
                if len(page) < limit:
                    break
        except Exception as e:
            print(f"[ERROR] Listing scenarios: {e}")
            break
    return scenarios

def fetch_blueprint(scenario_id):
    url = f"{BASE_URL}/scenarios/{scenario_id}/blueprint"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Token {TOKEN}")
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            # FIX: Dig into 'response' if present
            if 'response' in data:
                data = data['response']
            
            return data.get('blueprint', data)
    except: return None

def check_modules(modules):
    results = []
    for module in modules:
        m_str = json.dumps(module).lower()
        # Look for the combination of pipedrive.com and v1
        if 'pipedrive.com' in m_str and '/v1' in m_str:
            # Try to find exactly what module it is
            m_id = module.get('id', 'unknown')
            m_type = module.get('module', 'unknown')
            results.append((m_id, m_type))
        
        # Recurse
        if 'routes' in module:
            for route in module['routes']:
                results.extend(check_modules(route.get('flow', [])))
        if 'onerror' in module:
            results.extend(check_modules(module['onerror']))
    return results

def main():
    print(f"Starting FIXED Paged Search for Team {TEAM_ID}...")
    scenarios = fetch_all_scenarios(TEAM_ID)
    print(f"Scanning {len(scenarios)} total scenarios...")
    
    found_scenarios = []
    for s in scenarios:
        sid = s['id']
        sname = s.get('name', 'Unknown')
        
        blueprint = fetch_blueprint(sid)
        if blueprint:
            flow = blueprint.get('flow', [])
            matches = check_modules(flow)
            
            if matches:
                print(f"[FOUND] ID: {sid} | Name: {sname}")
                for mid, mtype in matches:
                    print(f"    - Module {mid} ({mtype})")
                found_scenarios.append(sid)
            
            # Explicit cleanup
            del blueprint
        
        time.sleep(0.01) # Speed up slightly as we have 381 to do

    print(f"\nScan complete. Total scenarios with Pipedrive v1 HTTP/Generic calls: {len(found_scenarios)}")
    if found_scenarios:
        print(f"Target IDs: {found_scenarios}")

if __name__ == "__main__":
    main()
