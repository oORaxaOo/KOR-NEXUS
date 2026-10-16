## Designtechnische Entwicklungsentscheidung 36 — Repository eindeutig zuordnen und CI vorbereiten (1.20.0)

- GitHub-Connector identifizierte `oORaxaOo/KOR-NEXUS` anhand des exakten Repository-Namens und Besitzers; Standardbranch `main`.
- Connector meldet Admin-/Push-Berechtigungen für die verbundene Identität. Keine Schreibaktion durchgeführt.
- Remote-README geprüft; `.github/workflows/release.yml` fehlt im Remote-Branch (`404`). Das Remote enthält nicht den vollständigen lokalen Projektstand.
- Lokale Arbeitskopie hat weiterhin kein `.git` und keinen Remote; der lokale Release-Workflow liegt nur in der Arbeitskopie.
- Kein Workflow-Dispatch, Commit, Push oder Release ausgelöst. Remote-CI-Status ist nicht bestätigt; nativer Arch-Paketbau mangels `makepkg`/`pacman` offen.
- Lokales Release 1.20.0, Funktionen und Offline-Geodaten bleiben erhalten; Archive und Prüfsummen werden nach Aktualisierung der Dokumentation neu erstellt und verifiziert.

## Designtechnische Entwicklungsentscheidung 35 — Repository eindeutig zuordnen (1.19.0)

- GitHub-Connector listete `oORaxaOo/test` und `oORaxaOo/myvirtualassistant`, beide privat. Der Abruf von `.github/workflows/release.yml` ergab in beiden Fällen 404.
- Gezielt nach `KOR-NEXUS` und `kor nexus` gesucht; kein passender Repository-Treffer.
- Die Arbeitskopie `/mnt/data/kor-nexus-work/kor-work` hat kein `.git` und keinen konfigurierten Remote.
- Fehlende Information: kanonische Repository-URL oder exakter `owner/repository`-Name (alternativ ein lokaler Klon, dessen Remote bereits gesetzt ist).
- Aus Sicherheitsgründen kein Workflow-Dispatch, Commit, Push oder Release. CI-Status bleibt OFFEN.
- Aktive Version auf 1.19.0 aktualisiert; lokale Qualitätstests und Archive dokumentieren den tatsächlich erreichten Stand, nicht einen echten Arch-CI-Erfolg.

## Designtechnische Entwicklungsentscheidung 34 — Erster echter CI-Lauf (1.18.0)

- Repositoryzugriff geprüft: kein KOR-NEXUS-Remote eindeutig zugeordnet; lokale Kopie ohne `.git`/Remote. Zwei über Connector sichtbare private Repositories hatten den erwarteten Workflow-Pfad nicht.
- Workflow verschärft: frischer Paketoutput, genau ein Paket, Metadaten-/Dateilistenprüfung, zeitbegrenzter Installationstest und Artefakt-Upload ausschließlich nach erfolgreichem Test.
- Ergebnis: Workflow lokal geprüft; echter CI-Lauf **OFFEN**, keine Veröffentlichungsaktion durchgeführt. Manueller Ablauf in `CI_MANUAL_START.md`.

# Technische Entscheidungen — KOR-NEXUS

Stand: 2026-10-16

## D1 — Lokaler Kern zuerst

Die Produktiv-Laufzeit basiert auf Python 3 Standardbibliothek und SQLite. Dadurch gibt es keine zusätzliche Paketinstallation, keinen Rust-/Cargo-Download und keinen npm-Registry-Zugriff beim Start. Der Kern wird lokal auf `127.0.0.1` gestartet. Er ist über eine browserbasierte App-Oberfläche erreichbar; Chromium/Chrome wird nach Möglichkeit mit `--app` für ein eigenständiges Fenster gestartet.

## D2 — SQLite ist die autoritative Datenquelle

