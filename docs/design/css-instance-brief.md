# Brief Claude Design — pages d'une instance Solid (CSS 7.2)

## Objet
Maquetter les pages servies par le serveur Solid (Community Solid Server) : c'est le premier contact d'une personne avec son pod. Il faut **deux habillages sur une même structure** :

- **Pod** : l'habillage générique de pod.nicolasdb.eu, calme et lisible, dans l'esprit solid-kit.
- **Maps of Making** : l'habillage de l'instance dédiée Maps of Making, en style riso.

La structure HTML (header, main, footer) et les formulaires sont communs aux deux. Seuls changent les tokens, les polices et les textes.

## Contraintes techniques (non négociables)
- Les formulaires sont générés par le serveur. Les champs, ids et boutons existent déjà : on stylise, on n'ajoute pas de champ.
- Une seule colonne, 560px max, mobile dès 360px.
- Contraste WCAG AA (4.5:1) pour le texte, focus visible sur chaque élément interactif.
- Pas de JS décoratif. Polices hébergées sur le serveur (woff2), pas de Google Fonts.
- Chrome commun : un header (logo, nom, sous-titre avec le domaine), le contenu, puis un footer (une phrase).

## Markup réel
Le HTML servi en prod est dans `markup/` (welcome, login, register, forgot, account) et les templates surchargés aussi (`consent.html.ejs`, `create-pod.html.ejs`). Les maquettes doivent respecter cette structure : `fieldset > legend > ol > li > label + input`, `p.actions > button`, `ul.actions > li > a.link`, `p.error`.

## Écrans à maquetter (chacun dans les deux habillages)
1. **Welcome** (racine du serveur) : ce qu'est ce serveur, créer un compte, se connecter.
2. **Login** : email + mot de passe ; liens « mot de passe oublié » et « créer un compte ».
3. **Register** : email, mot de passe, confirmation.
4. **Forgot / reset password** : email, puis le message de confirmation.
5. **Consent (OIDC)** : « l'application X demande l'accès à votre pod », avec le WebID utilisé, les boutons Autoriser / Refuser et l'option « se souvenir ». C'est l'écran le plus sensible : il doit montrer clairement qui demande quoi.
6. **Account overview** (`/.account/`) : la liste des pods, des WebID, des méthodes de connexion et des tokens clients.
7. **Create pod** : le nom du pod et l'aperçu de l'URL obtenue.
8. **Lecture d'un .md public** : un frontmatter affiché en grille (titre, auteur, date, sujets), puis la prose.
9. **États** : une erreur de formulaire, et l'écran « Your sign-in for this app is out of date » (récupération de session).

## Habillage Pod (existant, à affiner)
- Palette daylight : fond `#f6f4ef`, panneau `#fbfaf7`, texte `#26241f`, texte atténué `#6d6757`, filets `#e7e2d6`, accent sauge `#3d6b52` / `#eef3ef`. Prévoir aussi la variante sombre « ink » (Pod uniquement).
- Polices : Lexend (titres et UI), Atkinson Hyperlegible (texte), JetBrains Mono (identifiants, WebID).
- Ton : sobre, aéré, pas de carte flottante.
- Textes actuels : header « Your pod », footer « Your space on the web — you hold the key. »

## Habillage Maps of Making (nouveau)
- Source : `maps_of_making/web/maps-of-making.html`.
- Palette : papier `#f7f2e7`, encre `#1a1a1a` / `#2a2a2a`, texte atténué `#6a6357`, `#bfb7a4` pour les éléments à peine visibles, rouge riso `oklch(62% 0.18 25)`.
- Polices : Caveat (titres manuscrits), Inter Tight (texte), JetBrains Mono (petits labels en majuscules, espacés), Special Elite (machine à écrire, en accent).
- Signature visuelle :
  - séparateurs en pointillés `1px dashed` ;
  - badges avec une bordure de 1,5px en `currentColor` ;
  - bouton principal plein, encre sur papier ;
  - pastilles façon « sticker » ;
  - léger décalage d'impression riso possible, mais sans nuire au contraste.
- **Papier seul, pas de mode sombre** : cohérent avec le thème « carte ».
- Ton des textes : communauté de makers. On rejoint une carte des lieux et des savoir-faire, et on y garde ses données chez soi.

## Textes à proposer (à valider)
Pour chaque habillage :
- titre et sous-titre du header ;
- phrase du footer ;
- texte de la page Welcome ;
- intro au-dessus du formulaire de login ;
- texte explicatif du consent ;
- intro de la page compte.

Langue : **EN uniquement pour le MVP**. Le multilangue (EN/FR/NL, DE) est reporté : prévoir seulement que les textes puissent s'allonger d'environ 30 % (NL/DE) sans casser la mise en page.

## Livrables attendus
- Une maquette par écran et par habillage, en desktop et en mobile.
- Une planche de tokens par habillage (couleurs, typo, espacements, bordures), nommée selon les slots de solid-kit (`core.css`).
- Les états focus, erreur et désactivé pour les champs et les boutons.

## Prompt prêt à coller dans Claude Design
> Design the identity pages of a Solid pod server (Community Solid Server) in two skins sharing one HTML structure. Single column, max 560px, mobile from 360px, WCAG AA, visible focus, self-hosted fonts, English copy.
> Skin A "Pod": calm, airy daylight palette (bg #f6f4ef, panel #fbfaf7, text #26241f, muted #6d6757, rule #e7e2d6, sage accent #3d6b52 / soft #eef3ef), Lexend + Atkinson Hyperlegible + JetBrains Mono; plus a dark "ink" variant.
> Skin B "Maps of Making": risograph paper map look, paper only (no dark mode): paper #f7f2e7, ink #1a1a1a, muted #6a6357, faint #bfb7a4, riso red oklch(62% 0.18 25); Caveat for headings, Inter Tight body, JetBrains Mono uppercase spaced labels, Special Elite accents; 1px dashed rules, 1.5px currentColor badge borders, solid ink primary button, sticker-like chips. Tone: a community of makers mapping places and know-how, keeping their data in their own pod.
> Screens (each in both skins, desktop + mobile): Welcome, Log in, Sign up, Forgot/reset password, OIDC Consent ("App X wants access to your pod", WebID shown, Allow/Deny, remember), Account overview (pods, WebIDs, login methods, client tokens), Create pod (name + resulting URL preview), Public markdown reading (front-matter grid then prose), error state, "Your sign-in for this app is out of date" recovery.
> Forms are server-generated: keep the markup `fieldset > legend > ol > li > label + input`, `p.actions > button`, `ul.actions > li > a.link`, `p.error` — style only, add no fields. Propose English copy for header, footer, welcome, login intro, consent explanation, account intro. Deliver a token sheet per skin (color, type, spacing, borders) and focus/error/disabled states.

Joindre : les fichiers de `markup/`, et des captures de `maps_of_making/web/maps-of-making.html` comme référence du style riso.

## Avancement (2026-10-13)
- Fait : brief, markup réel des pages (`markup/`), décisions (EN seul MVP, riso papier seul, pas de mode sombre riso).
- Accès Claude Design OK (`/design-login`) ; projets : Classical, Industry, Design System (vide). Pas encore de design system « Solid instances ».
- Prochain : `/design-sync` (tokens + composants kit → projet Claude Design), mockups par Nicolas, retour ici, puis refactor solid-kit (identity.css + skins + copy + export script).
- Reporté : multilangue (EN/FR/NL/DE, config par instance, bascule côté client via `data-i18n`), infra VPS Maps of Making (composes séparés par fonction, TBD).
