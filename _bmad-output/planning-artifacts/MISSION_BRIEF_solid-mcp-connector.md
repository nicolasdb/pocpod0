# Mission Brief — Connecteur MCP Solid Pod

**Quest** : B — Infrastructure technique (Git + Obsidian → Pods)
**Mission** : Déployer un connecteur MCP auto-hébergé permettant à Claude (claude.ai) de lire/écrire dans un pod Solid et de consulter les permissions WAC.
**Handoff** : session Claude chat → Claude Code (accès VPS)
**Date** : 2026-07-30
**Statut** : prêt à implémenter

---

## 1. Contexte

HyperScope migre son infrastructure de connaissance vers des pods Solid. Un provider CSS auto-hébergé est déjà en production sur `pod.nicolasdb.eu`, avec plusieurs pods actifs (`hyperscope_ndb`, `nicolas_claude`, `nicolas`).

L'objectif de cette mission est de rendre ces pods accessibles depuis une conversation claude.ai — en lecture, écriture, et consultation des permissions — sans jamais confier à l'agent le contrôle du pod de données.

Principe directeur (*walking the talk*) : HyperScope doit bénéficier de ses propres outils en interne avant de les proposer à Singelijn, puis à des partenaires plus larges. Ce connecteur est le premier *walking skeleton* vertical de la Quest B : une tranche mince qui fonctionne de bout en bout avant tout élargissement.

### Réutilisabilité au-delà de claude.ai

Le serveur MCP issu de T1/T3 n'est pas spécifique à Claude : c'est un serveur MCP standard, joignable par n'importe quel client MCP. Si un agent basé sur Hermes embarque un client MCP, il peut pointer vers la même URL (avec son propre chemin/token, comme un membre de l'équipe). Aucun travail supplémentaire n'est requis pour ça — c'est la nature du protocole.

Si le harnais Hermes ne parle pas MCP, `src/podClient.js` et `src/wacManager.js` restent utilisables directement comme bibliothèque Node.js, indépendamment du transport — c'est pour ça qu'ils sont restés découplés du serveur MCP dans `src/mcp-server.js`.

### Pourquoi un connecteur et pas un simple Skill

Vérifié empiriquement en session : le sandbox d'exécution de code de claude.ai ne peut pas atteindre le pod.

```
curl https://pod.nicolasdb.eu/   → HTTP 403, x-deny-reason: host_not_allowed
curl https://registry.npmjs.org/ → HTTP 200
```

Le réseau du sandbox est restreint à une liste blanche de dépôts de paquets, non configurable côté utilisateur. Un Skill exécutant du code ne pourra donc jamais joindre le pod depuis un chat.

Un connecteur MCP distant fonctionne à l'inverse : **Claude appelle le serveur depuis l'infrastructure d'Anthropic**, vers une URL publique. Le serveur tourne donc sur le VPS, où le réseau est ouvert. C'est la seule voie possible pour un lien live depuis claude.ai.

---

## 2. Definition of done

Un membre de l'équipe, sur plan Claude Pro, peut :

1. ajouter le connecteur via *Settings > Connectors > Add custom connector* ;
2. s'authentifier avec **son propre** token AGENT ;
3. depuis une conversation : lister, lire, écrire dans les conteneurs que son WebID a le droit de toucher ;
4. consulter les permissions WAC d'une ressource ;
5. **et rien de plus** — toute tentative hors de son périmètre WAC échoue proprement avec un message clair.

---

## 3. État actuel — ce qui existe

Un toolkit Node.js est fourni (`solid-pod-agent.zip`), validé hors-ligne mais **jamais exécuté contre un pod réel**.

| Fichier | Rôle | Statut |
|---|---|---|
| `src/auth.js` | login client-credentials → session | non testé en réseau |
| `src/podClient.js` | CRUD fichiers / datasets / conteneurs | charge correctement, non testé en réseau |
| `src/wacManager.js` | lecture/écriture permissions WAC | logique testée hors-ligne (7/7 assertions) |
| `src/onboarding.js` | bootstrap : OWNER accorde accès à l'AGENT | non testé |
| `src/whoami.js` | l'agent audite ses accès réels | non testé |
| `src/mcp-server.js` | serveur MCP **stdio** | à convertir en HTTP |
| `references/architecture-and-checklist.md` | décisions d'architecture | à jour |

