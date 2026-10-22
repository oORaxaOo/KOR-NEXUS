# KOR-NEXUS Änderungsprotokoll

## Unveröffentlicht — GitHub Development Center (Feature-Branch)

- GitHub-Kommandozentrale ergänzt: autorisierte Repositories, Branches, offene Issues/PRs, Commits und Actions.
- Repository- und Branch-Listen vollständig paginiert; ungültige Branch-Referenzen und übergroße Ergebnisse werden explizit abgewiesen.
- Token nur zur Laufzeit aus GitHub CLI bzw. Umgebungsvariablen; keine Speicherung in der Datenbank und keine Ausgabe an das Frontend.
- Bestätigung vor Issue-, Branch-, PR- und Workflow-Schreibaktionen; kein automatischer Push oder Merge.

## 1.20.0 — Repository-Transfer, Bereinigung und Release-Gates

- Den vollständigen Projektbaum in `transfer/kor-nexus-1.20.0` wiederhergestellt und die Platzhalter-README durch eine aktuelle Projektübersicht ersetzt.
- Die Originaluploads nach `archive/legacy-uploads/` verschoben, statt sie zu löschen; die aktive Codebasis liegt nun in klaren Quell-, Web-, Packaging-, Skript- und Dokumentationspfaden.
- `.gitignore` für Python-Caches, Umgebungen, Build-Ausgaben, Laufzeitdatenbanken, Logs, Backups und lokale Secrets ergänzt.
- Den Release-Workflow für portable Qualitäts- und Browser-Prüfungen sowie nativen Arch-Paketbau einschließlich isoliertem Paket-Installationstest eingerichtet. Der Workflow erzeugt CI-Artefakte, aber keine automatischen Releases oder Tags.
- Eine temporäre Transfer-Workflow-Datei nach erfolgreicher Wiederherstellung wieder entfernt; die normale Release-Pipeline bleibt erhalten.
- 29 Kern-API-Tests, Quick-CI und den isolierten Benutzer-Installationstest erfolgreich ausgeführt. Offline-Weltkarte und SHA-256-Prüfsumme bestätigt.
- Der vollständige portable Release-Gate einschließlich Browser-Prüfungen und Artefakt-Upload sowie der native Arch-Paketbau samt isoliertem Installationstest bestanden für Commit `6cfa3450` ([GitHub Actions](https://github.com/oORaxaOo/KOR-NEXUS/actions/runs/38965869764)).
- Die alten Screenshots als Archiv-Fallbacks dokumentiert, damit sie nicht versehentlich als aktuelle Browser-Testresultate ausgegeben werden.
- `main` wurde durch diese Transfer-Bereinigung nicht direkt verändert.

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
