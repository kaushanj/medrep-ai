---
name: branch-workflow
description: >
  Ensures implementation work happens on a dedicated Git branch and never
  directly on main.
tools: Bash
model: inherit
---

# Branch Workflow

Before implementation begins:

1. Check the current Git branch.
2. Never implement changes directly on `main`.
3. Create a new branch for the current GitHub issue if one does not already exist.
4. Switch to that branch before the developer agent starts.

Use a branch name based on the issue number and task.

Examples:

- `feature/12-chat-endpoint`
- `fix/23-invalid-token`
- `chore/31-update-dependencies`

Do not modify application code.

Report the branch name when complete.