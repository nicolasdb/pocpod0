# Schéma TOML v1 — Pipeline Otis

> Source canonique : `references/schema-v1.md` (partagé) — **ce chemin n'existe
> pas ailleurs dans ce dépôt** ; si un autre dépôt/système le référence
> littéralement, voir la note de handoff datée du 30 août ci-dessous avant de
> renommer ou déplacer ce fichier.
> Dernière mise à jour : 30 août 2026 — anagnorisis redevient un flag (voir §4
> et le journal de changements en fin de fichier)

Le pipeline Otis produit **deux niveaux de TOML**, un seul protocole :

| Niveau | Format | Contenu | Où | Producteur |
|---|---|---|---|---|
| **Raw** | `[session_capture]` + `[[trace]]` | Messages bruts, avec bruit, non filtrés | `capture/raw/` | Scripts sources |
| **Gist** | `[[gist]]` seulement | Observation qualitative, 3-5 phrases, nettoyée | `capture/gists/` | Passe de nettoyage Otis |

Les deux partagent `version_schema = "v1"`. Le gist est **issu** d'une ou plusieurs traces ; le champ `archive` dans l'en-tête gist référence les fichiers traces sources.

---

## 1. Format Raw — `[session_capture]` + `[[trace]]`

Produit par les adaptateurs sources (ex: `otis-session-reader.py`). Capture brute sans interprétation. Destiné à la passe de nettoyage d'Otis.

```toml
[session_capture]
version_schema = "v1"
timestamp_capture = 1787050940
profile = "manny"
session_id = "20260818_045837_ded4b6d2"
traces_count = 12

[[trace]]
id = "trace-manny-20260818-001"
timestamp = 1787049200
type = "decision"
raw = "Texte original du message — strictement textuel, pas de reformulation"

# Recommandés
raw_type = "decision"
source = "session:manny/20260818_045837_ded4b6d2"
status = "provisoire"
confidence = 0.85

# Optionnels
tags = ["backfill", "session:manny"]
routing = "humain"
capture_point = "backfill-p1"
parent_id = "null"
message_id = 4291
```

### Champs `[session_capture]`

| Champ | Type | Description |
|---|---|---|
| `version_schema` | string | `"v1"` — version partagée avec le format gist |
| `timestamp_capture` | int | Unix timestamp de l'extraction |
| `profile` | string | Profil Hermes source (manny, bianca, etc.) |
| `session_id` | string | ID de session Hermes (traçabilité) |
| `traces_count` | int | Nombre de traces dans le fichier |

### Champs `[[trace]]`

| Champ | Type | Requis | Description |
|---|---|---|---|
| `id` | string | **Oui** | Identifiant unique. Convention : `trace-{profil}-{session_prefix}-{seq}` |
| `timestamp` | int | **Oui** | Unix timestamp du message original |
| `type` | string | **Oui** | Type de trace (voir enum) |
| `raw` | string | **Oui** | Texte original. Strictement textuel, pas de reformulation |
| `raw_type` | string | Recommandé | Sous-type : `narrative` / `analyse` / `meta` / `decision` |
| `source` | string | Recommandé | Provenance : `session:{profile}/{session_id}` |
| `status` | string | Recommandé | Cycle de vie : `provisoire` (défaut) / `valide` / `archive` |
| `confidence` | float | Recommandé | Confiance automate (0.0 – 1.0). Défaut : `0.5` |
| `tags` | array | Optionnel | Tags libres |
| `routing` | string | Optionnel | Résultat routage : `automate` / `humain` / `intermediaire` |
| `capture_point` | string | Optionnel | Phase du protocole ayant généré la trace |
| `parent_id` | string | Optionnel | ID de trace parente (chaînage). `"null"` si aucune |
| `message_id` | int | Optionnel | ID du message dans la DB Hermes |

---

## 2. Format Gist — `[[gist]]`

Produit par la passe de nettoyage d'Otis. Destiné à la cérémonie de swipe.

