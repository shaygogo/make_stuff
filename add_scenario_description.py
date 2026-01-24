import json
import sys
from datetime import datetime

def analyze_scenario(blueprint):
    """Generate a human-readable description of a Make.com scenario"""
    
    flow = blueprint.get('flow', [])
    name = blueprint.get('name', 'Unnamed Scenario')
    
    description_parts = []
    description_parts.append(f"**{name}**\n")
    description_parts.append(f"Total modules: {len(flow)}\n\n")
    
    # Analyze flow
    description_parts.append("**Workflow:**\n")
    for i, module in enumerate(flow, 1):
        module_type = module.get('module', 'unknown')
        module_id = module.get('id')
        
        # Determine friendly name
        if module_type == 'gateway:CustomWebHook':
            webhook_label = module.get('metadata', {}).get('restore', {}).get('hook', {}).get('label', '')
            name_str = f"Webhook Trigger: {webhook_label}" if webhook_label else "Webhook Trigger"
        elif module_type == 'airtable:ActionGetRecord':
            table = module.get('mapper', {}).get('table', '')
            name_str = f"Get Airtable Record from {table}" if table else "Get Airtable Record"
        elif module_type == 'airtable:ActionUpdateRecords':
            table = module.get('mapper', {}).get('table', '')
            name_str = f"Update Airtable Record in {table}" if table else "Update Airtable Record"
        elif module_type == 'builtin:BasicRouter':
            name_str = "Router (split flow)"
        elif module_type == 'http:ActionSendData':
            url = module.get('mapper', {}).get('url', '')
            if 'pipedrive' in url.lower():
                name_str = "HTTP Request to Pipedrive API"
            else:
                name_str = "HTTP Request"
        elif module_type == 'builtin:BasicFeeder':
            name_str = "Iterator (loop through items)"
        elif module_type == 'gateway:WebhookRespond':
            name_str = "Webhook Response"
        else:
            name_str = module_type.replace(':', ' - ')
        
        filter_name = module.get('filter', {}).get('name', '')
        if filter_name:
            name_str += f" (Filter: {filter_name})"
        
        description_parts.append(f"{i}. [{module_id}] {name_str}\n")
    
    return ''.join(description_parts)

def add_description_note(blueprint_path, output_path=None):
    """Add auto-generated description as a note to the scenario"""
    
    # Read the blueprint
    with open(blueprint_path, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)
    
    # Parse blueprint
    scenario_name = blueprint.get('name', 'Unnamed Scenario')
    modules = blueprint.get('flow', [])
    module_count = len(modules)
    
    # Build workflow list with emoji indicators
    workflow_lines = []
    for i, module in enumerate(modules, 1):
        module_type = module.get('module', 'unknown')
        module_id = module.get('id')
        
        # Determine emoji based on module type
        emoji = "⚙️"  # Default
        if 'Webhook' in module_type or 'Trigger' in module_type:
            emoji = "🎯"
        elif 'Get' in module_type or 'Search' in module_type or 'List' in module_type:
            emoji = "📖"
        elif 'Update' in module_type or 'Create' in module_type or 'Delete' in module_type:
            emoji = "✏️"
        elif 'Router' in module_type:
            emoji = "🔀"
        elif 'Iterator' in module_type or 'Feeder' in module_type:
            emoji = "🔁"
        elif 'http:' in module_type.lower():
            emoji = "🌐"
        
        # Get friendly name
        if module_type == 'gateway:CustomWebHook':
            webhook_label = module.get('metadata', {}).get('restore', {}).get('hook', {}).get('label', '')
            name_str = f"Webhook: {webhook_label}" if webhook_label else "Webhook Trigger"
        elif module_type == 'airtable:ActionGetRecord':
            table = module.get('mapper', {}).get('table', '')
            name_str = f"Get Airtable Record" + (f" ({table})" if table else "")
        elif module_type == 'airtable:ActionUpdateRecords':
            table = module.get('mapper', {}).get('table', '')
            name_str = f"Update Airtable" + (f" ({table})" if table else "")
        elif module_type == 'builtin:BasicRouter':
            name_str = "Router"
        elif module_type == 'http:ActionSendData':
            name_str = "HTTP Request"
        elif module_type == 'builtin:BasicFeeder':
            name_str = "Iterator"
        elif module_type == 'gateway:WebhookRespond':
            name_str = "Webhook Response"
        else:
            name_str = module_type.replace(':', ' › ')
        
        workflow_lines.append(f"{emoji} <b>{i}.</b> {name_str}")
    
    # Create polished HTML with compact spacing and subtle backgrounds
    html_content = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #333;">
<div style="margin: -8px -8px 8px -8px; padding: 10px 12px; background: #F0FDF4; border-left: 3px solid #10B981;">
    <span style="font-size: 16px;">🤖</span>
    <b style="color: #059669; font-size: 14px; margin-left: 4px;">Auto-Generated Description</b>
</div>

<h4 style="margin: 0 0 6px 0; font-size: 16px; color: #111; font-weight: 700;">{scenario_name}</h4>

<div style="display: inline-block; background: #DBEAFE; color: #1E40AF; padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; margin-bottom: 12px;">
    {module_count} MODULE{"S" if module_count != 1 else ""}
</div>

<div style="background: #F9FAFB; padding: 10px; border-radius: 4px; margin-top: 12px;">
    <div style="font-weight: 600; font-size: 11px; color: #6B7280; text-transform: uppercase; margin-bottom: 8px;">Workflow</div>
    <div style="line-height: 1.8;">
        {('<br>'.join(workflow_lines))}
    </div>
</div>

<div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #E5E7EB; font-size: 10px; color: #9CA3AF; text-align: right;">
    {datetime.now().strftime('%b %d, %Y • %H:%M')}
</div>
</div>"""
    
    # Create the note
    new_note = {
        "moduleIds": [1],  # Attach to first module
        "content": html_content,
        "isFilterNote": False,
        "metadata": {
            "color": "#00C853"  # Green color for auto-generated
        }
    }
    
    # Ensure metadata exists
    if 'metadata' not in blueprint:
        blueprint['metadata'] = {}
    
    # Add or update notes array INSIDE metadata
    if 'notes' not in blueprint['metadata']:
        blueprint['metadata']['notes'] = []
    
    # Remove any existing auto-generated notes from metadata.notes
    blueprint['metadata']['notes'] = [n for n in blueprint['metadata']['notes'] if '[AUTO] Generated Description' not in n.get('content', '')]
    
    # Add the new note to metadata.notes
    blueprint['metadata']['notes'].append(new_note)
    
    # Save
    output_path = output_path or blueprint_path
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(blueprint, f, indent=4, ensure_ascii=False)
    
    print(f"[OK] Added description note to metadata.notes: {output_path}")
    print("\n" + "="*80)
    print(f"SCENARIO: {scenario_name}")
    print(f"MODULES: {module_count}")
    print("="*80)
    
    return blueprint

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python add_scenario_description.py <blueprint.json> [output.json]")
        sys.exit(1)
    
    blueprint_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    add_description_note(blueprint_path, output_path)
