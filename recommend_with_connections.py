"""
Scenario Recommendation Demo
Demonstrates combining app recommendations with existing connections.

This script shows the workflow - actual execution happens via agent MCP tools.
"""

# TEAM CONFIGURATION
TEAM_ID = 7616
ORG_ID = 8538

# Example intention
INTENTION = "send notifications to Slack when important events happen"

print(f"""
Recommendation Workflow for: "{INTENTION}"
{'='*80}

STEP 1: Analyze existing scenarios to find apps already in use
STEP 2: Get app recommendations from Make.com
STEP 3: Merge and prioritize apps that already have connections

This requires agent execution via MCP tools:
- mcp_make_scenarios_list(teamId={TEAM_ID})
- mcp_make_scenarios_get(scenarioId=X) for each scenario
- mcp_make_apps_recommend(intention="{INTENTION}")

Run this via the agent to execute the full workflow.
""")
