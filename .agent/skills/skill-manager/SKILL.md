---
name: skill-manager
description: Manage agent memory. Trigger on: user rule definition, bug fix, or discovery of new reusable patterns.
---

# Skill Management Protocol

## Triggers
1. **User Request**: "Remember this...", "Create a skill for..."
2. **Auto-Correction**: You fixed a bug, found an undocumented API format, or corrected a path.

## Update Protocol
1. **Verify**: Is this a general rule? (Not one-off data).
2. **Edit**: Update the relevant `.agent/skills/<name>/SKILL.md`.
   - Add/Update "## Learned Patterns".
3. **Notify**: "I updated the [Skill] skill with [Rule]."

## Safety
- **No Secrets/IDs**: Save patterns only.
- **No Duplicates**.
