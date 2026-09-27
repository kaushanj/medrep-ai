---
name: boundary-testing
description: >
  Tests numeric boundaries: minimum, one below minimum, maximum, one above
  maximum, and old boundary values when a limit changes. Use when writing,
  updating, or reviewing tests for numeric limits, ranges, min/max
  validation, quantity caps, or a changed numeric constraint.
---

# Boundary Testing

For every numeric limit, test:

- minimum
- one below minimum
- maximum
- one above maximum
- old boundary values when a limit changes

Treat inclusive bounds as `[MIN, MAX]`. The valid boundary is the last accepted value. The first invalid value is the first integer outside that boundary.

## Required cases

| Case | Value | Expected |
| --- | --- | --- |
| minimum | `MIN` | valid |
| one below minimum | `MIN - 1` | invalid |
| maximum | `MAX` | valid |
| one above maximum | `MAX + 1` | invalid |

Do not substitute nearby values (`MIN + 1`, `MAX - 1`, typical happy-path numbers) for these four cases. Those may exist as extra coverage; they do not replace the boundary.

If only a minimum exists, still test minimum and one below minimum. If only a maximum exists, still test maximum and one above maximum.

## Old boundary values when a limit changes

When `MIN` or `MAX` moves, keep tests for the previous edges.

1. Add the four cases for the **new** limit.
2. Keep (or add) tests for the **old** boundary values: old minimum, one below old minimum, old maximum, one above old maximum.
3. Update expected outcomes for old values that crossed the new limit. A former valid maximum that now sits above the new maximum must be invalid.

Do not delete old-boundary tests because they no longer sit on the current edge. They catch the old limit coming back.

## Reporting

In the final report, name each boundary case and its expected outcome:

- valid boundary value (`MIN`, `MAX`)
- first invalid value outside that boundary (`MIN - 1`, `MAX + 1`)
- any old boundary values that still need coverage after a limit change
