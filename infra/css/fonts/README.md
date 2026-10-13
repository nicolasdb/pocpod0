# Fonts for the identity pages

Self-hosted so the pages make no request to a third party (the brief forbids
Google Fonts). Latin subset only: it covers English, French, Dutch and German.
Served at `/fonts/…` by the `PodFontsAsset` folder entry in `../config.json`.

| File | Family | Weight | Role |
|---|---|---|---|
| `lexend-latin-{400,500,600}-normal.woff2` | Lexend | 400, 500, 600 | headings, labels, buttons |
| `atkinson-hyperlegible-latin-{400,700}-normal.woff2` | Atkinson Hyperlegible | 400, 700 | body text |
| `jetbrains-mono-latin-{400,500}-normal.woff2` | JetBrains Mono | 400, 500 | WebIDs, domain, kickers |

Source: the `@fontsource/*` 5.3.0 npm packages. Licence: SIL Open Font License
1.1, one copy per family in `OFL-*.txt`.
