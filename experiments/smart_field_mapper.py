import json
import re

# --- MOCK DATA (Simulating Pipedrive API Response) ---
# In production, this comes from GET /dealFields
PIPEDRIVE_FIELD_DEFINITIONS = {
    "170fec77b436631984905a2a5f82308bad04aff3": {
        "name": "תעריף טיפולים",
        "type": "enum",
        "options": [
            {"id": 5877, "label": "תעריף 2022"},
            {"id": 7068, "label": "תעריף 2023"},
            {"id": 9885, "label": "תעריף 2025"},
            {"id": 9438, "label": "תעריף 2026"},
            {"id": 5891, "label": "תעריף be-well"}
        ]
    }
}

# --- LOGIC ---

def is_dynamic_value(value):
    """Check if value contains Make variable syntax {{...}}"""
    return isinstance(value, str) and "{{" in value

def get_option_id_by_label(field_hash, label_value):
    """Lookup ID for a given label in the field definitions"""
    field_def = PIPEDRIVE_FIELD_DEFINITIONS.get(field_hash)
    if not field_def or field_def['type'] != 'enum':
        return None
    
    for opt in field_def.get('options', []):
        if opt['label'] == label_value:
            return opt['id']
    return None

def transform_mapper_smart(mapper, injected_helper_id=999):
    """
    Scans a mapper dictionary. 
    Refactors Static Labels -> IDs
    Refactors Dynamic Vars -> map() formula
    """
    new_mapper = {}
    logs = []
    
    # Standard Pipedrive v2 structure requirement: custom fields go into 'custom_fields'
    # For this test, we simplify and just show the value transformation
    
    for key, value in mapper.items():
        # Check if this key is a known Custom Field
        if key in PIPEDRIVE_FIELD_DEFINITIONS:
            field_def = PIPEDRIVE_FIELD_DEFINITIONS[key]
            logs.append(f"Detected Custom Enum Field: {field_def['name']} ({key})")

            # CASE A: Dynamic Value (Variable)
            if is_dynamic_value(value):
                # We construct the smart map() formula
                # formula: {{get(map(999.body.data.options; "id"; "label"; ORIGINAL_VALUE); 1)}}
                # Note: We assume the helper module returns the specific field definition in body.data
                
                # Logic: We need to map the whole OPTIONS array. 
                # In a real scenario, the GetDealFields returns ALL fields. 
                # So the path is usually: 
                # 999.data -> find element where key matches -> .options 
                # This is complex in Make formulas. 
                
                # SIMPLER APPROACH for Test: Assume we inject a Variable/DataStore or use the simpler map structure
                # "map(2.options; id; label; value)" validation requires checking the array exists.
                
                # Let's generate the formula assuming we have the options array available from the helper
                # For the test, we'll format it as the user requested
                
                # Assuming the helper module (ID 999) outputs the dictionary of fields
                transformed_value = (
                   f"{{{{get(map({injected_helper_id}.custom_field_options.{key}; 'id'; 'label'; {value.replace('{{', '').replace('}}', '')}); 1)}}}}"
                )
                logs.append(f"  -> Converted Dynamic Value to Formula: {transformed_value}")
                new_mapper[key] = transformed_value

            # CASE B: Static Value (Label)
            else:
                found_id = get_option_id_by_label(key, value)
                if found_id:
                    logs.append(f"  -> Resolved Static Label '{value}' to ID {found_id}")
                    new_mapper[key] = found_id
                else:
                    logs.append(f"  -> WARNING: Could not find ID for label '{value}'")
                    new_mapper[key] = value # Keep original if fails
        
        else:
            # Standard field, keep as is
            new_mapper[key] = value

    return new_mapper, logs

# --- EXECUTION ---

def run_experiment():
    print("--- STARTING EXPERIMENT ---\n")
    
    # Load fixture
    with open('experiments/fixtures/enum_mapping_scenario.json', 'r', encoding='utf-8') as f:
        scenario = json.load(f)

    for module in scenario['modules']:
        if 'mapper' in module:
            print(f"Processing Module {module['id']} ({module['module']})...")
            
            original_mapper = module['mapper']
            new_mapper, logs = transform_mapper_smart(original_mapper)
            
            # Print Logs
            for log in logs:
                print(log)
            
            # Compare
            print(f"  Original: {json.dumps(original_mapper, ensure_ascii=False)}")
            print(f"  Transformed: {json.dumps(new_mapper, ensure_ascii=False)}")
            print("-" * 30)

if __name__ == "__main__":
    run_experiment()
