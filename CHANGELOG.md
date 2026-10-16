## 1.20.0 — Repository eindeutig identifiziert; Remote-CI weiterhin offen

- GitHub-Connector identifizierte `oORaxaOo/KOR-NEXUS` anhand des exakten Repository-Namens und Besitzers; Standardbranch `main`.
- Connector meldet Admin-/Push-Berechtigungen für die verbundene Identität. Diese Berechtigungen wurden nicht zum Ändern des Remote verwendet.
- Remote-README ist ein kurzer Platzhalter. `.github/workflows/release.yml` fehlt im Remote-Branch (`404`); ein Remote-Workflow-Lauf ist nicht nachgewiesen.
- Die lokale Arbeitskopie besitzt kein `.git` und keinen Remote. Kein Commit, Push, Workflow-Dispatch oder Remote-Release wurde ausgeführt.
- Lokaler Quick-Release-Check, 29 Kern-API-Tests, 19 Browser-Prüfungen und isolierter Benutzer-Installationstest bestanden. Ein kombinierter Full-Check überschritt einmal das Zeitlimit; die Testgruppen wurden anschließend separat erfolgreich ausgeführt.
- Archive wurden neu erzeugt und Integrität sowie SHA-256-Prüfsummen verifiziert; nativer Arch-Paketbau und echter Remote-CI-Lauf bleiben offen.

## 1.19.0 — Repository-Zuordnung und CI-Status

- GitHub-Connector-Repositories aufgelistet und gezielt nach `KOR-NEXUS` sowie `kor nexus` gesucht.
- Kein eindeutig zugeordnetes Repository gefunden; die zwei sichtbaren privaten Repositories hatten keinen abrufbaren `.github/workflows/release.yml`-Pfad.
- Lokale Projektkopie ohne `.git` und ohne Remote bestätigt. Für die Zuordnung fehlt die kanonische Repository-URL oder der exakte `owner/repository`-Name.
- Kein Workflow-Dispatch, Commit, Push oder Release ausgelöst. Echter CI-Lauf bleibt offen.
- Aktive Versionsmarken auf 1.19.0 angehoben; bestehende Funktionen und Offline-Geodaten unverändert beibehalten.

## 1.18.0 — CI-Validierung und sicherer erster Lauf

- Arch-CI-Job fail-closed gehärtet: genau ein frisch gebautes Paket, Metadaten- und Dateilistenprüfung, anschließend Installationstest mit Zeitlimit.
- Arch-Paket-Artefakt wird erst nach erfolgreichem Installationstest hochgeladen; kein automatisches GitHub-Release und kein Push.
- Neue `CI_MANUAL_START.md` dokumentiert Connector-/Remote-Befund und manuellen Start. Echter CI-Lauf bleibt offen, bis ein eindeutig zugeordnetes Repository und ein Laufresultat vorliegen.

# KOR-NEXUS Änderungsprotokoll

## 1.17.0 — Isolierter Arch-Installations- und Integritätstest

- CI-Workflow erweitert: nach dem nativen `makepkg`-Build wird das Paket in demselben wegwerfbaren Arch-Linux-Container installiert und funktional geprüft.
- Neues `scripts/test-built-package-installation.sh` prüft installierte Dateipfade, ausführbare Launcher, Desktop-Eintrag, Offline-Weltkarte, Start, Health-Endpunkt, Einzelinstanzverhalten, Stop, SQLite-Erstellung und datenerhaltende Paketdeinstallation.
- Der Integrationstest verwendet einen eigens angelegten unprivilegierten Testbenutzer und temporäre XDG-Datenpfade; der Testcontainer wird nach Abschluss verworfen.
- Keine Installation auf einem persönlichen NyarchLinux-System. Der native Build und der CI-Integrationstest bleiben unbestätigt, bis der Remote-Workflow tatsächlich ausgeführt wurde.

## 1.15.0 — CI-Pipeline und automatisierte Release-Gates

- Provider-neutrales CI-Einstiegsskript `scripts/ci.sh` ergänzt, das denselben reproduzierbaren Release-Gate lokal und in CI ausführt.
- GitHub Actions wurde nicht voreilig festgelegt: Im Arbeitsverzeichnis ist kein Git-Remote und keine vorhandene CI-Konfiguration hinterlegt. Der portable Einstieg kann in einen später gewählten CI-Anbieter eingebunden werden.
- Release-Prüfung vergleicht zwei unabhängig erzeugte Quellarchive anhand SHA-256 und prüft Versionskonsistenz, erwartete Paketdateien, Syntax, Archivinhalt, Kern-API-, Browser- und Installationstests.
- Arch-spezifischer Paketbau bleibt getrennt; fehlendes `makepkg` ist ein explizit gemeldeter, nicht ausgeführter Schritt. Keine Zielsysteminstallation wird behauptet.
- Anwendungsfunktionen, API, Datenbeziehungen, Offline-Geodaten und Installationspfade bleiben erhalten.