Aufgaben, Atlas-Notizen, Projekte, Archiv, Simulation und Datenbankeinträge werden in SQLite gespeichert. `localStorage` ist nur noch ein optionaler Importpfad für die ältere Vorschau. Schemaänderungen laufen über eine Versionstabelle und idempotente Tabelleninitialisierung.

## D3 — Sichere lokale API

Die HTTP-Oberfläche wird an Loopback gebunden. `Host` wird auf lokale Namen beschränkt; bei Browser-API-Anfragen wird eine fremde `Origin` abgelehnt. JSON-Körper haben eine feste Größenbegrenzung. Einträge werden als Text escaped dargestellt; externe Links öffnen mit `noopener noreferrer`. RSS-XML wird über die Standardbibliothek ausgelesen, und externe Inhalte bleiben nicht vertrauenswürdige Daten.

## D4 — Backups sind Teil des Produkts

Backups nutzen die SQLite-Backup-API und werden per `PRAGMA integrity_check` validiert. Sicherungen entstehen beim Start, in konfigurierbaren Intervallen während der Nutzung und auf Knopfdruck. Vor Import und Restore entsteht ein Sicherheitsbackup. Dateinamen und Aufbewahrung sind kontrolliert; beschädigte oder fremde Schemas werden nicht wiederhergestellt.

## D5 — RSS statt kopierter Artikel

WELT, tagesschau.de und Deutschlandfunk werden per RSS angefragt. Überschriften und begrenzte Teaser werden lokal zwischengespeichert und mit dem Original verlinkt. Netzwerkfehler sollen keine lokalen Funktionen blockieren. Live-Feeds können sich technisch ändern oder zeitweise nicht erreichbar sein; der Status bleibt in der Oberfläche sichtbar.

## D6 — Keine erfundenen Geodaten

Die Weltkarte ist aus lokal vorhandenen Natural-Earth-Low-Resolution-Geometrien erzeugt und als GeoJSON offline gebündelt. Natural Earth deklariert seine Geodaten als Public Domain. Die Deutschlandansicht zoomt auf die echte, generalisierte Ländergrenze. Die 16 amtlichen Bundeslandpolygone sind noch nicht gebündelt: Es wird ein lizenzgeprüfter GeoJSON-Import in WGS84/EPSG:4326 angeboten. Als offizielle Bezugsquelle ist BKG VG250 dokumentiert; bis ein tatsächlicher Download geprüft und eingebettet wurde, behaupten wir keine vollständige Bundeslandkarte.

## D7 — One-click Installation

Die direkte Nutzung erfolgt mit `./launch.sh`. Für die dauerhafte Arch/Linux-Benutzerinstallation erstellt `./install-user.sh` einen lokalen Launcher und Desktop-Menüeintrag. Die Produktiv-Paketdefinition benötigt Python und kein Rust/Cargo oder Node.js. `src-tauri/` und `archive/react-prototype/` bleiben als Entwicklungsreferenzen erhalten und sind nicht Teil des aktiven Startpfads.


## M2 / Atlas-Koordinatenmarker — 2026-10-16

- Neue `map_locations`-Tabelle hält Titel, Typ, Region, WGS84-Koordinaten, optionale Projektverknüpfung und Notizen.
- Lokale API validiert Koordinatenbereiche und Projekt-IDs; Projektlöschung setzt die Referenz gemäß SQLite-Fremdschlüssel auf NULL.
- Atlas zeigt Marker über einer equirektangulären Projektion, Standortliste und Eingabeformular.
- Marker sind im JSON-Export enthalten; Import ordnet Projekte über den Projekttitel erneut zu.
- Der Meilenstein M2 lieferte den Marker- und Projektverknüpfungskern; ab M3 liegt darunter die lokal gebündelte Natural-Earth-Weltgeometrie. Die amtlichen Bundeslandpolygone bleiben offen, bis eine lizenzgeprüfte Quelle importiert wurde.


## M3 / Offline-Geografie — 2026-10-16

