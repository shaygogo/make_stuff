import json
import os

def load_coords(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle response wrapper if present
    if 'response' in data:
        data = data['response']
    blueprint = data.get('blueprint', data)
    flow = blueprint.get('flow', [])
    
    coords = {}
    
    def extract_coords(modules):
        for m in modules:
            mid = m.get('id')
            if 'metadata' in m and 'designer' in m['metadata']:
                d = m['metadata']['designer']
                coords[mid] = (d.get('x'), d.get('y'))
            
            if 'routes' in m:
                for r in m['routes']:
                    if 'flow' in r:
                        extract_coords(r['flow'])
            if 'onerror' in m:
                extract_coords(m['onerror'])

    extract_coords(flow)
    return coords

before_path = r'c:\dev\Make_Migration\position\before.json'
after_path = r'c:\dev\Make_Migration\position\after.json'

coords_before = load_coords(before_path)
coords_after = load_coords(after_path)

all_ids = sorted(set(coords_before.keys()) | set(coords_after.keys()))
all_ids_sorted = sorted(all_ids, key=lambda mid: coords_before.get(mid, (99999,99999))[0] if coords_before.get(mid) else 99999)

with open('analysis_out.txt', 'w', encoding='utf-8') as f:
    f.write(f"{'ID':<10} | {'Before (X, Y)':<20} | {'After (X, Y)':<20} | {'Delta (dX, dY)':<20}\n")
    f.write("-" * 80 + "\n")

    for mid in all_ids_sorted:
        b = coords_before.get(mid)
        a = coords_after.get(mid)
        
        b_str = f"{b[0]}, {b[1]}" if b else "N/A"
        a_str = f"{a[0]}, {a[1]}" if a else "N/A"
        
        delta_str = ""
        if b and a:
            dx = a[0] - b[0]
            dy = a[1] - b[1]
            if dx != 0 or dy != 0:
                delta_str = f"{dx}, {dy}"
            else:
                delta_str = "0, 0"
        elif b and not a:
            delta_str = "REMOVED"
        elif not b and a:
            delta_str = "ADDED"
            
        f.write(f"{mid:<10} | {b_str:<20} | {a_str:<20} | {delta_str:<20}\n")
    
    f.write(f"Total Modules: {len(all_ids)}\n")