### Confirmé
- `npm install` résout proprement : `@inrupt/solid-client@2.1.2`, `@inrupt/solid-client-authn-node@2.5.0`, `@modelcontextprotocol/sdk@1.30.0`.
- Toutes les fonctions de bibliothèque utilisées existent réellement dans les paquets installés (vérifié par introspection, pas par mémoire).
- La logique ACL produit l'état attendu : agent avec read/write sur conteneur + enfants, aucun `control`, owner conserve `control`, révocation propre.

### Non confirmé — à valider sur le VPS
- Tout appel réseau réel : login, lecture, écriture, écriture d'ACL.
- Le comportement exact de CSS sur la création d'une ACL absente.
- La disponibilité de l'authentification par **request headers** sur le plan Pro (voir T2).

---

## 4. Contraintes d'architecture — non négociables

Ces contraintes découlent de décisions prises en session. Ne pas les contourner pour simplifier l'implémentation ; si l'une d'elles bloque, remonter la question plutôt que de la lever.

### 4.1 Modèle à deux tokens

| Token | WebID | Détenteur | Usage |
|---|---|---|---|
| **OWNER** | `hyperscope_ndb` | l'humain seul | `onboarding.js`, exécuté à la main, une fois |
| **AGENT** | `nicolas_claude` | le serveur MCP | runtime |

Le token OWNER **ne doit jamais** être déployé avec le serveur, ni figurer dans un `.env` de production, ni être collé dans une conversation avec un agent. Le donner à un agent revient exactement au risque que ce modèle existe pour éviter : cet agent pourrait alors s'accorder n'importe quel accès et retirer les siens à l'humain.

Raison technique : seul un WebID détenant déjà `acl:Control` sur un conteneur peut modifier son ACL. L'agent ne peut donc pas s'auto-accorder l'accès. **C'est la propriété de sécurité, pas une contrainte à contourner.**

### 4.2 Un compte CSS par personne

Chaque membre de l'équipe crée **son propre compte** sur `pod.nicolasdb.eu`, puis à l'intérieur de son compte :
- son pod de données ;
- un second pod dédié à l'agent (motif `<prenom>_claude`) ;
- un token client-credentials associé au WebID du pod agent.

Ne pas héberger les pods de plusieurs personnes sur un compte partagé : le détenteur du mot de passe du compte peut générer un token pour n'importe lequel de ses WebID, donc accéder à toutes les données du compte. Pour une infrastructure de souveraineté des données, ce serait contradictoire. Nicolas est l'hébergeur, pas le propriétaire.

### 4.3 Périmètre de l'agent

- L'agent n'a **jamais** `acl:Control` sur un pod de données.
- Note : CSS accorde à chaque WebID le contrôle total sur *son propre* pod à la création. L'agent a donc `control` sur `<prenom>_claude/` par construction. C'est acceptable (c'est son espace de travail : journal d'audit, état mis en cache), mais rien de sensible ne doit y être stocké.
- Les grants sont scopés par conteneur, jamais à la racine du pod.
- Toujours utiliser `scope: 'both'` pour un conteneur, sinon l'agent peut lister le dossier sans pouvoir toucher son contenu.

### 4.4 Confirmation humaine avant écriture de permission

`solid_grant_access`, `solid_revoke_access` et `setPublicAccess` modifient qui voit quoi. Ces outils doivent être annotés comme destructifs/sensibles côté MCP, afin que le client demande une approbation explicite. Ne pas les rendre invocables silencieusement.

---

## 5. Tâches

### T1 — Convertir le transport stdio → Streamable HTTP
`src/mcp-server.js` utilise `StdioServerTransport`, qui ne fonctionne que pour un processus local. Basculer sur `StreamableHTTPServerTransport` derrière Express (ou équivalent).

Conserver le SDK MCP en **1.x**. Une v2 accompagne la spec 2026-07-28 et l'API change (`registerTool` notamment) ; la 1.x reste supportée en production plusieurs mois. Ne pas bumper sans vérifier la doc courante.

### T2 — Authentification par requête (multi-tenant) — non disponible pour le MVP
Objectif visé : le serveur ne détient plus une identité fixe dans `.env`, mais dérive l'identité **par requête** depuis les credentials fournis par l'appelant, via des en-têtes configurés à l'ajout du connecteur.

**Vérifié en session (2026-07-30) : absent.** La boîte de dialogue *Add custom connector* sur un compte Pro n'expose que `Name`, `Remote MCP server URL`, et sous *Advanced settings* : `OAuth Client ID` / `OAuth Client Secret` (pour un flow OAuth, pas l'injection d'un header statique). Pas de champ « Request headers ». Cette fonctionnalité mentionnée dans la doc Anthropic comme beta à déploiement progressif n'est donc pas disponible sur ce compte actuellement.

