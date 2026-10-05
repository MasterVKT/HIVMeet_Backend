# HIVMeet — Adaptateur Claude Code backend

Lire d'abord [AGENTS.md](AGENTS.md). Les skills canoniques sont dans
`.agents/skills`; les adaptateurs de découverte Claude/Cline sont dans
`.claude/skills`. Les hooks Claude sont configurés dans `.claude/settings.json`.

Utiliser le graphe de revue avant une exploration textuelle lorsque disponible,
puis appliquer le workflow local, les garde-fous DRF et l'audit final.