```toml
[gist_session]
version_schema = "v1"
timestamp_distillation = 1787296500
timestamp_capture = 1787295600
profile = "otis"
archive = "capture/raw/2026-08-20-manny-traces.toml"
traces_source = ["capture/raw/2026-08-20-manny-script-traces.toml"]
traces_raw_count = 71
gists_count = 8
ingested = false

[[gist]]
id = "gist-20260820-001"
timestamp = 1787295600
type = "protocole"
titre = "hyperCampus installé — 9 outils Solid MCP"
validation = "pending"
raw = """Description qualitative de l'observation, 3-5 phrases max.
Archive : capture/raw/2026-08-20-manny-traces.toml
"""

# Recommandés
source = "session:manny/20260820_084638_175f4909"
raw_type = "analyse"
status = "provisoire"
confidence = 0.8

# Optionnels
tags = ["hypercampus", "solid"]
routing = "automate"
parent_id = null
note = ""
```

### Champs `[gist_session]`

| Champ | Type | Description |
|---|---|---|
| `version_schema` | string | `"v1"` — partagé avec le format trace |
| `timestamp_distillation` | int | Unix timestamp du moment de production des gists |
| `timestamp_capture` | int | Unix timestamp de la capture source |
| `profile` | string | Toujours `"otis"` |
| `archive` | string | Chemin vers le(s) fichier(s) trace source |
| `traces_source` | array | Liste des fichiers traces bruts utilisés |
| `traces_raw_count` | int | Nombre de traces brutes en entrée |
| `gists_count` | int | Nombre de gists produits |
| `ingested` | bool | `false` (défaut / absent) / `true` — marqué par Weaver après ingestion |

### Champs `[[gist]]`

| Champ | Type | Requis | Description |
|---|---|---|---|
| `id` | string | **Oui** | Identifiant unique. Convention : `gist-{date}-{seq}` |
| `timestamp` | int | **Oui** | Unix timestamp du moment original (tri SPARQL) |
| `type` | string | **Oui** | Type de gist (même enum que les traces) |
| `titre` | string | **Oui** | Titre court, descriptif |
| `validation` | string | **Oui** | `"pending"` (défaut) / `"validated"` / `"rejected"` — statut porté par Valisette (3 valeurs depuis le 30 août 2026 ; voir §4 pour `anagnorisis`, qui n'en fait plus partie) |
| `raw` | string | **Oui** | Description qualitative, 3-5 phrases. Archive les sources |
| `source` | string | Recommandé | Provenance : `session:{profile}/{session_id}` |
| `raw_type` | string | Recommandé | Sous-type : `narrative` / `analyse` / `meta` / `decision` |
| `status` | string | Recommandé | Cycle de vie : `provisoire` / `valide` / `archive` |
| `confidence` | float | Recommandé | Confiance automate (0.0 – 1.0) |
| `tags` | array | Optionnel | Tags libres (pipeline, jamais écrits par Valisette) |
| `routing` | string | Optionnel | `automate` / `humain` / `intermediaire` |
| `parent_id` | string | Optionnel | ID de trace parente. `null` si aucune |
| `note` | string | Optionnel | Note ajoutée par Nicolas lors du swipe (Valisette) |
| `triage_flags` | array | Optionnel | Extensions libres Valisette : `["revisit", "priority", "anagnorisis"]` — **Weaver doit lire `anagnorisis` ici depuis le 30 août 2026** (voir §4 et le journal de changements) ; les autres valeurs restent ignorées par Weaver |

---

## 3. Correspondance trace → gist

Les champs communs sont compatibles par nom et par type, ce qui permet la traçabilité :

| Champ trace | Champ gist | Correspondance |
|---|---|---|
| `trace.id` | `raw` (archivé) | Référence dans le corps du gist |
| `trace.timestamp` | `gist.timestamp` | Conservé à l'identique |
| `trace.type` | `gist.type` | Conservé ou reclassifié par Otis |
| `trace.source` | `gist.source` | Conservé |
| `trace.raw_type` | `gist.raw_type` | Conservé |
| `trace.confidence` | `gist.confidence` | Peut être ajusté par Otis |
| `trace.tags` | `gist.tags` | Fusionné |
| `trace.routing` | `gist.routing` | Conservé |
| `trace.parent_id` | `gist.parent_id` | Conservé |
| — | `gist.titre` | **Nouveau** — ajouté par la passe de nettoyage |
| — | `gist.validation` | **Nouveau** — `"pending"` jusqu'au swipe, porté à `"validated"` / `"rejected"` par Valisette |
| — | `gist.note` | **Nouveau** — ajouté par Nicolas au swipe |
| — | `gist.triage_flags` | **Nouveau** — extensions libres Valisette, ignorées par Weaver |
| — | `[gist_session].ingested` | **Nouveau** — `false` (ou absent) jusqu'à l'ingestion Weaver, puis `true` |

Les champs internes à la trace (`message_id`, `capture_point`, `session_capture`) ne remontent pas dans le gist — ils sont dans la chaîne d'archive via `[gist_session].archive`.

---

## 4. Anagnorisis 🏛️

> *"Le passage de l'ignorance à la connaissance."* — Aristote, *Poétique*
>
> **Changement du 30 août 2026 :** anagnorisis est un **tag dans
> `triage_flags`**, pas un statut de `validation`. Ce champ avait déjà
> oscillé flag → statut → flag → statut avant de se figer sur "statut" lors
> d'une vérification contre cette même section (voir story 7.15,
> "Spec Change Log", 26 août). La récurrence du flip-flop était le signal :
> forcer un moment de reconnaissance à occuper le même champ que la direction
> du swipe était la mauvaise forme depuis le début. Anagnorisis marque un
> déclic *en plus de* valider ou rejeter, pas *à la place de* — exactement
> comme revisit/priority.