- `web/geodata/world.geojson` enthält 177 vereinfachte Natural-Earth-Länder-/Gebietsfeatures (364.876 Byte) und wird ohne Netzwerkanfrage geladen.
- Atlas-Modi Welt und Deutschland verwenden dieselbe WGS84-Projektion; Marker werden auf den jeweiligen Ausschnitt projiziert.
- Bundesland-GeoJSON-Import akzeptiert Polygon/MultiPolygon-FeatureCollections in WGS84, prüft Koordinatenbereiche und persistiert die Datei in SQLite plus lesbarem Sidecar.
- Importierte Geodaten sind Teil der SQLite-Backups und des JSON-Exports/Imports.
- BKG VG250 ist als offizieller Kandidat dokumentiert (69 MB ZIP laut Produktseite; dl-de/by-2-0). Kein BKG-Datensatz wurde in dieser Umgebung heruntergeladen; konkrete Grenzgeometrien bleiben ein offener Lieferpunkt.


## M4 — Interaktive strategische Projektplanung (1.5.0)

- Standorttabelle erhält additive Spalten `status`, `progress`, `task_id`, `unit_id`, `resource_id`; bestehende Zeilen erhalten sichere Defaults.
- Statuswerte sind `geplant`, `aktiv`, `blockiert`, `abgeschlossen`; Fortschritt ist ganzzahlig 0–100.
- API unterstützt Standortanlage und PATCH-Änderungen mit validierten Referenzen zu bestehenden Projekten, Aufgaben, Einheiten und Ressourcen.
- Frontend unterstützt Kartenklick zur Koordinatenübernahme, Marker ziehen, Formularbearbeitung, Such-/Statusfilter und regionale Ressourcenübersicht.
- Einschränkung: Deutschlandansicht ist weiterhin eine geografische Übersicht, keine Navigation. Exakte Bundeslandgrenzen fehlen bis zum Import eines geprüften Datensatzes.


## M5 — Robuste Karteninteraktion (1.6.0)

- Kartenkoordinaten werden mit `getScreenCTM()` und dessen Inverser in beide Richtungen transformiert; damit wird das Seitenverhältnis des SVG berücksichtigt.
- Marker-Drag sendet einen minimalen PATCH nur mit `latitude` und `longitude`. SQLite bewahrt alle sonstigen Felder und Fremdschlüssel.
- Kartenklick befüllt Koordinatenfelder, fokussiert den Titel und benötigt weiterhin eine explizite Speichern-Aktion.
- `pointercancel` bricht ab ohne zu persistieren; ein Mindestbewegungsschwellwert trennt Klick und Drag.
- Tests: API-PATCH-Erhalt aller Referenzen und Browser-Mausdrag in Desktop- und mobilem Viewport. Echte Touch-Hardware wurde nicht getestet.


## M6 — Vollständige Datenportabilität (1.7.0)

- Schema 2 ist das kanonische JSON-Backupformat für alle strukturierten Module, Kartenmarker, Personenprofile, Ressourcen, Projektzuweisungen, Einstellungen, importierte Geodaten und Nachrichten-Cache.
- IDs sind nur innerhalb des Exportpakets Referenzschlüssel. Beim Import werden neue lokale IDs erzeugt; Beziehungen werden kontrolliert über Zuordnungstabellen neu verbunden.
- Vor jeder Mutation werden Struktur, IDs, Feldgrenzen und Referenzen geprüft. Legacy-Titel werden nur verwendet, wenn die Zuordnung eindeutig ist.
- Gültige Imports erfolgen transaktional nach Sicherheitsbackup; Fremdschlüssel werden anschließend geprüft. Schema 1 bleibt für Altimporte erhalten.
- Das vollständige Feldverzeichnis und die Kompatibilitätsregeln stehen in `EXPORT_SCHEMA.md`.


## M7 — Importvorschau und Konfliktbericht (1.8.0)

