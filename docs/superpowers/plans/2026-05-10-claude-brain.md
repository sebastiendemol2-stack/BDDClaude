    # Claude-Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mettre en place `claude-brain` comme couche mémoire persistante Supabase pour les sessions Claude Code, avec chargement automatique au démarrage et sauvegarde automatique à 90% de contexte.

**Architecture:** Script Python `_scripts/brain.py` (commandes `load` / `save`) calqué sur `sync.py` existant. Hooks Claude Code déclenchent la sauvegarde automatiquement. Résultat du `load` mis en cache dans `wiki/context-session.md` lu par `/prime`.

**Tech Stack:** Python 3, httpx (déjà dans `_scripts/lib/`), Supabase REST API (service_role), Claude Code hooks (settings.json)

---

## File Map

| Fichier | Action | Responsabilité |
|---|---|---|
| `_scripts/brain.py` | Créer | Commandes load / save vers Supabase claude-brain |
| `_scripts/.env` | Modifier | Ajouter BRAIN_URL + BRAIN_SERVICE_KEY |
| `_scripts/.env.example` | Modifier | Même variables (sans valeurs réelles) |
| `.claude/settings.json` | Créer | Hooks Notification (90%) + Stop |
| `wiki/context-session.md` | Auto-généré | Cache du load — lu par /prime |
| `skills/prime.md` | Modifier | Ajouter lecture de context-session.md |
| `skills/save.md` | Modifier | Ajouter appel brain.py save |

---

## Task 1 : Migration Supabase — Schema + RLS

**Files:**
- Aucun fichier local — exécution via MCP Supabase (projet claude-brain)

> ⚠️ Utilise l'outil MCP `mcp__dcaafc3f...__execute_sql` sur le projet claude-brain (pas `ottoqbwctcpzzdfzewdi`). Obtiens d'abord le project_id de claude-brain via `list_projects`.

- [ ] **Step 1 : Identifier le project_id de claude-brain**

Via MCP : `list_projects` → noter le project_id du projet "claude-brain" (région CA).

- [ ] **Step 2 : Recréer les tables avec le bon schema**

```sql
-- Supprimer les tables existantes (vides)
DROP TABLE IF EXISTS public.claude_memory CASCADE;
DROP TABLE IF EXISTS public.sessions CASCADE;
DROP TABLE IF EXISTS public.projects CASCADE;
DROP TABLE IF EXISTS public.vault_notes CASCADE;

-- projects
CREATE TABLE public.projects (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text UNIQUE NOT NULL,
  name        text NOT NULL,
  working_dir text NOT NULL,
  status      text DEFAULT 'active',
  created_at  timestamptz DEFAULT now()
);

-- sessions
CREATE TABLE public.sessions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid REFERENCES public.projects(id),
  started_at  timestamptz DEFAULT now(),
  ended_at    timestamptz,
  summary     text,
  trigger     text
);

-- claude_memory
CREATE TABLE public.claude_memory (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid REFERENCES public.projects(id),
  type        text NOT NULL,
  key         text NOT NULL,
  value       text NOT NULL,
  session_id  uuid REFERENCES public.sessions(id),
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now(),
  UNIQUE (project_id, key)
);

-- vault_notes (réservé futur sync Obsidian)
CREATE TABLE public.vault_notes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz DEFAULT now()
);
```

- [ ] **Step 3 : Activer RLS sur toutes les tables**

```sql
ALTER TABLE public.projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claude_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vault_notes   ENABLE ROW LEVEL SECURITY;
```

- [ ] **Step 4 : Vérifier — aucun accès anon**

