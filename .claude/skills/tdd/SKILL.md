---
name: tdd
description: >
  Implements a change with test-driven development: write a failing test,
  confirm it fails for the expected reason, implement the minimum code to
  pass, then refactor without changing behavior. Use when implementing a
  feature, bug fix, or behavior change, or when asked for TDD,
  red-green-refactor, or a failing test first.
---

# Test-Driven Development

Follow the steps in order for testable behavior changes.

Do not write implementation code before a failing test exists for the requested
behavior unless the change cannot reasonably be tested first. If that happens,
state why before proceeding.

## Workflow

1. Understand the task and existing code.
   Read the requirement and the relevant existing code, tests, and conventions
   before writing anything.

2. RED: write a failing test first.
   Add the smallest test that demonstrates the requested behavior.
   Do not change implementation code in this step.

3. Confirm the test fails for the expected reason.
   Run the new test.
   It must fail because the requested behavior is missing or incorrect.
   If it passes, or fails for another reason, fix the test and run it again.
   Do not continue until the failure matches the missing behavior.

4. GREEN: implement the minimum code required to pass.
   Change only the implementation needed for the test to pass.
   Do not add unrelated functionality.

5. REFACTOR: improve the code without changing behavior.
   Clean up only after the test passes.
   Keep all tests passing during refactoring.
   Do not weaken test assertions to accommodate the implementation.

6. Run relevant tests again.
   Run the new test and the existing tests related to the changed behavior.
   Run the broader test suite when practical.

7. Summarize what changed and what was tested.
   Report:
   - files changed
   - behavior added or fixed
   - tests added or changed
   - test commands executed
   - test results

## Rules

- Do not weaken, skip, or remove tests just to make them pass.
- Do not implement unrelated functionality.
- Prefer testing observable behavior instead of implementation details.
- Follow the project's existing testing framework and conventions.
- Do not claim tests passed unless they were actually executed.