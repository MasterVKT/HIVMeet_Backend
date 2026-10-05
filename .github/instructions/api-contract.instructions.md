---
applyTo: "**/views*.py"
---

# API Contract Instructions

When implementing or modifying endpoints:

- Keep URLs aligned with the existing convention under /api/v1/ and use kebab-case resource names.
- Use the correct HTTP method and return the documented status code.
- Preserve response keys and nesting already used by the frontend contract.
- Return consistent error payloads with an error message and, when useful, details for validation errors.
- Avoid breaking pagination, filtering, or ordering behavior for list endpoints.
- If a change affects the API contract, update or review the corresponding documentation before shipping it.
