# KOR-NEXUS 1.20.0 — CI-Startanleitung

Status: **Änderungen auf einem separaten GitHub-Branch vorbereitet; der PR-CI-Lauf muss die neue Pipeline noch bestätigen.** Es wird kein grüner Status vorweggenommen.

## Pipeline-Aufbau

Die Workflow-Datei `.github/workflows/release.yml` definiert drei getrennte Jobs:

1. **Portable quality gates** (Ubuntu): Python 3.12 und Node.js 22; `bash scripts/ci.sh quick`; Backend-Unit-Tests; Prüfsummen, Integrität und erforderliche Einträge des reproduzierbaren Quellarchivs; Quellartefakte werden nur nach erfolgreichem Job hochgeladen.
2. **Browser QA and user installation integration test** (Ubuntu): installiert Playwright/Chromium und führt Browser-QA sowie den isolierten Benutzer-Installationstest separat mit jeweils 120 Sekunden Prozesslimit aus. Der Job besitzt zusätzlich ein Gesamtlimit von 15 Minuten.
3. **Native Arch Linux package build and isolated install test** (Arch-Linux-Container): baut als unprivilegierter Benutzer, prüft Paketmetadaten und Paketdateiliste und testet die Installation nur innerhalb des wegwerfbaren Containers. Gesamtlimit: 35 Minuten.

Alle Jobs erhalten nur `contents: read`. GitHub-Actions wird mit auf konkrete Commit-SHAs fixierten Actions ausgeführt. Der Workflow erstellt keine Releases oder Tags und führt keine Deployments aus. Es werden keine Secrets benötigt.

## Lokale Prüfungen

Im Projektstamm:

```bash
bash -n scripts/ci.sh scripts/release-check.sh scripts/test-installation.sh scripts/test-built-package-installation.sh
python3 -m py_compile core/server.py core/test_server.py scripts/qa-preview-playwright.py scripts/create-source-archive.py scripts/verify-built-package.py
node --check web/app.js
python3 -m unittest -v core.test_server
bash scripts/ci.sh quick
python3 scripts/qa-preview-playwright.py
bash scripts/test-installation.sh
```

Die Browserprüfung setzt Playwright und Chromium voraus. Der native Paketbau erfordert eine Arch-Linux-Umgebung mit `pacman` und `makepkg`:

```bash
bash scripts/build-arch-package.sh
```

Der Befehl baut standardmäßig ein Paket, installiert es nicht auf dem persönlichen Host. Der CI-Installationstest läuft nur innerhalb eines wegwerfbaren Arch-Containers.

## Zeitlimits und Archivprüfung

Für `scripts/release-check.sh full` gelten folgende konfigurierbare Prozesslimits:

- `KOR_BROWSER_QA_TIMEOUT` — Standard: 120 Sekunden.
- `KOR_INSTALL_TEST_TIMEOUT` — Standard: 120 Sekunden.

Die Archivprüfung verwendet `removeprefix('./')`, damit gültige Einträge wie `.github/workflows/release.yml` nicht fälschlich verändert werden. Ein Zeitlimit begrenzt Hänger, behebt aber nicht automatisch deren Ursache.

## Remote-Status und Sicherheitsgrenzen

Die Änderung liegt in einem separaten Branch und soll per Pull Request geprüft werden. Der Workflow wird durch den PR ausgelöst; es wurde kein manueller Workflow-Dispatch ausgelöst. **Ergebnisse gelten erst dann als bestätigt, wenn der zu diesem Branch gehörende Actions-Lauf abgeschlossen ist.**

Keine Zugangsdaten oder Secrets wurden hinzugefügt. Die Pipeline besitzt keine Schreibberechtigungen auf das Repository. Es erfolgen keine automatische Veröffentlichung und kein automatisches Zusammenführen.