L'anagnorisis est un **tag de triage** posé par Nicolas dans le swipe. Il marque un moment de **reconnaissance soudaine** — un insight qui change la compréhension. Le geste : tapoter 💡 dans le bandeau (comme revisit/priority), puis swiper dans le sens que le gist mérite. Le tag part dans `triage_flags` avec ce swipe ; `validation` reste `validated` ou `rejected`, jamais une 3ᵉ valeur pour ceci.

```toml
[[gist]]
id = "gist-20260820-003"
timestamp = 1787296000
type = "apprentissage"
titre = "12 meridiens = processus, pas agents"
validation = "validated"
triage_flags = ["anagnorisis"]      # ← tag, indépendant de la direction du swipe
note = "C'est le moment où j'ai compris la différence fondamentale"
```

C'est un tag que **toi seul poses**, dans le swipe, parce que toi seul sais ce qui a été un vrai déclic dans ta journée. L'automate ne peut pas le détecter — et c'est voulu.

Dans le graphe final (Oxigraph), les triples marqués `otis:anagnorisis true` auront toujours un poids plus élevé pour les queries de synthèse — ce comportement de pondération, côté requête, ne change pas. Ce qui change est la source : Weaver doit désormais lire l'appartenance à `triage_flags` plutôt que `validation == "anagnorisis"`. Voir la note de handoff en fin de fichier pour la compatibilité avec les gists déjà swipés sous l'ancien contrat.

---

## 5. Enum des types (commun aux deux formats)

| Type | Description | Routage | Confiance auto |
|---|---|---|---|
| `decision` | Décision engageante | HUMAIN | 30-65% |
| `apprentissage` | Leçon tirée, observation structurée | INTERMÉDIAIRE | 65-80% |
| `signal_faible` | Observation non confirmée, hypothèse | AUTOMATE | 65-75% |
| `protocole` | Description de procédure, implémentation | AUTOMATE | 75-80% |
| `frontiere` | Analyse de la limite automate/humain | HUMAIN | ~50% |
| `meta` | Trace sur la trace, gouvernance, pipeline | HUMAIN | 55-70% |

---

## 6. Cycle de vie complet (format par format)