## 1.13.0 — HUD-Verfeinerung und visuelle Signatur

- Aufbauend auf 1.12.0 die visuelle Identität mit technischer Rasterlogik, markanten Abschnittsmarkierungen und präziserer typografischer Hierarchie weiterentwickelt.
- Mikroanimationen für Navigation, Karten und Projektkarten zurückhaltend ergänzt; Animationen bleiben bei `prefers-reduced-motion` deaktiviert.
- Kopfzeile, Navigation, Seitenleiste, Karten, Formulare, Dialoge, Statusanzeigen, Kartenoberfläche und Nachrichtenansicht gestalterisch vereinheitlicht.
- Dashboard-Kennzahlen und Projektkarten mit besserer visueller Hierarchie und lesbarer Informationsdichte gestaltet.
- Mobile Navigation und Eingabeflächen optimiert; horizontales Überlaufen im 390-px-Testfenster wird geprüft.
- Sichtbare Tastatur-Fokuszustände und `prefers-reduced-motion` ergänzt.
- Browser-Smoke-Test um Design-Token-, Mobile-Overflow- und Barrierefreiheits-Prüfungen erweitert; Desktop- und Mobil-Screenshots werden erzeugt.
- Keine API- oder Datenmodelländerung; Module, Offline-Geodaten, RSS, JSON-Portabilität, Importvorschau, Backups, Prozesssperre und Installationswege bleiben bestehen.


## 1.11.0 — Live-RSS und Quellenprüfung

- RSS-/Atom-Abruf mit fünf Sekunden Timeout, Größenbegrenzung, HTTPS-Quellenprüfung und verständlichem Quellenstatus verbessert.
- Leere/fehlerhafte XML-Antworten und DTD-/Entity-Deklarationen werden abgewiesen; unsichere Artikel-URLs, Zugangsdaten und doppelte URLs werden verworfen.
- Abruffehler und gültige leere Feeds löschen den vorhandenen Cache nicht; `last_success` bleibt bei Fehlschlägen unverändert.
- Quellenstatus und gespeicherte Meldungen bleiben auch offline verfügbar; keine erfundenen Nachrichten oder Erfolgszustände.
- Neue API-/Kernprüfungen für XML-Fehler, leere Antwort, DTD, Timeout, Cache-Erhalt, Duplikate, erfolgreiche Aktualisierung und Persistenz.

## 1.10.0 — Regionales Lagezentrum und Projekt-Dashboard

- Neues responsives Lage-Dashboard mit Filtern für Region, Projekt-ID und Status sowie Kennzahlen zu Projekten, offenen Aufgaben, Mitgliedern und Kartenstandorten.
- Neue API `GET /api/dashboard/projects`: Beziehungen werden über IDs aufgelöst; gleiche Namen bleiben getrennte Datensätze.
- Offene Aufgaben werden nur aus tatsächlichen `task_id`-Verknüpfungen an Kartenstandorten abgeleitet; Mitglieder und Ressourcen aus Projektzuweisungen; Kartenstandorte über `project_id`.
- Fortschritt und Status werden transparent aus vorhandenen Standortdaten abgeleitet; fehlende Werte bleiben unbekannt statt als Null/Planstatus ausgegeben zu werden.
- Ressourcenmengen bleiben je Ressource samt Einheit getrennt; keine Addition inkompatibler Einheiten.
- 2 neue API-Tests decken ID-basierte Beziehungen, doppelte Namen, Filter, leere Daten, ungültige Filter, fehlende Werte und Persistenz ab. Browser-Smoke-Test ergänzt um Beziehungen, Ressourcen-Einheiten und leere Filterergebnisse.
- Bestehende JSON-Export-/Importportabilität, Importvorschau, Offline-Geodaten, Backup-/Restore-Verhalten, Prozesssperre und sichere Installationspfade beibehalten.


## 1.9.0 — Installation und Ein-Klick-Start

