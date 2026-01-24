import json
import urllib.request

TOKEN = "da4c33f6-42de-4f77-afb7-e7758a8431ca"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE_URL = "https://eu1.make.com/api/v2"

def main():
    scenario_id = 343993
    url = f"{BASE_URL}/scenarios/{scenario_id}/blueprint"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Token {TOKEN}")
    req.add_header("User-Agent", USER_AGENT)
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            blueprint = data.get('blueprint', data)
            flow = blueprint.get('flow', [])
            
            print(f"Inspecting Scenario {scenario_id}...")
            find_pipedrive(flow)
    except Exception as e:
        print(f"Error: {e}")

def find_pipedrive(modules):
    for m in modules:
        # Convert module to string to find any mention of pipedrive
        m_str = json.dumps(m).lower()
        if 'pipedrive.com' in m_str:
            print(f"[MATCH] Module {m.get('id')} ({m.get('module')}):")
            # Extract possible URL fields
            params = m.get('parameters', {})
            mapper = m.get('mapper', {})
            print(f"  - Parameter URL: {params.get('url')}")
            print(f"  - Mapper URL: {mapper.get('url')}")
            
        if 'routes' in m:
            for r in m['routes']:
                find_pipedrive(r.get('flow', []))
        if 'onerror' in m:
            find_pipedrive(m['onerror'])

if __name__ == "__main__":
    main()
