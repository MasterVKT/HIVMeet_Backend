---
applyTo: "**/tests/**/*.py"
---

# Test Instructions

- Prefer focused, behavior-based tests for API and domain logic.
- Cover the happy path and the main failure path for new behavior.
- Keep tests deterministic and avoid over-mocking internal logic.
- When changing behavior that affects security, permissions, or matching logic, add or update regression tests.