```
Capture brute                        Passe de nettoyage              Swipe                    Weaver
────────────                         ─────────────────               ─────                    ────
[[trace]]                            [[gist]]                         validation               ingestion
  type, raw, confidence              type, titre, raw                  validated / rejected     SPARQL INSERT
  status="provisoire"                validation="pending"              triage_flags:            → Oxigraph
  routing=auto/humain                status="provisoire"                revisit/priority/        ↓
                                                                          anagnorisis
        │                                  │                              │                [gist_session].ingested = true
        │                                  │                              │
        ▼                                  ▼                              ▼
 capture/raw/                     capture/gists/YYYY-MM-DD.toml    PATCH in-place            (fichier mis à jour
 (toujours là, jamais écrasé)     (groupe, non modifié par Otis)   (validation du gist)       sur le pod)
```

Le fichier gist est **modifié en place** par Valisette (PATCH du champ `validation`) puis par Weaver (ajout de `ingested = true`). Le fichier raw n'est **jamais modifié** — Règle 2 garantie.

---

## 7. Règle de routage

```toml
[regle_routage]
version = "v1"
source = "nicolas"
maintenue_par = "nicolas"
appliquee_par = "agent_automatique"

[[categories_routage]]
categorie = "automate"
types = ["technique", "protocole", "signal_faible"]
destination = "rate"
confiance_min = 0.75

[[categories_routage]]
categorie = "intermediaire"
types = ["apprentissage"]
destination = "rate"
balise = "suggest"
confiance_min = 0.65

[[categories_routage]]
categorie = "humain"
types = ["decision", "frontiere", "strategique", "meta"]
destination = "attente-humain"
confiance_max = 0.70
```

---

## 8. Handoff — anagnorisis flag→statut→flag, pour Manny (30 août 2026)

**Ce qui change :** `anagnorisis` n'est plus une 4ᵉ valeur de `validation`.
`validation` redevient 3-way (`pending`/`validated`/`rejected`). Le tag vit
maintenant dans `triage_flags`, aux côtés de `revisit`/`priority` — voir §4
pour le pourquoi (le champ avait déjà flip-floppé plusieurs fois ; le
récidive était le signal que "statut de validation" était la mauvaise forme,
pas un accident isolé).

**Ce qui NE change pas :** la sémantique de pondération côté requête. Un gist
marqué anagnorisis doit toujours produire une pondération plus élevée dans
Oxigraph (`otis:anagnorisis true` ou équivalent) — seule la source de lecture
change côté Weaver.

**Action requise côté ingestion (Weaver) :**

```diff
- is_anagnorisis = (gist.validation == "anagnorisis")
+ is_anagnorisis = "anagnorisis" in gist.get("triage_flags", [])
```

Et `gist.validation` ne doit plus jamais être comparé qu'à `"pending"` /
`"validated"` / `"rejected"` — un `"anagnorisis"` ne sera plus produit par de
nouveaux swipes, mais voir la note de compatibilité ci-dessous.

**⚠️ Compatibilité — gists déjà swipés avant ce changement :** Valisette est
en usage réel depuis fin août 2026 (dogfooding mobile). Il est possible que
des fichiers `capture/gists/*.toml` sur le pod contiennent déjà des gists
avec `validation = "anagnorisis"` écrits par l'ancienne version, **pas encore
ingérés par Weaver** (`[gist_session].ingested = false`). Avant de déployer le
Weaver mis à jour :

1. Vérifier s'il existe des fichiers non-ingérés contenant
   `validation = "anagnorisis"` sur le pod.
2. Si oui : soit les migrer à la main (`validation` → `validated` ou
   `rejected` selon ce que le swipe voulait vraiment dire, plus
   `triage_flags = ["anagnorisis"]`), soit faire lire à Weaver **les deux
   formes** en transition (`validation == "anagnorisis"` OU
   `"anagnorisis" in triage_flags`) jusqu'à ce que le pod soit propre.
3. Cette note peut être supprimée du fichier une fois la transition terminée.

**Sur le chemin canonique du fichier :** l'en-tête de ce document déclare
`references/schema-v1.md` (partagé) comme source canonique, mais ce chemin
n'existe pas dans le dépôt `pocpod0` — seule la copie sous `valisette/`
existe ici. Si `references/schema-v1.md` existe ailleurs (dépôt de Manny, ou
un autre dépôt partagé), il faut soit y répercuter ce même changement, soit
clarifier laquelle des deux copies fait foi.
