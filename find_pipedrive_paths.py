import json

def find_paths(data, target, path=""):
    if isinstance(data, dict):
        for k, v in data.items():
            new_path = f"{path}.{k}" if path else k
            if target in str(k).lower() or target in str(v).lower():
                print(f"Match in key/value at: {new_path}")
                if isinstance(v, (str, int, float)):
                    print(f"  Value: {v}")
            find_paths(v, target, new_path)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_path = f"{path}[{i}]"
            if target in str(v).lower():
                print(f"Match in list at: {new_path}")
            find_paths(v, target, new_path)

with open('scenario_343993_blueprint.json', encoding='utf-8') as f:
    data = json.load(f)
    print("Searching for 'pipedrive' in Scenario 343993 Blueprint...")
    find_paths(data, 'pipedrive')
