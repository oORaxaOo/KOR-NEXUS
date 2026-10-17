# KOR-NEXUS 1.20.0 — CI-Workflow-Änderungen

## Status

Die Änderungen wurden auf dem separaten Branch `fix/ci-timeouts-docs-2026-10` vorbereitet. Sie sind nicht nach `main` gemergt. Die GitHub-Actions-Prüfung des Pull Requests ist der noch ausstehende Nachweis; dieser Bericht behauptet keinen erfolgreichen Remote-Lauf.

## Änderungen

- `.github/workflows/release.yml`: Die bisherigen Qualitäts-, Browser-/Installations- und Arch-Paketprüfungen sind in drei Jobs aufgeteilt. So lässt sich ein Browser-Hänger unabhängig von den portable Qualitätsprüfungen und dem nativen Paketbau erkennen.
- Jeder Job hat ein Gesamtzeitlimit. Browser-QA und Benutzerinstallation sind zusätzlich jeweils auf 120 Sekunden begrenzt.
- GitHub Actions werden auf konkrete Commit-SHAs festgelegt; Repository-Berechtigung bleibt `contents: read`. Keine Releases, Deployments oder Secrets.
- `scripts/release-check.sh`: Browser- und Installationstest erhalten konfigurierbare Zeitlimits (`KOR_BROWSER_QA_TIMEOUT`, `KOR_INSTALL_TEST_TIMEOUT`). Die TAR-Mitgliederprüfung verwendet `removeprefix('./')`, damit versteckte Pfade wie `.github/workflows/release.yml` korrekt erhalten bleiben.
- `CI_MANUAL_START.md`: Die Anleitung beschreibt nun alle drei Jobs, deren Limits und den tatsächlichen Status ohne vorweggenommenes CI-Ergebnis.

## Vorhandene lokale Testergebnisse aus dem vorherigen Prüfbericht

- `bash scripts/ci.sh quick`: bestanden.
- `python3 -m unittest -v core.test_server`: 29 Tests bestanden.
- `python3 scripts/qa-preview-playwright.py`: 19 Browser-/UI-Prüfungen in einem separaten Lauf bestanden.
- `bash scripts/test-installation.sh`: bestanden.
- Syntaxprüfungen für Shell, Python und JavaScript bestanden.
- Offline-Weltkarte: 177 GeoJSON-Features; Prüfsummen und Quellarchivintegrität geprüft.

Diese früheren lokalen Resultate sind keine Bestätigung für den neuen GitHub-Branch. Ein kombinierter lokaler Lauf von `scripts/ci.sh full` hing zuvor in der Browser-QA und überschritt sein äußeres Zeitlimit. Deshalb werden Browser- und Installationstest jetzt getrennt ausgeführt. Der Arch-Paketbau war lokal nicht verfügbar, da `makepkg` und `pacman` fehlten.

## Sicherheits- und Veröffentlichungsstatus

- Separate Branch-Änderungen; `main` bleibt unverändert, bis ein Pull Request geprüft und bewusst zusammengeführt wird.
- Kein manueller Workflow-Dispatch.
- Keine Secrets oder Zugangsdaten hinzugefügt.
- Kein Release und keine Veröffentlichung.
- Der native Paketbau und die CI-Ergebnisse müssen durch den zugehörigen GitHub-Actions-Lauf bestätigt werden.
