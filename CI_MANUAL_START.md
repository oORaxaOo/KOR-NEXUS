# KOR-NEXUS — CI-Status und Betriebshinweise

Stand: 2026-10-16 · Version 1.20.0

## Repository

- Repository: [`oORaxaOo/KOR-NEXUS`](https://github.com/oORaxaOo/KOR-NEXUS)
- Arbeitsbranch: [`transfer/kor-nexus-1.20.0`](https://github.com/oORaxaOo/KOR-NEXUS/tree/transfer/kor-nexus-1.20.0)
- Release-Workflow: [`.github/workflows/release.yml`](https://github.com/oORaxaOo/KOR-NEXUS/blob/transfer/kor-nexus-1.20.0/.github/workflows/release.yml)
- Aktuelle Ergebnisse: [GitHub Actions für den Transfer-Branch](https://github.com/oORaxaOo/KOR-NEXUS/actions?query=branch%3Atransfer%2Fkor-nexus-1.20.0)

Die Bereinigung und Wiederherstellung wurde im Transfer-Branch ausgeführt. `main` wurde von diesen Transfer-Commits nicht direkt verändert. Ursprüngliche Upload-Archive bleiben unter `archive/legacy-uploads/` erhalten.

## Pipeline

Die Release-Pipeline besteht aus zwei Jobs:

1. **Portable quality gates:** installiert Python 3.12, Node.js und Playwright/Chromium; führt `bash scripts/ci.sh full` aus und lädt Quellarchiv, Prüfsummen und PKGBUILD erst nach erfolgreichem Gate als CI-Artefakt hoch.
2. **Native Arch Linux package build:** baut das Paket in einem kurzlebigen Arch-Linux-Container, prüft Metadaten und Paketdateiliste, installiert es ausschließlich in diesem wegwerfbaren Container, testet Start/Health/Einzelinstanz/Stop und prüft den Erhalt der Nutzerdaten nach Entfernung.

Der Workflow besitzt auf Workflow-Ebene `contents: read`. Er erstellt keine GitHub-Releases, veröffentlicht keine Tags und pusht keine Änderungen aus den Jobs. Der Arch-Paketbau wird als unprivilegierter Benutzer ausgeführt; der Paket-Integrationstest läuft als Root nur innerhalb des isolierten Arch-CI-Containers.

## Bereits bestätigte Prüfungen

- 29/29 Kern-API-Unit-Tests bestanden.
- `bash scripts/ci.sh quick` bestanden; Versionskonsistenz, JavaScript-/Python-Syntax, Paketdateiliste und reproduzierbares Quellarchiv wurden geprüft.
- Der isolierte Benutzer-Installationstest bestand mit Pfaden, die Leerzeichen enthalten, einem absichtlich belegten Standard-Port, Health-Check, Doppelstart, Stop und Deinstallation bei erhaltenen Nutzerdaten.
- Die Offline-Weltkarte wurde mit 177 Features, 364.876 Byte und SHA-256-Prüfsumme validiert.
- Der native Arch-Paketbau und sein isolierter Installationstest bestanden in [diesem Actions-Lauf](https://github.com/oORaxaOo/KOR-NEXUS/actions/runs/38965584870).

Der neueste Workflow-Lauf bleibt für den finalen Release-Status maßgeblich; ein erfolgreiches früheres Teilresultat darf nicht als grünes Ergebnis eines neueren vollständigen Laufs dargestellt werden. Siehe die oben verlinkte Liste der Actions-Läufe.

## Lokale Prüfungen

Im Projektstamm:

```bash
python3 -m unittest -v core.test_server
bash scripts/ci.sh quick
bash scripts/test-installation.sh
```

Für den vollständigen portablen Release-Gate werden Playwright und Chromium benötigt:

```bash
bash scripts/ci.sh full
```

Ein nativer Paketbau benötigt eine Arch-Linux-Umgebung mit `makepkg` und `pacman`:

```bash
bash scripts/build-arch-package.sh
```

Das Skript baut standardmäßig, ohne das Paket auf dem Host zu installieren. Die ausdrücklich optionale Variante `bash scripts/build-arch-package.sh --install` ist für ein bewusst gewähltes persönliches Zielsystem gedacht und wird nicht von der CI-Pipeline verwendet.

## Vorschaubilder

Die Dateien `preview/*.png` sind historische visuelle Referenzen aus den zuvor hochgeladenen Archiven und keine aktuellen Prüfergebnisse. Neue Desktop-/Mobil-Screenshots mit Playwright und Chromium erzeugen:

```bash
python3 scripts/qa-preview-playwright.py
```
