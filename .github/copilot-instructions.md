# HIVMeet — Instructions Copilot backend

Lire [AGENTS.md](../AGENTS.md), puis `.agents/project-map.json` et le routeur de
skills si la tâche est ambiguë. Les règles backend canoniques sont dans
`.agents/PROJECT_RULES.md`; ne pas les dupliquer ici. Les hooks Copilot versionnés
sont dans `.github/hooks/`.

Respecter strictement serializers, permissions, Firebase, migrations, transactions,
contrats API et confidentialité des données. Utiliser le graphe avant l'exploration
textuelle lorsque disponible. Ne pas présenter un hook configuré comme une
activation observée sans preuve native de l'hôte.
