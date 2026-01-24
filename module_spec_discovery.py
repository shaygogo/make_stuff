"""
Get Module Specifications from Make.com API

This demonstrates how to retrieve module configuration requirements
for building scenarios from prompts.
"""

import json
import sys

# Example: How to get module information via MCP tools

print("""
MODULE SPECIFICATION DISCOVERY
================================

There are several ways to get module specs:

1. Via Scenario Interface (mcp_make_scenarios_interface)
   - Get the interface for a scenario
   - Shows modules used and their configuration

2. Via Module Validation (mcp_make_validate_module_configuration)
   - Validates a module configuration
   - Returns what parameters are required/optional
   - Shows field types and structures

3. Via Direct API (using inspect approach)
   - Make API endpoints for getting module metadata
   - Need to know app name and module name

Let me demonstrate each approach:
""")

# Method 1: Get scenario interface to see module configurations
print("\n=== METHOD 1: Scenario Interface ===")
print("Tool: mcp_make_scenarios_interface(scenarioId=YOUR_ID)")
print("Returns: The interface definition showing all modules and their parameters")

# Method 2: Validate module configuration (also returns spec info)
print("\n=== METHOD 2: Module Validation ===")
print("""
Tool: mcp_make_validate_module_configuration(
    organizationId=8538,
    teamId=7616,
    appName="slack",
    appVersion=4,
    moduleName="PostMessage",  # The specific module
    parameters={},  # Static params
    mapper={}  # Dynamic params
)

This will return:
- Required fields
- Field types and structures
- Validation errors showing what's missing
- Available options/choices
""")

# Method 3: Discovery by examining existing scenario
print("\n=== METHOD 3: Reverse Engineer from Existing Scenarios ===")
print("""
1. Get a scenario blueprint with the module you want
2. Examine the module's parameters and mapper structure
3. Use that as a template for new scenarios

Example module structure:
{
    "id": 1,
    "module": "slack:PostMessage",
    "version": 4,
    "parameters": {
        "channel": "CXXXXXX"  # Static channel ID
    },
    "mapper": {
        "text": "Hello World!"  # Dynamic message text
    },
    "metadata": {
        "designer": {
            "x": 100,
            "y": 200
        }
    }
}
""")

print("\n=== RECOMMENDED APPROACH ===")
print("""
For building scenarios from prompts, use this workflow:

1. Get recommended apps: mcp_make_apps_recommend(intention="...")
2. For each recommended app, pick a relevant module (e.g., "PostMessage")
3. Use mcp_make_validate_module_configuration with EMPTY params/mapper
4. The validation errors will tell you what's required!
5. Build the module configuration based on the errors
6. Validate again until successful

This is an iterative approach that uses validation errors as documentation!
""")
