---
applyTo: "**/*.py"
---

# Django Backend Instructions for GitHub Copilot

Follow these rules when editing Python code in this repository:

- Prefer the existing app/domain structure: authentication, profiles, matching, messaging, subscriptions, resources.
- Keep business logic in services or helper modules rather than stuffing it into views.
- Use DRF serializers for all incoming user data and validate strictness instead of trusting request payloads.
- Protect authenticated endpoints with the appropriate permission classes and keep access checks explicit.
- Respect the API contract in the documentation and existing endpoints; preserve response shapes and status codes.
- Use transactions for critical multi-step operations such as matching, premium activation, and account deletion.
- Avoid hardcoded secrets; use environment variables via python-decouple.
- Log sensitive actions with user context but never log secrets or full tokens.
- When changing models, include the corresponding migration and keep data migrations safe.
