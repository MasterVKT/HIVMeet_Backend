# Backend Skills Catalog - HIVMeet

## Recommended Entry Point
- Start with `.agents/skills/task-router/SKILL.md` for any request (frontend, backend, mixed).

## Backend Skill Set
- `.agents/skills/drf-api-development/SKILL.md`
- `.agents/skills/serializer-validation/SKILL.md`
- `.agents/skills/security-permissions/SKILL.md`
- `.agents/skills/firebase-auth-sync/SKILL.md`
- `.agents/skills/migrations-data-integrity/SKILL.md`
- `.agents/skills/celery-redis-reliability/SKILL.md`
- `.agents/skills/backend-testing-strategy/SKILL.md`
- `.agents/skills/performance-query-tuning/SKILL.md`
- `.agents/skills/backend-release-readiness/SKILL.md`
- `.agents/skills/backend-incident-hotfix/SKILL.md`

## Frontend Skill Set
- `.agents/skills/frontend-development/SKILL.md`
- `.agents/skills/api-contract-audit/SKILL.md`
- `.agents/skills/i18n-integrity/SKILL.md`
- `.agents/skills/regression-guard/SKILL.md`
- `.agents/skills/release-readiness/SKILL.md`
- `.agents/skills/test-impact-selection/SKILL.md`
- `.agents/skills/bug-fixing/SKILL.md`

## Graph Skills (code-review-graph powered)
- `.agents/skills/debug-issue/SKILL.md`
- `.agents/skills/explore-codebase/SKILL.md`
- `.agents/skills/refactor-safely/SKILL.md`
- `.agents/skills/review-changes/SKILL.md`

## Suggested Routing Shortcuts
- New endpoint: drf-api-development + serializer-validation
- Auth issue: firebase-auth-sync + security-permissions
- Model/data evolution: migrations-data-integrity + backend-testing-strategy
- Async task reliability: celery-redis-reliability + backend-testing-strategy
- Slow endpoint: performance-query-tuning + backend-testing-strategy
- Production emergency: backend-incident-hotfix + backend-testing-strategy

## Scope Notes

## Gouvernance et cycle de vie
- Orchestrateur local : `.agents/skills/hivmeet-backend-orchestrator/SKILL.md`
- Audit de complétude local : `.agents/skills/hivmeet-backend-completion-audit/SKILL.md`
- Gouvernance partagée : `../../../.agents/skills/hivmeet-governance/SKILL.md`

Les adaptateurs `.claude/skills/` redirigent Claude Code et Cline vers les skills
canoniques : ils ne constituent pas une seconde source.
- All skills are in `.agents/skills/` — single source of truth, no duplicates.
- These skills are aligned with Django/DRF backend + Flutter frontend of this repository.