**Conséquence : T3 est la voie retenue pour ce MVP, pas un fallback.** Revoir T2 périodiquement (changelog Anthropic) — si le champ apparaît, la migration vers T2 est un gain net (plus besoin d'URLs secrètes par personne) et ne change rien à `wacManager.js`/`podClient.js`.

### T3 — Un endpoint par personne (voie retenue)
Exposer un chemin par membre (`/mcp/nicolas`, `/mcp/alice`), chacun lié côté serveur à son propre token AGENT, stocké hors du dépôt (variable d'environnement ou fichier de config non versionné).

À documenter honnêtement comme un compromis : la sécurité repose en partie sur le secret de l'URL en plus du token WAC. Chemins longs et non devinables (ex. un slug aléatoire, pas juste le prénom), jamais en clair dans un dépôt, un canal partagé, ou un message Slack. Prévoir une rotation simple (changer le slug) si une URL fuite.

### T4 — Déploiement VPS
- Reverse proxy + TLS sur un sous-domaine dédié (ex. `mcp.nicolasdb.eu`), **distinct** du domaine du pod.
- Service systemd, redémarrage automatique, logs sans secrets.
- Le serveur doit être joignable depuis les plages IP d'Anthropic. Si un pare-feu filtre l'entrant, ajouter ces plages en allowlist (voir la doc Anthropic sur les adresses IP).
- Session `keepAlive: true` pour un processus long ; `keepAlive: false` pour les scripts one-shot (`onboarding.js`, `whoami.js`).

### T5 — Durcissement
- Rate limiting sur l'endpoint MCP.
- Gestion explicite des 401 / 403 / 404 / 409 : ce sont des cas de routine, pas des exceptions. Les traduire en messages exploitables (« pas d'accès en écriture à ce conteneur ») plutôt que de laisser fuiter une stack trace.
- `.env` en `chmod 600`, hors git (`.gitignore` déjà en place).
- Journal d'audit : chaque lecture / écriture / changement de permission, avec identité, ressource, horodatage. Sert à la fois à vérifier le comportement de l'agent et à constituer la référence de transparence proposable à Singelijn.

### T6 — Vérification (dans cet ordre)
1. `npm run onboard` — dry run, avec les credentials OWNER, en local. Vérifier que les grants annoncés sont exactement ceux voulus.
2. `npm run onboard:apply` — écrit les ACL et relit chaque grant pour confirmation.
3. `npm run whoami` — avec les credentials AGENT. Doit montrer les accès attendus **et les refus attendus** (le pod de données à la racine, le pod d'une autre personne).
4. Depuis claude.ai avec le connecteur : lister un conteneur, écrire un fichier, le relire, consulter les permissions.
5. Test négatif : demander à Claude d'écrire dans un conteneur non accordé → doit échouer proprement.

Éditer `GRANTS` dans `onboarding.js` et `PROBES` dans `whoami.js` avant de lancer : les valeurs actuelles (`hyperscope_ndb/notes/`, `/inbox/`) sont des suppositions à remplacer par les conteneurs réels.

### T7 — Documentation d'onboarding équipe
Une page courte, non technique, couvrant : créer son compte CSS → créer son pod agent → générer son token AGENT → ajouter le connecteur dans Claude → accorder l'accès à ses propres conteneurs. Avec l'avertissement explicite : ne jamais partager le token OWNER, seulement l'AGENT.

---

## 6. Pièges connus

Découverts en session, à ne pas redécouvrir :

1. **`getAgentAccessAll` prend la ressource-avec-ACL**, pas l'ACL extraite. Lui passer `getResourceAcl(...)` lève `Cannot read properties of undefined (reading 'resourceAcl')`. Bug présent dans la première version du toolkit, corrigé.
2. **`createAclFromFallbackAcl` retourne déjà un ACL dataset** — ne pas enchaîner `getResourceAcl()` sur sa sortie.
3. **`createSolidDataset()` retourne un objet gelé** : l'affectation directe de propriété échoue silencieusement. Utiliser `Object.assign` (concerne surtout les harnais de test).
4. **ACL orpheline** : sauvegarder une ACL neuve sans que personne ne détienne `control: true` rend la ressource définitivement non administrable — même par le propriétaire. Toujours inclure l'owner avec `control: true` dans le lot qui crée une ACL.
5. **`scope: 'resource'` seul** sur un conteneur ne couvre pas ses enfants. Voir 4.3.
6. **CSS et le mode `create`** : CSS a historiquement exposé des modes (`create`, `delete`) au-delà des quatre de la spec WAC, avec des 403 surprenants à la création de ressource. Si une écriture échoue alors que l'ACL semble correcte, vérifier les logs serveur pour le mode réellement exigé.
7. **`@inrupt/solid-client` n'expose pas `./package.json`** dans ses `exports` — la lecture de version par `require()` échoue. Détail de diagnostic.

---

## 7. Hors scope de cette mission

- **ACP** — voir annexe. Reste sur WAC pour le MVP.
- **Multi-provider** : `auth.js` est spécifique au flow client-credentials de CSS. On assume que tous les pods sont sur `pod.nicolasdb.eu`.
- **Notifications** (WebSockets/WebSub) : l'agent agit sur demande, il ne surveille pas.
- **Versioning / sauvegarde** des ressources de pod — vrai manque face à Git+Obsidian, à traiter comme mission distincte avant que les pods ne contiennent quoi que ce soit d'irremplaçable.
- **Sift Pearl** et la classification en pearls : couche distincte, en aval.

---

## Annexe — Anticiper le passage à ACP

Le tableau de la situation est exact, avec une nuance : la trajectoire n'est plus aussi univoque que « WAC = legacy, ACP = futur ».

Une proposition de mai 2026 sur la spec Solid vise à faire de **WAC le socle obligatoire (MUST) et d'ACP une option (MAY)**, au motif que l'écosystème a majoritairement convergé vers WAC. En parallèle, WAC est passé en editor's draft 1.1.0 (avril 2026), introduisant l'autorisation conditionnelle et un mécanisme d'extension — ce qui réduit l'écart fonctionnel avec ACP. Côté CSS : WAC reste activé dans la plupart des configurations livrées, avec une intention affichée de basculer vers ACP à terme, en commençant par des avertissements dans les logs.

**Une correction à la recommandation « utiliser les universal access APIs ».** Directionnellement juste, mais l'API `@inrupt/solid-client/universal` a des bugs connus face aux serveurs WAC (notamment : lève une erreur au lieu d'initialiser une ACL absente) et Inrupt teste principalement contre ACP. Elle devient un bon choix *si* tu passes à ACP ; elle n'est pas fiable comme couche d'abstraction tant que tu es sur WAC. D'où le choix des API WAC-spécifiques dans `wacManager.js`.

### Ce que coûterait le basculement

- **`wacManager.js` : réécriture complète.** Ce n'est pas un changement d'API cosmétique. ACP remplace les documents `.acl` par des ACR contenant des Policies et des Matchers, avec une sémantique différente — notamment un **deny explicite** qui l'emporte sur allow, absent de WAC.
- **Les ACL existantes ne se convertissent pas automatiquement.** Basculer la configuration du serveur signifie que les `.acl` en place cessent d'être honorés → **risque réel de perte d'accès**. Prévoir : inventaire des ACL existantes, script de conversion, et test sur une instance jetable avant la production.
- **`controlRead` / `controlWrite`** sont deux modes distincts en ACP, là où WAC n'a qu'un `acl:Control`. Toute couche d'abstraction refusera des valeurs divergentes.
- **`podClient.js` n'est pas affecté** : la lecture/écriture de ressources est indépendante du mécanisme d'autorisation.

### Le gain qui justifierait la migration, pour ce cas d'usage précis

ACP permet de contraindre l'accès sur l'**identité du client** (l'application), pas seulement sur le WebID de l'agent. Aujourd'hui en WAC, un token AGENT qui fuite est utilisable depuis n'importe quelle application. En ACP, on peut exiger « ce WebID **et** ce client » — ce qui réduit considérablement la valeur d'un token volé.

Pour une infrastructure qui confie des credentials à des agents automatisés, c'est l'argument le plus solide en faveur d'ACP. À considérer comme la vraie raison de migrer, plutôt que le suivi de tendance.

**Recommandation** : rester sur WAC pour ce MVP, garder `wacManager.js` isolé derrière une interface stable (ce qu'il est déjà : `grantAccess` / `revokeAccess` / `listAgentsWithAccess` / `getAgentAccess`) afin qu'une implémentation ACP puisse s'y substituer sans toucher au reste. Traiter la migration comme une mission dédiée, avec sa fenêtre de test.