- Benutzerinstallation beendet vor dem Austausch der Dateien eine laufende Instanz und bricht sicher ab, falls sie weiterläuft.
- Der Python-Kern nutzt eine prozessweite Sperre für alle Startwege; die Wiederverwendung prüft auch das Datenverzeichnis, damit eine andere KOR-Instanz mit eigenem Profil nicht fälschlich übernommen wird. Der Launcher rotiert Protokolle und meldet fehlende Browser mit einem klaren Hinweis.
- Desktop-Menüpfade werden mit Desktop-Entry-kompatibler Maskierung erzeugt; XDG-Daten-, Zustands- und Icon-Verzeichnisse werden berücksichtigt.
- Benutzer-Deinstallation entfernt nur Programmdateien und Desktop-Integration; Datenbank, Backups und importierte Geodaten bleiben unangetastet.
- Arch-Paket ergänzt `kor-workstation-stop`, Export-Schema und vollständige Release-Dokumentation. Build-Skript installiert nur mit explizitem `--install`.
- Ergänzende isolierte Installations- und Start/Stop-Tests.

## 1.8.0 — Importvorschau und Konfliktbericht

- Neue schreibgeschützte API-Vorschau unter `POST /api/import/preview`; keine Datenmutation und kein durch diesen Request ausgelöstes Backup.
- Vorschau zeigt Schema-Version, Zählwerte pro Modul, Profile, Ressourcen, Zuweisungen, Einstellungen, Geodaten-Features und News-Cache.
- Datenschutzbewusster Konfliktbericht meldet doppelte IDs, mehrdeutige Schema-1-Zuordnungen und serverseitig erkannte ungültige Felder/Referenzen ohne rohe private Inhalte offenzulegen.
- Endgültiger Import validiert erneut, erstellt danach das Sicherheitsbackup und behält transaktionalen Rollback, ID-Remapping und Fremdschlüsselprüfung.
- API-Tests für unveränderte Daten/Backups, doppelte IDs, mehrdeutige Legacy-Namen, ungültige Dateien und große Vorschau-Payloads; Browser-Smoke-Test für gültige und ungültige Vorschau.

## 1.7.0 — Vollständige Datenportabilität

- JSON-Schema 2 ergänzt vollständigen Export/Import von Aufgaben, sämtlichen Modul-Datensätzen, Kartenmarkern, Personenprofilen/Biografien, Ressourcen, Projektzuweisungen, Einstellungen, importierten Geodaten und News-Cache.
- Export-IDs dienen nur als Referenzen innerhalb der Datei; der Import vergibt neue lokale SQLite-IDs und erhält alle Beziehungen über Zuordnungstabellen.
- Vollständige Vorabvalidierung, Erkennung doppelter IDs und mehrdeutiger Legacy-Zuordnungen, Backup vor Mutation, transaktionaler Rollback und Fremdschlüsselprüfung ergänzt.
- Schema-1-Importe bleiben kompatibel; `EXPORT_SCHEMA.md` dokumentiert Aufbau, Regeln und Grenzen.
- Automatisierte Roundtrip-, Remapping-, Persistenz-, Legacy- und Fehlerfalltests ergänzt.

## 1.6.0 — Robuste Karteninteraktion

- Markerpositionen über die echte SVG-Screen-Transformation ausgerichtet, auch bei abweichendem Seitenverhältnis.
- Kartenklick übernimmt WGS84-Koordinaten in das Standortformular, ohne Datensätze automatisch anzulegen.
- Marker-Drag mit Pointer Events speichert nur die beiden Koordinatenfelder und erhält so alle bestehenden Beziehungen, Status-, Fortschritts- und Notizdaten.
- Pointer-Cancel, Drag-Bewegungsschwelle und Browser-Smoke-Tests für Desktop- und schmale Viewports ergänzt.
- API-Tests prüfen explizit, dass Koordinaten-PATCH Fremdschlüssel und nicht betroffene Daten erhält und ungültige WGS84-Werte abweist.
- Nicht durchgeführt: Test mit echtem Touchscreen und Installation auf dem NyarchLinux-Zielgerät.

## 1.5.0 — Strategische Projektplanung

- Georeferenzierte Standortmarker mit Status, Fortschritt und Beziehungen zu Projekten, Aufgaben, Mitgliedern und Ressourcen.
- Filter, Suche und regionale Ressourcenübersicht.

## 1.4.0 — Geografischer Atlas

- Lokal eingebettete Natural-Earth-Weltgeometrien und GeoJSON-Import für optionale Bundeslandgrenzen.
