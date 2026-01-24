import json, urllib.request

TOKEN = "da4c33f6-42de-4f77-afb7-e7758a8431ca"
headers = {"Authorization": f"Token {TOKEN}", "User-Agent": "Mozilla/5.0"}
scenario_id = 343993

url = f"https://eu1.make.com/api/v2/scenarios/{scenario_id}/blueprint"
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        
        # FIX: Check for 'response' wrapper
        if 'response' in data:
            data = data['response']
        
        # Access blueprint
        blueprint = data.get('blueprint', data)
        flow = blueprint.get('flow', [])
        
        print(f"Scenario {scenario_id} Flow length: {len(flow)}")
        
        def find_pd(modules):
            for m in modules:
                m_str = json.dumps(m).lower()
                if 'pipedrive.com/v1' in m_str:
                    print(f"FOUND v1 call in Module {m.get('id')}! Module type: {m.get('module')}")
                if 'routes' in m:
                    for r in m['routes']: find_pd(r.get('flow', []))
                if 'onerror' in m:
                    find_pd(m['onerror'])
        
        find_pd(flow)
except Exception as e:
    print(f"Error: {e}")