- `POST /api/import/preview` ist ein schreibgeschützter Validierungsendpunkt. Er liefert nur Zählwerte und datenschutzbewusste Konflikthinweise; er erstellt kein Backup.
- Die finale Importaktion verwendet die gleiche Schema-Validierung erneut. Zwischen Vorschau und Bestätigung wird kein Validierungsergebnis als Vertrauensnachweis wiederverwendet.
- Ungültige Dateien können in der Oberfläche nicht bestätigt werden. Schema-1-Namenszuordnungen müssen eindeutig sein; Schema 2 verlangt eindeutige Paket-IDs und gültige Referenzen.


## M8 — Installation und Ein-Klick-Start (1.9.0)

- Desktop-Menü und benutzerspezifische Installation folgen XDG-Verzeichnissen und maskieren Pfade korrekt.
- Der Python-Kern hält eine Prozesssperre unabhängig vom gewählten Startweg; der Launcher protokolliert Fehler und unterstützt einen separaten, sicheren Stop-Befehl.
- Die Deinstallation entfernt keine Datenbank, Backups oder importierten Geodaten aus dem Benutzerprofil.
- `scripts/build-arch-package.sh` baut standardmäßig nur; eine Installation benötigt das explizite Argument `--install`.

## M9 — Regionales Lagezentrum und Projekt-Dashboard (1.10.0)

- Das Dashboard ist eine lesende Aggregation; SQLite bleibt die autoritative Datenquelle. Es wird keine parallele Dashboard-Tabelle angelegt.
- Projektzuweisungen werden anhand `project_assignments.project_id`, `unit_id` und `resource_id` verbunden; Kartenstandorte über `map_locations.project_id`, Aufgaben über `task_id`. Anzeigenamen sind niemals Verknüpfungsschlüssel.
- Projektstatus und Fortschritt sind derzeit Eigenschaften verknüpfter Kartenstandorte, keine eigenständigen Projektfelder. Ohne Standortdaten ist der Projektstatus „unbekannt“ und Fortschritt `null`; mehrere unterschiedliche Standortstatus werden als „gemischt“ angezeigt.
- Offene Aufgaben werden nur aus existierenden `task_id`-Verknüpfungen und `done=0` abgeleitet. Nicht verknüpfte Aufgaben werden nicht einem Projekt zugeschrieben.
- Ressourcen werden mit Zuweisungsmenge und Originaleinheit dargestellt. Keine Summierung über unterschiedliche Ressourcentypen/Einheiten.
- Filter sind serverseitig und lesend; ungültige Projekt-IDs und Statuswerte liefern HTTP 400.


## M10 — Live-RSS und Quellenprüfung (1.11.0)

- Feste HTTPS-Quellen, begrenzter Timeout und begrenzte Antwortgröße.
- RSS-/Atom-Parser lehnt leere, ungültige XML-Dokumente und DTD-/Entity-Deklarationen ab.
- Artikelziele müssen absolute HTTP(S)-URLs ohne Zugangsdaten sein; wiederholte IDs/URLs werden dedupliziert.
- Bei Abruffehlern oder gültigen leeren Feeds bleibt der vorhandene Cache erhalten. Ein Fehler wird nicht als erfolgreicher Abruf ausgegeben.
- Automatisierte Tests prüfen Parserfehler, Timeout, leere Antwort, Cache-Erhalt, Deduplizierung, Aktualisierung und Persistenz.


## M11 — Visuelle Identität und HUD-Redesign (1.13.0)

Das visuelle Design wird über zentrale CSS-Tokens gesteuert. Graphit/Schwarz bilden die Oberflächen, klare helle Typografie stellt Lesbarkeit sicher, Rot ist ein gezielter Aktionsakzent und Gold markiert ausgewählte oder wichtige Informationen. Keine externen Assets oder Laufzeitbibliotheken sind erforderlich. Tastaturfokus, reduzierte Bewegung und schmale Viewports gehören zu den überprüfbaren Designanforderungen. Der Playwright-Smoke-Test erzeugt Desktop- und Mobil-Screenshots und prüft wichtige Design-Tokens, Navigation und horizontales Overflow.


