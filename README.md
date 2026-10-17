# KOR-NEXUS // COMMAND NEXUS

**KOR-NEXUS 1.20.0** ist eine lokal betriebene, SQLite-basierte Arbeitsumgebung für Atlas-Notizen, Projekte, Archivwissen, Szenarien und strukturierte Datensätze. Die Bedienoberfläche nutzt ein dunkles KOR-HUD aus Graphit, klaren Linien, Rot als Akzent und sparsamen Goldmarkierungen.

## Projekt- und Repository-Status

- **Kanonischer Quellbaum:** Die versionierten Projektdateien im Repository. Ursprüngliche Upload-Archive bleiben unter `archive/legacy-uploads/` als Herkunfts- und Wiederherstellungsreferenz erhalten; sie sind nicht die aktive Quelle.
- **Arbeitsbranch:** `transfer/kor-nexus-1.20.0`. Die vollständige Wiederherstellung ist bereits auch in `main` angekommen. Dieser Branch dient für weitere Änderungen und Verifikation; Änderungen werden hier zuerst geprüft und erst nach Review zusammengeführt.
- **Release-Prüfungen:** `.github/workflows/release.yml` führt portable Qualitätsprüfungen, Browser-Tests und einen nativen Arch-Linux-Paketbau mit isoliertem Installationstest aus. Der Workflow lädt Artefakte hoch, erzeugt aber nicht automatisch GitHub-Releases oder Tags.
- **Letzter grüner Gesamt-Gate:** 52 API-Tests, Browser-Smoke-Test inklusive KI-Panel, nativer Arch-Paketbau und isolierter Paketinstallation für Commit `41637a3` ([GitHub Actions](https://github.com/oORaxaOo/KOR-NEXUS/actions/runs/39034401643)). Die echten Modell-/Hardwaretests der optionalen KI sind noch offen.
- **Historische Baseline:** Der isolierte Benutzer-Installationstest prüft weiterhin Pfade mit Leerzeichen, belegten Standard-Port, Doppelstart, Stop und Datenerhalt bei Deinstallation; die Offline-Weltkarte enthält 177 GeoJSON-Features mit verifizierter Prüfsumme.
- **Aktueller Gesamtstatus:** Für den endgültigen Release-Status ist der neueste [GitHub-Actions-Lauf dieses Branches](https://github.com/oORaxaOo/KOR-NEXUS/actions?query=branch%3Atransfer%2Fkor-nexus-1.20.0) maßgeblich; ein älterer grüner Job ersetzt nicht das Ergebnis des neuesten Commits.
- **Vorschaubilder:** Die Dateien unter `preview/` sind ausdrücklich als archivierte visuelle Referenzen gekennzeichnet, nicht als aktuelle QA-Screenshots. Neue Screenshots lassen sich mit `python3 scripts/qa-preview-playwright.py` und installiertem Playwright/Chromium erzeugen.

## Schnellstart

Direkt aus dem Projektordner starten:

```bash
./launch.sh
```

Für eine benutzerspezifische Installation mit Anwendungsmenü:

```bash
./install-user.sh
```

Der Kern nutzt Python 3 und SQLite; das Frontend besteht aus lokal geladenem HTML, CSS und JavaScript. Der Server bindet ausschließlich an `127.0.0.1`. Für den Benutzerstart sind weder Root-Rechte noch ein Cloud-Konto oder eine Frontend-Build-Kette erforderlich. Datenbank, Sicherungen und Laufzeitprotokolle liegen getrennt von den Programmdateien und bleiben bei der Deinstallation erhalten.

## Optionale lokale KI (llama.cpp)

Die deterministische Kern-Engine benötigt keine KI. Der lokale KI-Assistent ist standardmäßig deaktiviert und kann nach erfolgreicher Stabilisierung des Kerns ausdrücklich aktiviert werden. Er liefert Beratungstexte, erhält keinen direkten Datenbank-Schreibzugriff und führt keine Aktionen aus. Prompts werden nicht an einen Cloud-Anbieter gesendet.

Für die optionale Laufzeit wird `llama-cpp-python` in einer eigenen virtuellen Umgebung unter `$XDG_DATA_HOME/kor-workstation/ai-venv` installiert. Die Einrichtung lädt **kein Modell** herunter: Du musst zuvor selbst eine GGUF-Datei beziehen und deren Lizenz prüfen.

Aus dem Quellordner:

```bash
bash scripts/setup-local-ai.sh
```

Bei einer Benutzerinstallation:

```bash
bash "${XDG_DATA_HOME:-$HOME/.local/share}/kor-workstation-app/scripts/setup-local-ai.sh"
```

Das Skript fragt nach dem Pfad zur vorhandenen `.gguf`-Datei, installiert die optionale Bindung isoliert und legt die Konfiguration mit privaten Dateirechten unter `$XDG_CONFIG_HOME/kor-nexus/ai.json` (Standard: `~/.config/kor-nexus/ai.json`) ab. Danach KOR-NEXUS neu starten. Der Launcher erkennt die virtuelle Umgebung automatisch; ohne sie bleibt der Standardstart unverändert.

Die Konfiguration kann beispielsweise so aussehen:

```json
{
  "enabled": true,
  "model_path": "/absoluter/pfad/zum/modell.gguf",
  "context_size": 4096,
  "max_tokens": 512
}
```

Die Laufzeit lädt das Modell erst bei der ersten Anfrage. Kontextfenster und Antwortlänge sind begrenzt. Die Oberfläche vergleicht die GGUF-Dateigröße grob mit dem aktuell verfügbaren RAM und warnt, wenn die Datei größer ist; KV-Cache und Backend benötigen zusätzlichen Speicher. Ein fehlendes Paket, ein ungültiger Modellpfad oder ein Ladefehler deaktiviert nicht die Kern-Engine. Es gibt keinen automatischen Modell-Download und keinen verpflichtenden Netzwerkdienst. Die Installation von `llama-cpp-python` kann abhängig von Plattform und Hardware Zeit benötigen und benötigt beim Setup Internetzugriff, sofern kein passendes Paket lokal verfügbar ist.

## Historische technische Änderungen

## Entwicklungsstand 1.11.0 — Live-RSS und Quellenprüfung

Der RSS-/Atom-Abruf nutzt feste HTTPS-Quellen, einen begrenzten Netzwerk-Timeout und eine harte Antwortgrößenbegrenzung. Leere, fehlerhafte oder mit DTD/Entity-Deklarationen versehene XML-Antworten werden abgewiesen. Artikelziele müssen absolute HTTP(S)-URLs ohne Zugangsdaten sein; identische URLs werden dedupliziert. Externe Titel und Teaser werden als nicht vertrauenswürdige Inhalte behandelt und sicher dargestellt. Fehlgeschlagene Abrufe und gültige leere Feeds löschen keine zuvor gespeicherten Meldungen. Der Quellenstatus unterscheidet Abruffehler, leere Feeds und erfolgreiche Aktualisierungen. RSS bleibt optional: alle lokalen Module, Karten und gespeicherten Nachrichten funktionieren ohne Internet weiter.

## Entwicklungsstand 1.10.0 — Regionales Lagezentrum

Das Projektmodul beginnt mit einem regionalen Lage-Dashboard: Region, Projekt und Status lassen sich unabhängig filtern. Kennzahlen zeigen Projekte, offene Aufgaben, beteiligte Mitglieder und Kartenstandorte. Projektzuweisungen, Mitglieder, Ressourcen, Aufgaben und Standorte werden über echte numerische IDs verknüpft — identische Namen führen nicht zu falschen Treffern. Status und Fortschritt werden nur aus vorhandenen Kartenstandorten abgeleitet; ohne Daten erscheint „Unbekannt“ bzw. „Keine Angabe“. Ressourcenmengen werden pro Ressource mit ihrer Einheit angezeigt und nicht unzulässig zusammengerechnet. Das Layout passt sich an Desktop und schmale Displays an. Der neue lesende Endpunkt `GET /api/dashboard/projects` unterstützt `region`, `project_id` und `status`. Die bisherigen Projektformulare, Atlas-Funktionen, Geodaten, JSON-Portabilität, Importvorschau, Backups und Installationspfade bleiben erhalten.

## Entwicklungsstand 1.9.0

Release 1.9.0 stärkt die benutzerspezifische Installation, den Start aus dem Desktop-Menü, das Verhalten bei Portkonflikten und die sichere Deinstallation. Nutzerdaten und Sicherungen bleiben bei der Entfernung der Programmdateien erhalten.

Der Atlas verwendet jetzt eine lokal eingebettete GeoJSON-Weltkarte aus Natural Earth statt der zuvor gezeichneten schematischen Umrisse. Die Deutschland-Ansicht zoomt auf die tatsächliche Ländergeometrie; bestehende SQLite-Marker und Projektverknüpfungen bleiben erhalten und werden mit den Kartenkoordinaten projiziert. Ein lokaler GeoJSON-Import für Bundeslandgrenzen ist eingebaut. Der strategische Planungsmodus erlaubt Marker direkt per Kartenklick zu positionieren, per Ziehen zu verschieben, zu bearbeiten und zu löschen. Marker besitzen Status und Fortschritt und können mit Projekten, Aufgaben, Mitgliedern und Ressourcen verknüpft werden. Filter, Suche und eine regionale Ressourcen-/Fortschrittsübersicht sind integriert. **Die amtlichen Polygone der 16 Bundesländer sind nicht mitgeliefert**, weil sie in dieser Umgebung nicht heruntergeladen und hinsichtlich Quelle/Lizenz nicht als konkretes Asset geprüft werden konnten. Die Einschränkung wird in der Oberfläche angezeigt. Siehe `PROJECT_STATUS.md`.

## Importvorschau und Konfliktbericht 1.8.0

Vor dem endgültigen JSON-Import zeigt die Oberfläche eine serverseitig validierte, schreibgeschützte Vorschau: Schema-Version, Aufgaben, Datensätze je Modul, Marker, Profile, Ressourcen, Zuweisungen, Einstellungen, Geodaten-Features und News-Cache. Doppelte Export-IDs, mehrdeutige Schema-1-Namenszuordnungen sowie ungültige oder fehlende Referenzen werden als verständliche Konflikte gemeldet, ohne private Inhalte oder IDs unnötig offenzulegen. Die Vorschau erstellt kein Backup und ändert keine Datensätze. Der endgültige Import führt die vollständige Validierung erneut aus und erstellt erst danach ein Integritäts-geprüftes Sicherheitsbackup. Details: `EXPORT_SCHEMA.md`.

## Karteninteraktion 1.6.0

- Markerpositionen werden über die tatsächliche SVG-ViewBox-/Screen-Transformation berechnet. Damit stimmen Position und Drag auch bei abweichenden Seitenverhältnissen und mobilen Viewports mit der gezeichneten Karte überein.
- Marker lassen sich mit Pointer Events (Maus und touchfähige Geräte) verschieben. Ein Drag speichert ausschließlich `latitude` und `longitude` per PATCH; Status, Fortschritt, Notizen und SQLite-Verknüpfungen werden nicht erneut aus einem veralteten Frontendobjekt übertragen.
- Ein Klick auf die Karte übernimmt Koordinaten in die beschrifteten Breitengrad-/Längengradfelder und fokussiert das Namensfeld. Der Klick legt nicht ungefragt einen Datensatz an; Speichern bleibt eine bewusste Formularaktion.
- Die manuelle Koordinateneingabe bleibt als zugängliche Alternative verfügbar. `Escape`-freie Formularaktionen sind nicht an Drag gebunden; `pointercancel` beendet die Geste ohne Speichern.
- Grenzen der Verifikation: Der Browser-Test simuliert Mausbewegungen in Desktop- und mobilem Viewport. Ein echter Touchscreen und eine reale NyarchLinux-Installation standen nicht zur Verfügung.

## Ein-Klick-Start

### Direkt aus dem Projektordner

Python 3 ist die einzige notwendige Anwendungs-Laufzeit; eine Prozesssperre im Python-Kern schützt alle Startwege vor konkurrierenden Instanzen. Zusätzliche Python-Pakete, npm-Downloads, eine Cloud-Verbindung und Root-Rechte sind nicht erforderlich.

```bash
./launch.sh
```

Der Start erstellt bzw. öffnet die lokale SQLite-Datenbank und öffnet die Oberfläche unter `http://127.0.0.1:8765/`. Wenn Chromium oder Chrome installiert ist, wird die Anwendung bevorzugt in einem eigenen App-Fenster geöffnet. Andernfalls wird ein verfügbarer Browser verwendet. Ein zweiter Start verwendet den bereits laufenden KOR-Kern wieder. Mit `./stop.sh` lässt sich der laufende Kern gezielt beenden. Nach einer Benutzerinstallation stehen `~/.local/bin/kor-workstation` und `~/.local/bin/kor-workstation-stop` zur Verfügung.

### Dauerhafte Benutzerinstallation unter Arch Linux

Im entpackten Projektordner einmal ausführen:

```bash
./install-user.sh
```

Danach lässt sich **KOR-NEXUS** mit einem Klick aus dem Anwendungsmenü starten; alternativ funktioniert `~/.local/bin/kor-workstation`. Die Installation ist benutzerspezifisch und benötigt kein `sudo`. Programmdateien liegen unter `~/.local/share/kor-workstation-app/`; die Nutzerdaten bleiben davon unabhängig unter `~/.local/share/kor-workstation/` (bzw. unter dem entsprechenden `XDG_DATA_HOME`). Zum Entfernen der Programmdateien und des Menüeintrags dient `./uninstall-user.sh`; Datenbank und Backups bleiben dabei erhalten. Vor einer Aktualisierung wird eine laufende Instanz kontrolliert beendet; falls das nicht bestätigt werden kann, bricht das Installationsskript ab, statt Programmdateien unter einem laufenden Server auszutauschen. Das Stop-Programm ist auch als `~/.local/bin/kor-workstation-stop` verfügbar. Die grafische Sitzung protokolliert Startfehler in `~/.local/state/kor-workstation/server.log` (bei gesetztem `XDG_STATE_HOME` entsprechend dort); die Datei ist auf zwei Protokollgenerationen begrenzt.

## Visuelles Design 1.13.0

Die Oberfläche nutzt ein konsistentes, lokal geladenes Designsystem: Graphit und Schwarz als Grundflächen, klare helle Typografie, Rot für aktive/primäre Aktionen und sparsame Goldmarkierungen für ausgewählte oder hervorgehobene Informationen. Fokuszustände für Tastaturbedienung, reduzierte Animationen (`prefers-reduced-motion`) und eine eigens geprüfte schmale Mobilansicht sind enthalten. Die Anwendung benötigt dafür weder externe Schrift-CDNs noch eine Frontend-Build-Kette.

Der optionale Browser-Smoke-Test schreibt Screenshots nach `preview/smoke-test.png`, `preview/hud-redesign-desktop.png` und `preview/hud-redesign-mobile.png`.

## Enthaltene Funktionen

- **Atlas:** offline verfügbare Weltgeometrien, Welt-/Deutschland-Ansicht, WGS84-Projektmarker mit Bearbeiten/Verschieben, Status, Fortschritt, Suche/Filter und Verknüpfungen zu Projekten, Aufgaben, Mitgliedern und Ressourcen; regionale Ressourcenübersicht, durchsuchbarer Atlas-Notizbestand und Index aller 16 Bundesländer. Bundesland-Polygone können als GeoJSON (WGS84/EPSG:4326) importiert werden.
- **Projekte:** beliebige Einträge mit Titel, ausführlichem Inhalt, Bereich und Tags; Bearbeiten, Suchen und Löschen.
- **Archiv:** lokale Wissensbasis für Grundsätze, Referenzen und Notizen.
- **Simulation:** eigener Bereich zum Dokumentieren von Szenarien, Annahmen und Folgen. Es werden keine Ergebnisse als echte Prognosen ausgegeben.
- **Datenbank:** allgemeines Register mit Tags, Bereich, Volltextsuche und Bearbeitungsfunktionen.
- **Personal & Logistik:** Profile mit Biografie, Rolle, Status, Region und Tags; Ressourcen mit Kategorie, Menge, Einheit und Standort; Zuordnung von Personen oder Ressourcen zu bestehenden Projekten. Zugewiesene Profile/Ressourcen lassen sich erst löschen, wenn die Zuweisungen entfernt wurden.
- **Anpassbare Bezeichnungen:** Einzahl/Mehrzahl für Personen lassen sich in den Systemeinstellungen ändern und werden in der Verwaltungsansicht verwendet.
- **Aufgaben:** Aufgaben anlegen, erledigen, umbenennen, einem Bereich zuordnen und löschen.
- **Nachrichten:** RSS-Adapter für WELT, tagesschau.de und Deutschlandfunk. Quellen werden parallel aktualisiert; Ergebnisse werden lokal zwischengespeichert. Bei fehlender Verbindung bleiben gespeicherte Daten verfügbar. Meldungen werden als Überschriften/Teaser mit Link zum Original gezeigt, nicht als kopierte Vollartikel.
- **SQLite:** persistente Speicherung über Programm- und Rechnerneustarts hinweg.
- **Automatische Sicherungen:** Sicherung beim Start, zeitgesteuerte Sicherung bei laufender Nutzung sowie manuelle Sicherung. Es können 3 bis 50 Sicherungen aufbewahrt werden; die Intervalleinstellung reicht von 5 Minuten bis 24 Stunden. Vor Import und Wiederherstellung wird eine zusätzliche Sicherung erstellt.
- **Wiederherstellung:** auswählbare Wiederherstellungspunkte, SQLite-Integritätsprüfung und Plausibilitätskontrolle des Schemas.
- **Datenportabilität 1.8.0:** Versioniertes JSON-Schema 2 exportiert/importiert Aufgaben, sämtliche Modul-Datensätze, Kartenmarker mit Status/Fortschritt und Referenzen, Mitgliederprofile samt Biografien, Ressourcen, Projektzuweisungen, Einstellungen, importierte Geodaten und News-Cache. IDs aus der Quelldatenbank werden ausschließlich als Paket-Referenzen verwendet und beim Import auf neu erzeugte lokale SQLite-IDs abgebildet. Fehlende/doppelte IDs, ungültige oder mehrdeutige Referenzen und beschädigte Inhalte werden vor der Änderung erkannt; vor dem Import wird ein geprüftes Sicherheitsbackup angelegt. Schema-1-Exporte und die ältere Browserdatenmigration werden weiterhin unterstützt. Details: `EXPORT_SCHEMA.md`.
- **Deutsch/Englisch:** Sprachumschalter für die primäre Navigation und Oberflächenlabels.
- **Lokaler Betrieb:** HTTP-Server ist ausschließlich an `127.0.0.1` gebunden. Eingehende JSON-Daten und Titel werden validiert; RSS- und Benutzerdaten werden beim Rendern als Text escaped.

## Daten und Datenschutz

- Datenbank: `${XDG_DATA_HOME:-~/.local/share}/kor-workstation/kor-workstation.sqlite3`
- Sicherungen: `${XDG_DATA_HOME:-~/.local/share}/kor-workstation/backups/`
- Startprotokoll der Menü-/Paketversion: `${XDG_STATE_HOME:-~/.local/state}/kor-workstation/server.log`
- Die Anwendung sendet keine Nutzerdaten an einen Cloud-Dienst.
- RSS-Abrufe gehen nur an die konfigurierten Verlags-Feeds. Ohne Netz bleibt die übrige Anwendung lokal verfügbar.
- Öffne die Anwendung möglichst nur mit dem mitgelieferten Launcher. Die Oberfläche ist für lokale Nutzung bestimmt und darf nicht über einen öffentlich erreichbaren Netzwerkserver bereitgestellt werden.
- Die Sicherungen liegen standardmäßig im selben Benutzerprofil und damit auf demselben Datenträger. Für Schutz vor Datenträgerausfall empfiehlt sich zusätzlich ein gelegentlicher JSON-Export auf einen zweiten, selbst gewählten Speicherort.

## Kartenstatus und Geodatenlizenzen

### Mitgelieferte Weltkarte

- Datei: `web/geodata/world.geojson`
- Umfang: 177 Länder-/Gebietsfeatures; **364.876 Byte (rund 356,3 KiB)** in der ausgelieferten Fassung.
- Grundlage: lokal vorhandener Natural-Earth-Low-Resolution-Datensatz, als GeoJSON vereinfacht. Er ist für eine globale Übersicht gedacht, nicht für Kataster-, Navigations- oder Grenzstreit-Entscheidungen.
- Lizenz: Natural Earth erklärt seine Raster- und Vektordaten als **Public Domain**; keine Namensnennung erforderlich. Die Anwendung nennt Natural Earth dennoch sichtbar als Datenquelle. Siehe [Natural Earth – Nutzungsbedingungen](https://www.naturalearthdata.com/about/terms-of-use/) und [Natural Earth – Downloads/Skalen](https://www.naturalearthdata.com/downloads/).
- Offline: Geometrien sind Teil des Projektpakets. Für die Weltkarte ist kein externer Kartendienst erforderlich.

### Bundeslandgrenzen Deutschlands — noch nicht gebündelt

Ein verifizierbarer Datensatz mit den 16 amtlichen Länderpolygonen war im verfügbaren lokalen Dateisystem nicht vorhanden; der externe Download war in der Entwicklungsumgebung nicht erreichbar. Deshalb wurden keine Grenzen synthetisch erzeugt und keine Lizenzen geraten. Die Deutschlandansicht zeigt bis zum Import nur die echte, aber generalisierte Deutschlandgeometrie der Weltkarte.

Ein geeigneter offizieller Ausgangspunkt ist das [BKG-Verwaltungsgebiete-Produkt VG250](https://gdz.bkg.bund.de/index.php/default/open-data/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html). Die veröffentlichte Standardkonfiguration wird als ZIP mit rund **69 MB** angegeben; die Daten werden kostenfrei unter **Datenlizenz Deutschland – Namensnennung 2.0 (dl-de/by-2-0)** bereitgestellt. Bei Weitergabe/öffentlicher Darstellung sind der geforderte Quellenvermerk und der Änderungshinweis einzuhalten. Quelle/Lizenz und aktuelle Produktdetails bitte vor dem konkreten Download prüfen. Eine feinere BKG-VG25-Ausgabe ist deutlich größer (die aktuelle Standardkonfiguration wird mit 320 MB ZIP angegeben) und für eine reine Länderübersicht voraussichtlich unnötig.

**Importweg:** aus der ausgewählten Länder-Ebene eine GeoJSON-FeatureCollection in WGS84/EPSG:4326 exportieren, danach im Atlas „Bundesländer-Geodaten importieren“ verwenden. Falls die Quelldatei im amtlichen UTM32s/EPSG:25832 vorliegt, muss sie beim Export nach EPSG:4326 transformiert werden (z. B. in QGIS, nicht bloß umbenannt). Der Import prüft Feature-/Geometrietypen und Koordinatenbereiche, kann aber weder die sachliche Richtigkeit der Grenzen noch die Lizenz einer Datei selbst bestätigen.

Importierte Geodaten werden lokal in SQLite gespeichert und gehören damit zu den SQLite-Sicherungen und JSON-Exporten. Die Karte bleibt eine Planungsübersicht; Routing und Navigation sind nicht enthalten.

## Tests und Prüfung

```bash
python3 -m unittest -v core.test_server
./scripts/verify-source.sh
```

Die 29 automatisierten Kern-API-Tests prüfen SQLite-Aufgaben und -Datensätze, Standortanlage/-bearbeitung, Status-/Fortschrittsvalidierung, referenzielle Verknüpfungen zu Projekt, Aufgabe, Mitglied und Ressource, Eingabevalidierung, Einstellungen, JSON-Import/-Export, Backup und Wiederherstellung, RSS/XML-Verarbeitung sowie die Ablehnung fremder Browser-Origin-Anfragen. Der Browser-Smoke-Test nutzt eine deterministische Mock-API; er ist kein Ersatz für eine echte Zielsysteminstallation.

Ein zusätzlicher Browser-Smoke-Test ist mit Python Playwright und Chromium möglich:

```bash
python3 scripts/qa-preview-playwright.py
```

Der optionale Browser-Smoke-Test ist von Playwright/Chromium abhängig; die Anwendung selbst hat diese Abhängigkeiten nicht. Der vollständige Release-Gate läuft mit `./scripts/release-check.sh` (Kern-, Browser- und Installationstests) oder `./scripts/release-check.sh quick` (schnelle statische Prüfungen). Das Skript erzeugt ein deterministisches Quellarchiv und aktualisiert die äußere PKGBUILD-Prüfsumme. Ein Arch-Paket wird ausschließlich auf einer passenden Arch-Umgebung mit `./scripts/build-arch-package.sh` gebaut; standardmäßig wird nicht installiert. Eine Paketinstallation erfordert die ausdrückliche Option `./scripts/build-arch-package.sh --install`.

## Laufzeit- und Hardwareziel

Der Kern nutzt Python-Standardbibliothek und SQLite, die Oberflächenressourcen sind lokal. Es wird keine dedizierte GPU benötigt. Das Programm ist für einen Rechner mit mindestens 16 GB RAM geeignet; diese Entwicklungsumgebung kann jedoch keinen unabhängigen Leistungstest auf deiner konkreten Hardware ersetzen.

## Technische Architektur

- `core/server.py` — lokale HTTP-API, SQLite, RSS, Backups/Restore und Ein-Klick-Launcher
- `core/test_server.py` — automatisierte API-/Integritätstests
- `web/` — eigenständiges HTML/CSS/JavaScript-Frontend ohne Laufzeitbibliotheken; `web/geodata/world.geojson` enthält die offline nutzbare Weltkarte
- `launch.sh` — sofortiger lokaler Start
- `install-user.sh` — benutzerspezifische Installation mit Anwendungsmenüeintrag
- `PKGBUILD` — Arch-Linux-Paketdefinition ohne Cargo- oder npm-Build-Abhängigkeit; `kor-workstation-stop` beendet die eigene lokale Instanz
- `scripts/ci.sh` — provider-neutraler Einstiegspunkt für lokale und externe CI-Läufe
- `scripts/release-check.sh` — prüft Versionskonsistenz, Paketdateiliste, reproduzierbares Quellarchiv, Prüfsummen, Syntax und verfügbare Tests
- `scripts/build-arch-package.sh` — erstellt Quellarchiv und baut das Arch-Paket mit `makepkg`; Installation nur mit `--install`
- `scripts/test-built-package-installation.sh` — isolierter Arch-CI-Integrationstest für Paketinstallation, Start/Stop und Datenerhalt; nur in einer wegwerfbaren Arch-Umgebung ausführen
- `scripts/verify-source.sh` und `scripts/qa-preview-playwright.py` — Quell-/Oberflächenprüfungen
- `DECISIONS.md` und `PROJECT_STATUS.md` — technische Entscheidungen und geprüfter Lieferumfang

## Lizenz

Siehe `LICENSE`.

## Nativer Arch-Paketbau und isolierter Installationstest in CI (1.17.0)

`.github/workflows/release.yml` definiert getrennte Jobs: plattformunabhängige Prüfungen und einen nativen Paketbau in einem Arch-Linux-Container. Der Arch-Job installiert seine Build-Werkzeuge nur innerhalb des kurzlebigen CI-Containers, erstellt einen unprivilegierten Build-Benutzer, regeneriert das deterministische Quellarchiv und ruft `makepkg` ohne Installationsoption auf. Paketmetadaten, Dateiliste und Paketarchiv werden geprüft und als CI-Artefakt bereitgestellt. Nach dem Paketbau wird das Paket innerhalb desselben kurzlebigen Arch-CI-Containers installiert, gestartet, geprüft und wieder entfernt. Dieser Test ist ausdrücklich keine Installation auf dem persönlichen Zielsystem.

Lokale Diagnose: `command -v makepkg`, `command -v pacman`, `command -v docker` und `command -v podman`. Auf einer Debian-Umgebung ohne diese Werkzeuge ist ein echter Arch-Paketbau nicht möglich; die CI-Konfiguration ersetzt keinen tatsächlich ausgeführten CI-Lauf.
