# CI-Startanleitung für KOR-NEXUS 1.20.0

Status: **REMOTE-CI OFFEN — Repository identifiziert, Remote-Workflow fehlt; kein Workflow-Lauf gestartet.**

## Aktueller Repository-Befund

Das passende Repository ist [`oORaxaOo/KOR-NEXUS`](https://github.com/oORaxaOo/KOR-NEXUS), Standardbranch `main`. Der GitHub-Connector meldet Admin-/Push-Berechtigungen für die verbundene Identität. Das Remote-README enthält nur einen kurzen Platzhaltertext; `.github/workflows/release.yml` ist im Remote-Branch nicht vorhanden (404). Die lokale Projektkopie `/mnt/data/kor-nexus-work/kor-work` besitzt kein `.git`-Verzeichnis und keinen konfigurierten Remote. Daher wurde nichts übertragen, kein Workflow gestartet und nichts veröffentlicht. Mit den verfügbaren Connector-Funktionen konnte kein belastbarer Status vorhandener Remote-Workflow-Läufe bestätigt werden.

## Sicherer nächster Schritt

1. Den Remote-Inhalt und die Zielstruktur erneut prüfen.
2. Die lokale Projektkopie samt Workflow über einen kontrollierten, überprüfbaren Weg in einen eigenen Branch einbringen; nicht ungefragt auf `main` pushen.
3. Erst nach ausdrücklicher Freigabe den Workflow aktivieren und auf einem geprüften Branch oder Pull Request starten.
4. `Portable quality gates` und `Native Arch Linux package build` sowie ihre Artefakte kontrollieren.
5. Einen grünen lokalen Lauf nicht als Ersatz für Remote-CI oder einen nativen Arch-Build ausgeben.

## Fehlerverhalten und Veröffentlichung

Der lokale Workflow liegt unter `.github/workflows/release.yml`. Er hat auf Workflow-Ebene nur `contents: read`; der Artefakt-Upload ist an vorherige erfolgreiche Prüfungen gebunden und verwendet `if-no-files-found: error`. Es gibt keinen automatischen GitHub-Release- oder Tag-Push. Das sind Eigenschaften des lokalen Workflow-Dateistands; sie wurden nicht durch einen Remote-Lauf bestätigt.

In der aktuellen Umgebung fehlen `makepkg` und `pacman`, daher wurde kein nativer Arch-Paketbau ausgeführt. Vor jeder Remote-Änderung sind Ziel-Repository und gewünschter Übertragungsweg ausdrücklich zu bestätigen.