## M12 — HUD-Verfeinerung und visuelle Signatur (1.13.0)

Die Version 1.13.0 verfeinert das in M11 etablierte visuelle System, statt neue Funktionen zu erfinden: technisches Raster, Abschnittsmarkierungen, bessere Hierarchie zwischen operativen Daten und Metadaten sowie zurückhaltende Interaktionsbewegung. Rot kennzeichnet Aktionen und Gold ausgewählte Hervorhebungen. Die API, das Datenmodell, Offline-GeoJSON, RSS, JSON-Portabilität, Importvorschau, Backups, Prozesssperre und Installationspfade bleiben unverändert. Die Browserprüfung verwendet weiterhin einen deterministischen Mock und ist kein Beleg für Live-Backend- oder Zielsystemtests.


## M13 — Arch-Paketbau und Release-Automatisierung (1.15.0)

Der Release-Check prüft Versionen, Paketdateiliste, deterministisches Quellarchiv, Archivintegrität, SHA-256, Python- und JavaScript-Syntax sowie verfügbare Kern-, Browser- und Installationstests. Quellarchiv-Erzeugung, Arch-Paketbau, Paketinstallation und Zielsystemprüfung sind getrennte Schritte. Fehlendes `makepkg` führt zu einem klaren Nichtverfügbar-Status und wird nicht durch einen fremden Paketmanager oder einen Scheinbuild ersetzt.


## M14 — CI-Pipeline und automatisierte Release-Gates (1.15.0)

Ein provider-neutraler CI-Einstieg wurde gewählt, weil im verfügbaren Arbeitsverzeichnis weder ein Git-Remote noch eine bestehende CI-Konfiguration nachweisbar war. `scripts/ci.sh` delegiert an denselben dokumentierten Release-Gate wie lokale Entwicklung; damit entsteht keine zweite, abweichende Testdefinition. Zwei Quellarchive werden unabhängig erzeugt und anhand SHA-256 verglichen. Versions-, Paketdatei-, Syntax-, Kern-, Browser- und Installationstests laufen vor dem Release. Arch-Paketbau und Installation bleiben separate Aktionen und werden nur auf einer passenden Umgebung als ausgeführt gemeldet.


## M15 — Nativer Arch-Paketbau und CI-Build-Vorbereitung (1.17.0)

Die lokale Laufzeit wurde geprüft: Debian GNU/Linux 13, x86_64. `makepkg`, `pacman`, Docker und Podman sind nicht vorhanden; es wurde weder ein Hostpaket installiert noch ein Paketbau vorgetäuscht. `.github/workflows/release.yml` definiert deshalb einen echten Arch-Linux-Containerjob für CI. Dieser erzeugt das Quellarchiv und baut das Paket mit `makepkg` als unprivilegierter Benutzer, prüft Paketmetadaten und Dateiliste und veröffentlicht das Paket als Artefakt. Ein separater plattformunabhängiger Job führt Release-Gates aus. Der Workflow wurde lokal statisch validiert; eine remote CI-Ausführung steht aus.

## M16 — Isolierter Arch-Installations- und Integritätstest (1.17.0)

- CI-Workflow ergänzt nach dem nativen Paketbau einen Installationstest in einem kurzlebigen Arch-Linux-Container.
- Test prüft installierte Pfade, Launcher-Berechtigungen, Desktop-Integration, Offline-Weltkarte, Health-Endpunkt, SQLite-Erstellung, Prozesssperre, Stop und Datenerhalt nach Paketentfernung.
- Testdaten liegen in temporären XDG-Pfaden; Paketinstallation erfolgt nur im wegwerfbaren CI-Container, nie automatisch auf dem persönlichen Zielsystem.
- Nicht ausgeführt in der lokalen Debian-Umgebung: nativer `makepkg`-Build, Arch-Paketinstallation und Remote-CI-Lauf.
