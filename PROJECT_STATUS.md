# Projektstatus — KOR-NEXUS

Stand: 2026-10-17 · Version 1.20.0 · Schwerpunkt: Core Engine, Live-Updates und sichere lokale Automatisierung

## Aktueller Arbeitsstand — `transfer/kor-nexus-1.20.0`

- [x] Additives SQLite-Ereignisjournal mit Änderungs-Triggern, REST-Replay, SSE-Stream, Polling-Rückfall und Reset bei Replay-Lücken.
- [x] Begrenzte Journal-Aufbewahrung mit konfigurierbarem Umfang von 1.000 bis 1.000.000 Ereignissen; Änderung über Systemeinstellungen, sofortige Bereinigung und getesteter Reset für ältere Cursor.
- [x] Ressourcen-Bewegungsledger mit idempotenten Buchungen, Ausgangsbeständen für Altdaten, Bestandsrichtlinien und deterministischen Warnungen.
- [x] Aufgaben-Fälligkeiten, Prioritäten und Abhängigkeiten mit Zyklusprüfung; geplante Jobs und sichere, allowlist-basierte Automationen.
- [x] Kritische Ressourcenänderungen werden als Aktionsvorschläge gespeichert und benötigen eine bestätigte Freigabe; Routinen sind idempotent.
- [x] Core-Engine-/Automationsarbeitsbereich in der UI; optionaler in-process llama.cpp-Provider über `llama-cpp-python`, read-only Beratungs-API und KI-Panel. Standardprovider bleibt deaktiviert.
- [x] JSON-Schema 2, Backup/Restore und ältere Datenbankstände bleiben durch additive Migrationen und Kompatibilitätstests unterstützt.
- [x] Letzter grüner Release-Gate: 48 API-Tests einschließlich SSE-Replay und Live-Delivery mit zwei Clients, Browser-Smoke-Test sowie nativer Arch-Paketbau und isolierter Installationstest erfolgreich ([Workflow](https://github.com/oORaxaOo/KOR-NEXUS/actions/runs/39032781743)).
- [x] Optionale llama.cpp-Laufzeit nach Stabilisierung des Kerns integriert; manuelle GGUF-Auswahl, isolierte Python-Umgebung und lokale JSON-Konfiguration. Kein automatischer Modell-Download.
- [ ] Reale Modell-Lade- und Hardwareprüfung steht aus; CI verwendet ausschließlich einen Fake-Provider. Ein Modellmanager mit Speicher-/RAM-Schätzung bleibt offen.
- [x] Client wechselt nach Polling-Fallback periodisch zurück zu SSE, dedupliziert Ereignisse und setzt den Cursor bei einem Reset auch nach einer Datenbankwiederherstellung korrekt zurück.
- [x] Ende-zu-Ende-Prüfung bestätigt Replay bereits committeter Ereignisse und Live-Delivery an zwei gleichzeitige SSE-Clients; der Client dedupliziert Events und versucht nach Polling-Fallback erneut SSE.
- [x] Alle Änderungen bleiben auf dem Arbeitsbranch; `main` wurde nicht direkt verändert.


## Release 1.20.0 — Repository-Transfer und Qualitätsprüfung

- [x] Vollständiger 1.20.0-Quellbaum aus den vorhandenen Upload-Artefakten wiederhergestellt; jede wiederverwendete Quelldatei wurde anhand ihrer erwarteten SHA-256-Prüfsumme geprüft.
- [x] Die zwei fehlenden Textdateien `PKGBUILD` und `scripts/test-installation.sh` gezielt rekonstruiert und anschließend durch CI-/Installationstests validiert.
- [x] Ursprüngliche Upload-Archive erhalten und nach `archive/legacy-uploads/` verschoben; temporäre Testdatei, Auditdatei und Übertragungsskript aus dem Projektwurzelverzeichnis entfernt.
- [x] `.gitignore` ergänzt, Vorschaubilder als nicht aktuelle Archiv-Fallbacks gekennzeichnet und den Release-Workflow mit schreibgeschützten Repository-Berechtigungen angelegt.
- [x] 29/29 Kern-API-Tests, Quick-CI, isolierte Benutzerinstallation, Start/Health/Doppelstart/Stop/Deinstallation und Erhalt der Nutzerdaten erfolgreich durchlaufen.
- [x] Offline-Weltkarte überprüft: 177 GeoJSON-Features, 364.876 Byte und verifizierte SHA-256-Prüfsumme.
- [x] Der native Arch-Paketbau einschließlich isoliertem Installationstest wurde in GitHub Actions erfolgreich abgeschlossen: [Workflow-Lauf](https://github.com/oORaxaOo/KOR-NEXUS/actions/runs/38965584870).
- [x] Vollständiger portabler Release-Gate, Browser-Prüfungen, Artefakt-Upload und nativer Arch-Paketbau samt isoliertem Installationstest für Commit `6cfa3450` bestanden ([GitHub Actions](https://github.com/oORaxaOo/KOR-NEXUS/actions/runs/38965869764)).
- [x] Die Änderungen dieser Übertragungsrunde blieben auf `transfer/kor-nexus-1.20.0`; `main` wurde nicht direkt geändert.
- [x] Keine automatische Veröffentlichung, Tag-Erstellung oder Installation auf dem persönlichen NyarchLinux-System.

## Historische Implementierungsstände

## Historischer Implementierungsstand 1.17.0 — Isolierter Arch-Installations- und Integritätstest

- [x] GitHub Actions-Workflow mit getrennten Portable-Quality- und Arch-Paketbau-Jobs angelegt
- [x] Paketverifikation prüft Metadaten und notwendige Payload-Pfade
- [x] Lokale Umgebung erkannt: Debian GNU/Linux 13; makepkg, pacman, Docker und Podman fehlen
- [x] Isoliertes Arch-CI-Integrationstestskript für Paketinstallation, Start/Stop und Datenerhalt ergänzt
- [x] Test nutzt temporäre Daten und dedizierten unprivilegierten Benutzer im kurzlebigen CI-Container
- [x] Keine Installation auf dem persönlichen Zielsystem vorgenommen
- Historischer Hinweis: Remote-CI, nativer Paketbau und Integrationstest standen zum damaligen Versionsstand noch aus; der aktuelle Status steht oben bei Release 1.20.0.

## Release 1.15.0 — CI-Pipeline und automatisierte Release-Gates

Der provider-neutrale Einstieg `scripts/ci.sh` ruft den dokumentierten Release-Gate auf und eignet sich sowohl für lokale Läufe als auch zur Einbindung in einen CI-Anbieter. Es gibt in diesem Arbeitsverzeichnis kein vorhandenes Git-Remote und keine bestehende CI-Konfiguration, daher wurde kein Anbieter ungeprüft vorausgesetzt. Die Prüfungen umfassen Versionskonsistenz, erwartete Paketdateien, Syntax, reproduzierbare Quellarchive, SHA-256, Kern-/Browser- und Installationstests. Der Arch-Paketbau bleibt separat und erfordert ein echtes Arch-System mit `makepkg`; eine Zielsysteminstallation wurde nicht ausgeführt.


- [x] Visuelle Signatur mit technischem Raster, Abschnittsmarkierungen und präziser Typografie
- [x] Hierarchie in Atlas, Dashboard, Nachrichten, Personal und Logistik verfeinert
- [x] Mikroanimationen zurückhaltend ergänzt und reduzierte Bewegung berücksichtigt
- [x] Tastatur-Fokusindikatoren und `prefers-reduced-motion`
- [x] Browser-Smoke-Test um visuelle Signatur und Desktop-/Mobil-Layout ergänzt
- [x] 29 API-Tests bestanden; Browser-Smoke-Test mit 19 Prüfschritten bestanden; Installationsprüfung bestanden
- [x] Screenshots erstellt: `preview/hud-redesign-desktop.png` und `preview/hud-redesign-mobile.png`
- [ ] Zielsystemdarstellung auf NyarchLinux wurde in dieser Umgebung nicht unabhängig verifiziert

## Release 1.11.0 — Live-RSS und Quellenprüfung

- [x] HTTPS-Feed-Quellen, Timeout und Antwortgrößenbegrenzung
- [x] Fehlerhafte/leere XML-Antworten und DTD-/Entity-Deklarationen abgewiesen
- [x] Nur absolute HTTP(S)-Artikellinks ohne Zugangsdaten; Deduplizierung nach ID und URL
- [x] Abruffehler und gültige leere Feeds bewahren den vorhandenen News-Cache
- [x] `last_success` wird bei Fehlschlägen nicht fälschlich aktualisiert; Quellenstatus unterscheidet Fehler und leere Feeds
- [x] Neue RSS-Regressionstests für Parserfehler, Timeout, leere Antwort, Cache-Erhalt, erfolgreiche Aktualisierung, Duplikate und Persistenz
- [x] Offline-Module, Geodaten, Backups, Prozesssperre, JSON-Portabilität, Importvorschau und Installation beibehalten

## Release 1.10.0 — Regionales Lagezentrum und Projekt-Dashboard

- [x] Responsives Projekt-Dashboard mit Region-, Projekt- und Statusfiltern
- [x] API-Aggregation für Projekte, offene Aufgaben, Mitglieder, Ressourcen und Kartenstandorte
- [x] Beziehungen ausschließlich anhand tatsächlicher IDs; Tests mit doppelt vorkommenden Namen
- [x] Status/Fortschritt nur aus vorhandenen Kartenstandorten abgeleitet; unbekannte Werte bleiben explizit unbekannt
- [x] Ressourcen mit Originaleinheit je Zuweisung angezeigt, keine Summe inkompatibler Einheiten
- [x] Zwei zusätzliche API-Tests für Beziehungen, Filter, leere Daten, ungültige Filter und Persistenz; 24 API-Tests insgesamt
- [x] Browser-Smoke-Test für Dashboard, ID-verknüpfte Beziehungsdarstellung, Ressourcen-Einheiten, Statusfilter und leeres Ergebnis
- [x] JSON-Portabilität, Importvorschau, Offline-GeoJSON, Backups, Prozesssperre und Installationspfade unverändert erhalten

## Abgeschlossen

- [x] Ein-Klick-Start über `launch.sh` mit Python 3 Standardbibliothek
- [x] Lokale Loopback-Weboberfläche; Chromium/Chrome-App-Fenster bevorzugt, Browser-Fallback vorhanden
- [x] Fester lokaler Dienst-Port zur Wiederverwendung eines bereits laufenden Kerns
- [x] SQLite-Datenbank im Benutzerprofil mit Schema-Initialisierung/Migrationsversion
- [x] CRUD für Aufgaben und alle Modul-Datensätze; Titel, Beschreibung, Bereich/Region und Tags
- [x] Suchen, Bearbeiten und Löschen von Datensätzen; Aufgabenabhaken, Umbenennen und Löschen
- [x] Atlas-Notizen nach auswählbarer Region und Index für alle 16 Bundesländer
- [x] RSS-Adapter für WELT, tagesschau.de und Deutschlandfunk; lokale Zwischenspeicherung und Quellstatus
- [x] Automatische Start-/Intervall-Backups, manuelle Backups, Retention und Wiederherstellung mit Integritätsprüfung
- [x] JSON-Export/Import mit vorgeschaltetem Sicherheitsbackup
- [x] Grundlegender Deutsch-/Englisch-Umschalter
- [x] Nutzerinstallation mit Menüeintrag/Icon, begrenztem Startprotokoll und sauberem Entfernen der Programmdateien
- [x] Arch-Paketdefinition ohne Cargo-/npm-Runtime-Abhängigkeit, separater Stop-Befehl und Paketinstallation nur mit explizitem `--install`
- [x] Sicherheitsgrenzen für lokale API und externe Feed-Inhalte
- [x] Neunundzwanzig automatisierte Kern-API-Tests einschließlich Einheiten, Ressourcen, Projektzuweisungen, Kartenstandorten und Koordinatenvalidierung
- [x] API-Löschrouten für Profile, Ressourcen und Zuweisungen mit Schutz vor dem Löschen noch zugewiesener Datensätze
- [x] UI für Personenbiografien, Ressourcenbestand und Projektzuweisungen; Personenbezeichnungen können über Einstellungen geändert werden
- [x] SQLite-Tabellen und lokale API-Endpunkte für Einheitenbiografien, Ressourcenbestände und Projektzuweisungen
- [x] Eingabevalidierung und referenzielle Integrität für Zuweisungen
- [x] Verwaltungsmodul Personal & Logistik mit Profil-, Ressourcen- und Projektzuweisungsformularen
- [x] JSON-Export/Import der Kartenstandorte inklusive erneuter Projektzuordnung per Projekttitel
- [x] Offline-Weltkarte aus lokal eingebettetem Natural-Earth-GeoJSON (177 Features; 364.876 Byte)
- [x] Welt-/Deutschland-Ansicht auf echter Welt-/Deutschlandgeometrie; Markerpositionen folgen dem Karten-Ausschnitt
- [x] Lokaler GeoJSON-Import für Bundesland-Polygone mit WGS84-Koordinatenvalidierung
- [x] Importierte Bundesland-Geodaten werden in SQLite gehalten und in Datenbankbackups/JSON-Export einbezogen
- [x] Tests für Geodatenimport, Koordinatenprüfung, Persistenz und Export/Import
- [x] Additive SQLite-Schemamigration v5 für Kartenstatus, Fortschritt und Referenzen zu Aufgaben, Mitgliedern und Ressourcen
- [x] Kartenmarker per Kartenklick positionieren, per Drag-and-drop verschieben, editieren und löschen
- [x] Projektstatus und Fortschritt pro Standort, Such-/Statusfilter und regionale Ressourcenübersicht
- [x] Referenzvalidierung und API-Tests für Projekt-, Aufgaben-, Mitglieder- und Ressourcenverknüpfungen
- [ ] Vollständiger JSON-Export/Import von Mitgliederprofilen, Ressourcen und Projektzuweisungen
- [ ] Amtliche Bundeslandpolygone beziehen, Lizenzvermerk prüfen und als getestetes Asset bündeln
- [ ] Native Desktop-Abnahme auf einem echten Arch-/NyarchLinux-Rechner

## Durchgeführte Verifikation

- Python-Kern und Testdatei: Syntaxkompilierung erfolgreich.
- JavaScript: `node --check web/app.js` erfolgreich.
- Fünfzehn API-Tests bestanden: Gesundheit/Speicherung, Datensatzoperationen/Validierung, Backup/Restore und Aufbewahrung, Einstellungen/Import/Export, Host-/Origin-Schutz, RSS/XML-Parsing, Integrität fehlerhafter Importe, statische Assets und Sicherheitsheader, Kartenmarker-CRUD, Koordinatenvalidierung, Standortbearbeitung, Status-/Fortschrittsgrenzen, Projekt-/Aufgaben-/Mitglieder-/Ressourcenverknüpfungen, lokale Geodatenvalidierung, persistenter Import und GeoJSON-Export/Import.
- Isolierte Benutzerinstallation erfolgreich durchgespielt: Installation, Start über den installierten Launcher, `/api/health`, Auslieferung der Oberfläche, `stop.sh` und Deinstallation bei erhaltener Nutzerdatenbank. Ein Portkonflikt wurde zusätzlich getestet; der Kern wechselte automatisch auf einen freien Loopback-Port.
- Browser-Smoke-Test mit deterministischer Mock-API bestanden: alle sieben Module, 16 Bundesländer, Kartenmarker anlegen/anzeigen/bearbeiten/löschen, Status und Fortschritt, Suche/Filter, bestehende Datensätze beim Modulwechsel, CRUD, Suche, DE/EN, Backupdialog, mobile Ansicht und keine unbehandelten JavaScript-Fehler.
- Ein echter Chrome-/Chromium-Request gegen Loopback wurde in dieser Testumgebung durch Browserrichtlinien blockiert (`ERR_BLOCKED_BY_ADMINISTRATOR`); daher wurde dieser spezielle Echtbrowserpfad nicht als bestanden gezählt. HTTP-/API-Integration und isolierter Launcherstart wurden separat erfolgreich getestet.
- Statischer Frontend-Build erzeugte `dist/index.html`, `dist/styles.css` und `dist/app.js`.

## Bewusst nicht als fertig behauptet

- Die Weltkarte basiert auf tatsächlichen, aber generalisierten Natural-Earth-Geometrien. Die 16 amtlichen Bundeslandpolygone sind nicht gebündelt, da ein konkreter Datensatz in der Umgebung nicht heruntergeladen/verifiziert werden konnte. Der Importweg ist vorhanden; bis zum Import zeigt die Deutschlandansicht nur die generalisierte Deutschlandgeometrie.
- Live-RSS-Abrufe konnten in der eingeschränkten Entwicklungsumgebung nicht gegen die echten externen Anbieter durchgetestet werden (ausgehende DNS-/Netzwerkverbindungen sind gesperrt). Parser, Cache und Fehlerzustände sind automatisiert getestet; mit Internetzugang auf dem Zielrechner werden echte Feeds abgefragt.
- Ein echter Desktop-WebView-Build über Tauri ist nicht Teil des aktiven Ein-Klick-Startpfads. Stattdessen wird die bereits vollständige lokale Weboberfläche in einem Browser-/App-Fenster ausgeführt, damit sie ohne Rust/Cargo-Downloads startbar ist.
- In dieser Entwicklungsumgebung sind `makepkg` und `pacman` nicht verfügbar. Der Arch-Paketbau und die Installation auf NyarchLinux sind deshalb ausdrücklich nicht ausgeführt.
- Performance auf der konkreten Zielhardware mit mindestens 16 GB RAM wurde nicht physisch gemessen.

## Laufzeit-Dateien

- Datenbank: `${XDG_DATA_HOME:-~/.local/share}/kor-workstation/kor-workstation.sqlite3`
- Backups: `${XDG_DATA_HOME:-~/.local/share}/kor-workstation/backups/`
- Programmdateien der Benutzerinstallation: `${XDG_DATA_HOME:-~/.local/share}/kor-workstation-app/`

## Qualitätsziel

Die Kernfunktionen sind lokal ausführbar, persistent und testbar. Kartenpräzision, vollständige englische Übersetzungen, echter Tauri-Wrapper und ein auf einem realen Arch-System erstelltes Installationspaket bleiben klar abgegrenzte Folgearbeit und werden nicht durch Platzhalter als erledigt markiert.


## Release 1.5.0 Entwicklungsnotiz

Die bestehenden Tabellen `units`, `resources` und `project_assignments` werden nun über das siebte Navigationsmodul bedient. Profile und Ressourcen können angelegt und gelöscht werden; eine Löschung wird abgelehnt, solange aktive Projektzuweisungen bestehen. Zuweisungen können erstellt und entfernt werden. Die Personenbezeichnung ist in den Einstellungen anpassbar. API-Tests und der isolierte Browser-Smoke-Test wurden erneut ausgeführt. Koordinatenbasierte Projekt-/Standortmarker bleiben erhalten. Migration v5 ergänzt Status, Fortschritt und persistente optionale Fremdschlüssel auf Projekte, Aufgaben, Mitglieder und Ressourcen. Marker können direkt auf der Karte angelegt/positioniert, gezogen und bearbeitet werden; Suche, Statusfilter und regionale Bestandsübersicht sind ergänzt. Die Weltkarte nutzt eingebettete Natural-Earth-Geometrien. Bundesland-Geodaten können als WGS84-GeoJSON importiert werden und werden in SQLite gespeichert/gesichert. Die exakten Bundeslandgrenzen sind noch nicht gebündelt; Bearbeiten bestehender Personen-/Ressourcendatensätze, vollständiger Export/Import von Personal, Ressourcen und Zuweisungen, Live-RSS-Abnahme und echte Arch-Installation bleiben offen.


## Release 1.6.0 — Karteninteraktion absichern

- [x] SVG-ViewBox-zu-Bildschirmtransformation für Kartenmarker vereinheitlicht; Marker richten sich an tatsächlichen gerenderten SVG-Geometrien aus.
- [x] Drag-and-drop verwendet die invertierte SVG-Screen-Transformation und speichert per PATCH ausschließlich die neuen WGS84-Koordinaten.
- [x] Maus-Pointer-Events, Pointer-Cancel, Schwellwert gegen versehentliches Ziehen und mobile Layoutprüfung ergänzt.
- [x] Kartenklick übernimmt Koordinaten in manuell editierbare Felder; Formular wird nicht automatisch abgesendet.
- [x] API-Test stellt sicher, dass Koordinaten-PATCH Status, Fortschritt, Notizen und alle vier Referenzfelder erhält.
- [ ] Echter Touchscreen-Test: nicht verfügbar in der Entwicklungsumgebung.
- [ ] Installation/Build auf dem NyarchLinux-Zielgerät: nicht durchgeführt.
- [ ] Amtliche Bundeslandgrenzen bleiben weiterhin ein separater offener Geodaten-Meilenstein.


## Release 1.7.0 — Vollständige Datenportabilität

- JSON-Schema 2 deckt Aufgaben, alle Modul-Datensätze, Kartenmarker, Mitgliederprofile/Biografien, Ressourcen, Projektzuweisungen, Einstellungen, importierte Geodaten sowie RSS-Cache und Quellenstatus ab.
- Import referenziert IDs ausschließlich innerhalb der Exportdatei und erstellt daraus neue lokale IDs; die Beziehungen werden über Zuordnungstabellen aufgelöst. SQLite-IDs aus fremden Installationen werden niemals direkt eingesetzt.
- Vollständige Validierung vor Backup und Mutation, Erkennung doppelter IDs und mehrdeutiger Legacy-Titelzuordnungen, Referenzprüfung, Transaktion mit Rollback und abschließende `PRAGMA foreign_key_check`.
- Vor jedem gültigen Import wird ein Integritäts-geprüftes Sicherheitsbackup angelegt. Schema 1 bleibt für ältere JSON-Exporte und Browsermigration verfügbar. Das Exportformat ist in `EXPORT_SCHEMA.md` dokumentiert.
- API-Roundtrip, remappte Fremdschlüssel, Profile/Biografien, Einstellungen/Geodaten, Persistenz nach erneutem Laden und ungültige Referenzen werden automatisiert getestet.
- Verifikationsgrenze: automatisierte API-/Browser-Smoke-Tests sind keine Installation auf einem echten NyarchLinux-Rechner; echter Touchscreen bleibt nicht getestet.


## Release 1.8.0 — Importvorschau und Konfliktbericht

- [x] Neue schreibgeschützte `POST /api/import/preview`-Route mit derselben vollständigen Schema-Validierung wie der finale Import.
- [x] Die Vorschau umgeht den request-getriggerten automatischen Backup-Aufruf; sie schreibt weder Nutzerdaten noch ein Sicherheitsbackup.
- [x] UI-Vorschau zeigt Schema-Version, Aufgaben, Datensätze je Modul, Kartenmarker, Profile, Ressourcen, Projektzuweisungen, Einstellungen, Geodaten-Objekte/Features sowie News-Einträge/Quellen.
- [x] Konfliktbericht für doppelte Export-IDs, mehrdeutige Schema-1-Namenszuordnungen und ungültige Felder/Referenzen; Meldungen enthalten keine privaten Datensatzinhalte oder konkreten Export-ID-Werte.
- [x] Import-Button bleibt bei ungültiger Vorschau gesperrt; der Server validiert beim tatsächlichen Import erneut.
- [x] 20 API-Tests bestanden, darunter schreibgeschützte Vorschau, Backup-Anzahl, unveränderte Inhalte, Duplikate, Legacy-Mehrdeutigkeit, ungültige Felder und eine 1-MiB-Payload.
- [x] Browser-Smoke-Test bestanden: gültige Vorschau, ungültiges Format, deaktivierte Bestätigung und Abbrechen; keine unbehandelten JavaScript-Fehler.
- [ ] Echter NyarchLinux-Paketbuild/Installation weiterhin nicht durchgeführt; `makepkg` ist in der aktuellen Entwicklungsumgebung nicht verfügbar.


## Release 1.9.0 — Installation und Ein-Klick-Start

- [x] Isolierter Installationstest mit Pfaden, die Leerzeichen enthalten; echter Serverstart und Gesundheitsprüfung.
- [x] Doppelstart-Sperre, Stop, Upgrade bei laufendem Server und datenerhaltende Deinstallation automatisiert geprüft.
- [x] Portkonflikt-Fallback mit temporär belegtem Port 8765 geprüft, sofern dieser Port für den Test verfügbar war.
- [x] Fehlender Browser wird durch eine klare Protokollmeldung mit Installationshinweis und lokaler URL gemeldet.
- Benutzerinstallation stoppt vor einer Aktualisierung die eigene laufende Instanz und bricht ab, wenn sie nicht sicher beendet werden konnte.
- Der Python-Kern nutzt eine benutzerspezifische Prozesssperre gegen konkurrierende Starts; der Launcher begrenzt die Protokolldatei mit Rotation.
- Desktop-Datei wird mit korrekt maskiertem Exec-Pfad geschrieben; Icon, Laufzeitstatus und Log-Verzeichnis folgen den XDG-Pfaden.
- Benutzer-Deinstallation entfernt nur Programmdateien und Desktop-Integration; Datenbank, Backups und importierte Geodaten bleiben erhalten.
- Arch-Paket enthält Export-Schema, Release-Hinweise und einen separaten Stop-Befehl. Build-Skript installiert das Paket nicht mehr automatisch, außer bei ausdrücklichem `--install`.
- Arch-Build und Zielsysteminstallation sind nur als ausgeführt zu werten, wenn `makepkg` beziehungsweise die Installation tatsächlich auf einem Arch-System erfolgreich waren.