```sql
-- Vérification : RLS activé sur toutes les tables
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

Attendu : `rowsecurity = true` pour les 4 tables.

- [ ] **Step 5 : Récupérer l'URL et la service_role key du projet**

Via MCP : `get_project_url` + `get_publishable_keys` → noter `BRAIN_URL` et `BRAIN_SERVICE_KEY` (dans le dashboard Supabase : Settings → API → service_role secret).

---

## Task 2 : Variables d'environnement

**Files:**
- Modify: `_scripts/.env`
- Modify: `_scripts/.env.example`

- [ ] **Step 1 : Ajouter les variables brain dans .env**

Ouvrir `_scripts/.env` et ajouter à la fin :

```
BRAIN_URL=https://<claude-brain-project-id>.supabase.co
BRAIN_SERVICE_KEY=<service_role_key_from_task1>
```

Ne pas modifier les variables SUPABASE_URL / SUPABASE_ANON_KEY existantes (elles sont pour sync.py / projet base-de-donnees).

- [ ] **Step 2 : Mettre à jour .env.example**

Remplacer le contenu de `_scripts/.env.example` par :

```
SUPABASE_URL=https://ottoqbwctcpzzdfzewdi.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
VAULT_PATH=C:\base de données
BRAIN_URL=https://<claude-brain-project-id>.supabase.co
BRAIN_SERVICE_KEY=your_service_role_key_here
```

---

## Task 3 : brain.py — Structure de base + commande `load`

**Files:**
- Create: `_scripts/brain.py`
- Test: exécution manuelle CLI

- [ ] **Step 1 : Créer le fichier brain.py avec la structure de base**

```python
"""
Mémoire persistante Claude Code <-> Supabase (claude-brain).

Usage:
    python brain.py load --dir "D:\\Dev\\base-de-donnees"
    python brain.py save --dir "D:\\Dev\\base-de-donnees" --summary "..." --trigger manual
    python brain.py save --dir "D:\\Dev\\base-de-donnees" --trigger stop --summary-only
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "lib"))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BRAIN_URL = os.environ["BRAIN_URL"]
BRAIN_KEY = os.environ["BRAIN_SERVICE_KEY"]
VAULT_PATH = Path(os.environ.get("VAULT_PATH", Path(__file__).parent.parent))

HEADERS = {
    "apikey": BRAIN_KEY,
    "Authorization": f"Bearer {BRAIN_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def rest(method: str, path: str, **kwargs) -> httpx.Response:
    url = f"{BRAIN_URL}/rest/v1/{path}"
    r = httpx.request(method, url, headers=HEADERS, **kwargs)
    r.raise_for_status()
    return r
```

- [ ] **Step 2 : Ajouter la fonction `get_or_create_project`**

```python
def get_or_create_project(working_dir: str) -> dict:
    slug = Path(working_dir).name.lower().replace(" ", "-")
    r = rest("GET", f"projects?working_dir=eq.{working_dir}&select=*")
    rows = r.json()
    if rows:
        return rows[0]
    r = rest("POST", "projects", json={
        "slug": slug,
        "name": Path(working_dir).name,
        "working_dir": working_dir,
        "status": "active",
    })
    return r.json()[0]
```

- [ ] **Step 3 : Ajouter la fonction `load`**

```python
def load(working_dir: str) -> None:
    project = get_or_create_project(working_dir)
    project_id = project["id"]

    # Mémoire globale (project_id IS NULL)
    r_global = rest("GET", "claude_memory?project_id=is.null&select=type,key,value,updated_at&order=updated_at.desc")
    global_mem = r_global.json()

    # Mémoire projet
    r_project = rest("GET", f"claude_memory?project_id=eq.{project_id}&select=type,key,value,updated_at&order=updated_at.desc")
    project_mem = r_project.json()

    # Écrire wiki/context-session.md
    output_path = VAULT_PATH / "wiki" / "context-session.md"
    lines = [
        "---",
        "type: context-session",
        f"generated: {datetime.now(timezone.utc).isoformat()}",
        f"project: {project['slug']}",
        "---",
        "",
        "# Contexte session Claude Brain",
        "",
        f"**Projet :** {project['name']} (`{working_dir}`)",
        "",
    ]

    if global_mem:
        lines += ["## Mémoire globale", ""]
        for m in global_mem:
            lines.append(f"- **[{m['type']}] {m['key']}** : {m['value']}")
        lines.append("")

    if project_mem:
        lines += [f"## Mémoire projet — {project['name']}", ""]
        for m in project_mem:
            lines.append(f"- **[{m['type']}] {m['key']}** : {m['value']}")
        lines.append("")

    if not global_mem and not project_mem:
        lines.append("_Aucune mémoire enregistrée pour ce projet._")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Contexte chargé → {output_path}")
    print(f"  {len(global_mem)} entrées globales, {len(project_mem)} entrées projet")
```

- [ ] **Step 4 : Tester la commande load**

```bash
cd _scripts
python brain.py load --dir "D:\Dev\base-de-donnees"
```

Attendu :
```
✓ Contexte chargé → ...\wiki\context-session.md
  0 entrées globales, 0 entrées projet
```

Et `wiki/context-session.md` doit exister avec le header YAML.

---

## Task 4 : brain.py — commande `save`

**Files:**
- Modify: `_scripts/brain.py`

- [ ] **Step 1 : Ajouter `get_or_create_session`**

```python
def get_or_create_session(project_id: str) -> dict:
    # Chercher une session ouverte (ended_at IS NULL)
    r = rest("GET", f"sessions?project_id=eq.{project_id}&ended_at=is.null&select=*&order=started_at.desc&limit=1")
    rows = r.json()
    if rows:
        return rows[0]
    r = rest("POST", "sessions", json={"project_id": project_id})
    return r.json()[0]
```

- [ ] **Step 2 : Ajouter `upsert_memory`**

```python
def upsert_memory(project_id: str | None, type_: str, key: str, value: str, session_id: str) -> None:
    payload = {
        "project_id": project_id,
        "type": type_,
        "key": key,
        "value": value,
        "session_id": session_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    rest("POST", "claude_memory", json=payload, headers={
        **HEADERS,
        "Prefer": "resolution=merge-duplicates,return=representation",
    })
```

- [ ] **Step 3 : Ajouter la fonction `save`**

```python
def save(working_dir: str, summary: str | None, trigger: str, summary_only: bool) -> None:
    project = get_or_create_project(working_dir)
    project_id = project["id"]
    session = get_or_create_session(project_id)
    session_id = session["id"]

    # Clôturer la session
    patch_data: dict = {
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
    }
    if summary:
        patch_data["summary"] = summary

    rest("PATCH", f"sessions?id=eq.{session_id}", json=patch_data)

    if summary_only:
        print(f"✓ Session clôturée (trigger: {trigger})")
        return

    # Upsert mémoire projet : état courant
    if summary:
        upsert_memory(project_id, "state", "last-session-summary", summary, session_id)

    upsert_memory(project_id, "state", "last-session-date",
                  datetime.now(timezone.utc).date().isoformat(), session_id)

    print(f"✓ Session sauvegardée (trigger: {trigger})")
    print(f"  Projet : {project['name']} | Session : {session_id[:8]}...")
```

- [ ] **Step 4 : Ajouter le point d'entrée `main`**

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Brain — mémoire persistante sessions")
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load")
    p_load.add_argument("--dir", required=True, help="Répertoire de travail courant")

    p_save = sub.add_parser("save")
    p_save.add_argument("--dir", required=True, help="Répertoire de travail courant")
    p_save.add_argument("--summary", default=None, help="Résumé de la session")
    p_save.add_argument("--trigger", default="manual", choices=["manual", "context-limit", "stop"])
    p_save.add_argument("--summary-only", action="store_true", help="Clôture session sans upsert mémoire")

    args = parser.parse_args()

    if args.command == "load":
        load(args.dir)
    elif args.command == "save":
        save(args.dir, args.summary, args.trigger, args.summary_only)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5 : Tester save complet**

```bash
python brain.py save --dir "D:\Dev\base-de-donnees" --summary "Test initial brain.py" --trigger manual
```

Attendu :
```
✓ Session sauvegardée (trigger: manual)
  Projet : base-de-donnees | Session : xxxxxxxx...
```

- [ ] **Step 6 : Vérifier dans Supabase**

Via MCP `execute_sql` sur le projet claude-brain :
```sql
SELECT p.name, s.summary, s.trigger, s.ended_at
FROM sessions s
JOIN projects p ON p.id = s.project_id
ORDER BY s.started_at DESC
LIMIT 5;
```

Attendu : une ligne avec `summary = "Test initial brain.py"` et `ended_at` non null.

- [ ] **Step 7 : Tester save --summary-only (hook Stop)**

```bash
python brain.py save --dir "D:\Dev\base-de-donnees" --trigger stop --summary-only
```

Attendu :
```
✓ Session clôturée (trigger: stop)
```

---

## Task 5 : Hooks Claude Code

**Files:**
- Create: `.claude/settings.json`

- [ ] **Step 1 : Créer .claude/settings.json**

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "context window.*9[0-9]%",
        "hooks": [
          {
            "type": "command",
            "command": "python D:\\Dev\\base-de-donnees\\_scripts\\brain.py save --dir \"D:\\Dev\\base-de-donnees\" --trigger context-limit"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python D:\\Dev\\base-de-donnees\\_scripts\\brain.py save --dir \"D:\\Dev\\base-de-donnees\" --trigger stop --summary-only"
          }
        ]
      }
    ]
  }
}
```

> ⚠️ Les chemins sont absolus car les hooks s'exécutent hors du répertoire courant.

- [ ] **Step 2 : Vérifier la syntaxe JSON**

```bash
python -c "import json; json.load(open('.claude/settings.json')); print('JSON valide')"
```

---

## Task 6 : Mettre à jour `/prime`

**Files:**
- Modify: `skills/prime.md`

- [ ] **Step 1 : Ajouter l'étape brain load dans prime.md**

Remplacer le contenu de `skills/prime.md` par :

```markdown
# Prime — Chargement de contexte

Charge le contexte du vault au debut de chaque session Claude Code.

## Etapes

1. **Lance brain.py load** pour charger la mémoire persistante depuis Supabase :
   ```bash
   python _scripts/brain.py load --dir "D:\Dev\base-de-donnees"
   ```

2. **Lis `wiki/context-session.md`** — généré par l'étape précédente, contient la mémoire projet

3. **Lis `CLAUDE.md`** a la racine du vault — ce sont les instructions operationnelles

4. **Lis `wiki/index.md`** — c'est le panneau de direction du wiki

5. **Lis la derniere daily note** dans `wiki/Daily/` — c'est le resume de la session precedente

## Output attendu

Confirme ce qui a ete charge en resumant :

- Nombre d'entrées mémoire chargées depuis claude-brain
- Nombre de categories dans l'index
- Derniere daily note lue (date)
- Points cles de la derniere session

## Regles

- Ne JAMAIS ecrire dans le vault pendant /prime — c'est une operation de lecture uniquement
- Ne JAMAIS scanner tous les fichiers du wiki — utilise l'index comme point d'entree
- Si brain.py échoue (Supabase inaccessible), continuer sans erreur fatale
- Si l'index n'existe pas ou est vide, le signaler a l'utilisateur
```

---

## Task 7 : Mettre à jour `/save`

**Files:**
- Modify: `skills/save.md`

- [ ] **Step 1 : Ajouter l'étape brain save dans save.md**

Ajouter une nouvelle étape **avant** "### 1. Daily note" :

```markdown
### 0. Sauvegarder dans claude-brain

Lancer brain.py save avec un résumé de la session :

```bash
python _scripts/brain.py save \
  --dir "D:\Dev\base-de-donnees" \
  --summary "<résumé 1-2 phrases de ce qui a été fait>" \
  --trigger manual
```

Si brain.py échoue (Supabase inaccessible), continuer les étapes suivantes sans erreur fatale.
```

---

## Task 8 : Test end-to-end

- [ ] **Step 1 : Simuler une session complète**

```bash
# 1. Load au démarrage
python _scripts/brain.py load --dir "D:\Dev\base-de-donnees"

# 2. Ajouter manuellement une entrée mémoire de test
# (via brain.py ou directement dans Supabase dashboard)

# 3. Save en fin de session
python _scripts/brain.py save --dir "D:\Dev\base-de-donnees" --summary "Session end-to-end test" --trigger manual

# 4. Recharger pour vérifier la persistance
python _scripts/brain.py load --dir "D:\Dev\base-de-donnees"
cat wiki/context-session.md
```

- [ ] **Step 2 : Vérifier que la clé anon est bien bloquée**

```bash
python -c "
import httpx, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('_scripts/.env'))
# Utiliser anon key de base-de-donnees pour tester (pas de clé anon pour brain)
# Ce test vérifie que sans service_role, les tables retournent 0 rows ou 403
url = os.environ['BRAIN_URL'] + '/rest/v1/projects?select=*'
r = httpx.get(url, headers={'apikey': 'invalid_key', 'Authorization': 'Bearer invalid_key'})
print(f'Status: {r.status_code} — attendu 401 ou 403')
"
```

---

## Self-Review

**Spec coverage :**
- ✅ Schema Supabase (Task 1)
- ✅ RLS activé (Task 1, Step 3)
- ✅ Variables d'environnement (Task 2)
- ✅ `brain.py load` → `context-session.md` (Task 3)
- ✅ `brain.py save` complet + `--summary-only` (Task 4)
- ✅ Hook Notification 90% + Hook Stop (Task 5)
- ✅ `/prime` mis à jour (Task 6)
- ✅ `/save` mis à jour (Task 7)
- ✅ Test end-to-end (Task 8)

**Placeholder scan :** aucun TBD ni TODO.

**Type consistency :** `project_id` est `str | None` partout, `session_id` est `str` partout, `upsert_memory` accepte `project_id: str | None` correctement.
