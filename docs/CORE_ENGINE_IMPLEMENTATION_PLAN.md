# KOR-NEXUS — Implementierungsplan: Core Engine, Live-Updates und optionale lokale KI

Stand: 2026-10-17  
Zielbranch: `transfer/kor-nexus-1.20.0`  
Ausgangsbasis: `main` enthält den integrierten Stand 1.20.0; alle weiteren Änderungen erfolgen ausschließlich im Arbeitsbranch.  
Status: Phase 0 und Phase 1 abgeschlossen (additives Ereignisjournal, REST-Replay, SSE, Polling-Rückfall und Wiederherstellungskompatibilität). Phase 2 in Arbeit: deterministische, schreibgeschützte Engine-Statusberechnung, ein standardmäßig deaktivierter AI-Provider-Vertrag sowie ein additives Ressourcen-Bewegungsledger mit Eröffnungsbestand, Import-Snapshots, Idempotenz und Negativbestands-Schutz sind implementiert. Mindest-/Zielbestandsrichtlinien, deterministische Bestandswarnungen, idempotente Alert-Auswertung und Bestätigung offener Alerts sind implementiert. Portable Sicherung dieser neuen Einstellungen, Automationsregeln, Freigabe-Workflows für kritische Aktionen, Aufgabenabhängigkeiten und llama.cpp-Laufzeit folgen.

## 1. Verbindliche Architekturentscheidungen

- Die deterministische Core Engine und die KI-Integrationsschnittstelle werden parallel entworfen. Die eigentliche llama.cpp-Laufzeit wird erst nach Stabilisierung und Abnahme des Kerns eingebunden.
- Live-Änderungen: Server-Sent Events (SSE), Polling als Rückfall und Replay verpasster Ereignisse über fortlaufende Ereignis-IDs.
- Routinen dürfen nur vorab definierte, idempotente und sichere Aktionen automatisch ausführen. Kritische oder irreversible Aktionen benötigen eine explizite Bestätigung.
- Alle Kernfunktionen müssen vollständig ohne Modell, Netzwerk oder KI-Laufzeit funktionieren.
- Vorhandene Module, API-Verträge, JSON-Import/-Export, Backups, Offline-Kartendaten, Installation und Nutzerdaten bleiben erhalten.
- Bestehende Tabellen werden nicht unüberlegt ersetzt oder umbenannt. Vor der Implementierung wird das tatsächliche Schema aus `initialize()` und vorhandenen Tests inventarisiert.

## 2. Zielarchitektur

```text
Web UI (bestehende Module)
  ├─ bestehende REST-API
  ├─ EventSource /api/events (SSE)
  └─ Polling-Fallback + Replay nach letzter event_id
             │
Local HTTP API (127.0.0.1)
  ├─ Validierung und Berechtigungs-/Bestätigungsgrenzen
  ├─ Domain Services: Tasks, Resources, Projects
  ├─ Core Engine
  │    ├─ deterministische Berechnungen
  │    ├─ Regelprüfung und Fristen
  │    ├─ Scheduler/Job-Runner
  │    └─ Warnungen und Audit-Ereignisse
  ├─ Event Journal / Outbox (SQLite)
  ├─ bestehende Backup-/Import-/Export-Dienste
  └─ optionale AI Provider-Schnittstelle (standardmäßig deaktiviert)
       └─ spätere native llama.cpp-Adapter/Laufzeit
             │
SQLite (bestehende Datenbank; additive Migrationen)
```

Domain Services schreiben Daten und Ereignisjournal in derselben SQLite-Transaktion. SSE publiziert nur bereits committete Ereignisse. Damit gibt es keine Live-Meldung für eine Transaktion, die anschließend zurückgerollt wird.

## 3. Datenbankschema — additive Erweiterung

Die Namen unten sind vorgeschlagene neue Tabellen. Vor dem Coding werden bestehende Tabellen, IDs, Constraints und Schema-Versionierung geprüft; bei Namensüberschneidungen wird ein kompatibler Name gewählt. Bestehende Datensätze werden nicht kopiert oder neu nummeriert, sofern es keinen zwingenden Grund mit getesteter Referenzabbildung gibt.

### 3.1 Migrationen und Ereignisjournal

**`schema_migrations`** (nur ergänzen, falls nicht bereits ein gleichwertiger Mechanismus existiert)
- `version INTEGER PRIMARY KEY`
- `name TEXT NOT NULL`
- `applied_at TEXT NOT NULL`
- `checksum TEXT`

**`event_journal`**
- `event_id INTEGER PRIMARY KEY AUTOINCREMENT` — monotone Replay-Cursor-ID
- `event_uuid TEXT NOT NULL UNIQUE` — stabile UUID für Deduplizierung
- `occurred_at TEXT NOT NULL` — UTC ISO-8601
- `entity_type TEXT NOT NULL` — allowlist, z. B. task/resource/project/alert/routine
- `entity_id TEXT`
- `event_type TEXT NOT NULL` — allowlist, z. B. task.updated/resource.movement.recorded
- `payload_json TEXT NOT NULL` — minimales, versioniertes JSON ohne Geheimnisse
- `schema_version INTEGER NOT NULL DEFAULT 1`
- Indizes: `(event_id)`, `(entity_type, entity_id, event_id)`, `(occurred_at)`

Das Journal ist für Aktualisierungsereignisse und Replay gedacht, nicht als unkontrolliertes Duplikat sämtlicher Datensätze. Payloads enthalten IDs und betroffene Felder; Clients laden aktuelle Zustände über die API nach. Aufbewahrung wird konfigurierbar und begrenzt; der letzte Replay-Cursor bleibt erhalten.

### 3.2 Ressourcenbuchungen

**`resource_movements`**
- `id INTEGER PRIMARY KEY`
- `resource_id INTEGER NOT NULL` — FK auf die vorhandene Ressourcen-Tabelle, tatsächlichen Tabellennamen vor Implementierung prüfen
- `movement_type TEXT NOT NULL` — `opening`, `receipt`, `consumption`, `adjustment`, `reservation`, `reservation_release`
- `quantity REAL NOT NULL CHECK(quantity >= 0)`
- `unit TEXT NOT NULL` — Einheit explizit speichern und gegen Ressourceneinheit validieren
- `project_id INTEGER` — nullable FK auf vorhandene Projekte
- `task_id INTEGER` — nullable FK auf vorhandene Aufgaben
- `reference TEXT`, `note TEXT`
- `created_at TEXT NOT NULL`, `created_by TEXT`
- `idempotency_key TEXT UNIQUE` — schützt vor doppelter Buchung nach Wiederholung eines Requests
- `reverses_movement_id INTEGER` — nullable FK; Korrekturen bevorzugt durch Gegenbuchung statt Löschen

Bestandsregeln: Zugänge erhöhen den physischen Bestand; Verbrauch senkt ihn; Reservierungen verändern nur die reservierte Menge; Freigaben senken die Reservierung. Keine Buchung mit inkompatibler Einheit. Mengen bleiben intern als Dezimalwerte mit definierter Präzision; Rundung erfolgt nur nach expliziter Einheit-/Anzeigeregel. Bestehende Ressourcenmengen werden als unveränderter Ausgangsbestand behandelt; sie werden nicht stillschweigend in erfundene historische Bewegungen umgedeutet. Optional kann nach Bestätigung eine dokumentierte Eröffnungsbuchung erzeugt werden.

Abgeleitete Werte:
- `on_hand = opening_balance + receipts + positive_adjustments - consumption - negative_adjustments`
- `reserved = sum(active reservation) - sum(release)`
- `available = on_hand - reserved`

Die exakte Vorzeichenabbildung wird zentral in einer getesteten Funktion definiert. Überreservierung, negativer Bestand und unzulässige Korrekturen werden je Ressourcentyp durch konfigurierbare Regeln verhindert oder als explizit bestätigte Ausnahme protokolliert. Bestandswerte werden aus Buchungen berechnet, nicht als zweite, unabhängig beschreibbare Wahrheit gespeichert.

### 3.3 Ressourcenregeln und Verbrauchsmetriken

**`resource_policies`**
- `id INTEGER PRIMARY KEY`
- `resource_id INTEGER NOT NULL UNIQUE` — FK zur vorhandenen Ressource
- `minimum_quantity REAL`, `target_quantity REAL`
- `low_stock_enabled INTEGER NOT NULL DEFAULT 1`
- `forecast_window_days INTEGER NOT NULL DEFAULT 14`
- `allow_negative_stock INTEGER NOT NULL DEFAULT 0`
- `updated_at TEXT NOT NULL`

Verbrauchsraten werden aus echten Bewegungen in einem angegebenen Zeitfenster berechnet. Wenn keine ausreichenden Verbrauchsdaten vorhanden sind, zeigt die Engine „Datenbasis unzureichend“ statt eine erfundene Reichweite.

### 3.4 Aufgabenplanung und Abhängigkeiten

Bestehende Aufgaben-Spalten bleiben unverändert. Ergänzungen werden mit `ALTER TABLE ADD COLUMN` nur nach Schema-Prüfung eingeführt, z. B.:
- `due_at TEXT`
- `priority TEXT NOT NULL DEFAULT 'normal'`
- `estimated_minutes INTEGER`
- `actual_minutes INTEGER`
- `recurrence_rule_json TEXT` — validiertes, eingeschränktes Regelobjekt; keine ausführbaren Strings
- `updated_at TEXT` (nur falls kein vorhandenes Änderungsfeld existiert)
- `blocked_reason TEXT` (optional)

**`task_dependencies`**
- `task_id INTEGER NOT NULL` — FK zur vorhandenen Aufgaben-Tabelle
- `depends_on_task_id INTEGER NOT NULL`
- `dependency_type TEXT NOT NULL DEFAULT 'finish_to_start'`
- `created_at TEXT NOT NULL`
- Primärschlüssel `(task_id, depends_on_task_id)`; CHECK gegen Selbstabhängigkeit

Vor dem Einfügen wird ein Zykluscheck ausgeführt. Zyklen werden abgelehnt. Abhängigkeiten ändern nicht stillschweigend den Erledigt-Status: wenn alle Vorgänger erledigt sind, kann eine Aufgabe auf „Bereit“ wechseln oder eine Meldung erzeugen, gemäß expliziter Regel.

### 3.5 Regeln, Jobs, Warnungen und Bestätigungen

**`automation_rules`**
- `id INTEGER PRIMARY KEY`
- `name TEXT NOT NULL`, `enabled INTEGER NOT NULL DEFAULT 0`
- `trigger_type TEXT NOT NULL` — z. B. `schedule`, `event`, `threshold`
- `condition_json TEXT NOT NULL` — validiertes, versioniertes JSON mit Operator-Allowlist
- `action_type TEXT NOT NULL` — Allowlist; keine freie Codeausführung
- `action_config_json TEXT NOT NULL`
- `risk_level TEXT NOT NULL` — `routine` oder `critical`
- `requires_confirmation INTEGER NOT NULL`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

**`scheduled_jobs`**
- `id INTEGER PRIMARY KEY`
- `job_key TEXT NOT NULL UNIQUE` — idempotenter Schlüssel pro Regel und Fälligkeit
- `rule_id INTEGER`, `job_type TEXT NOT NULL`
- `due_at TEXT NOT NULL`, `status TEXT NOT NULL` — pending/running/done/failed/cancelled
- `attempts INTEGER NOT NULL DEFAULT 0`, `last_error TEXT`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`

**`alerts`**
- `id INTEGER PRIMARY KEY`
- `fingerprint TEXT NOT NULL UNIQUE` — unterdrückt doppelte identische Warnungen
- `severity TEXT NOT NULL` — info/warning/critical
- `status TEXT NOT NULL DEFAULT 'open'` — open/acknowledged/resolved
- `source_type TEXT NOT NULL`, `source_id TEXT`
- `title TEXT NOT NULL`, `details_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL`, `resolved_at TEXT`

**`action_proposals`**
- `id INTEGER PRIMARY KEY`
- `proposal_uuid TEXT NOT NULL UNIQUE`
- `action_type TEXT NOT NULL`, `payload_json TEXT NOT NULL`
- `risk_level TEXT NOT NULL`, `status TEXT NOT NULL` — pending/approved/rejected/expired/executed
- `reason TEXT NOT NULL`, `created_at TEXT NOT NULL`, `expires_at TEXT NOT NULL`
- `approved_at TEXT`, `executed_at TEXT`, `idempotency_key TEXT UNIQUE`

Nur serverseitig definierte Aktionshandler dürfen Vorschläge ausführen. Genehmigung bindet an den exakten Payload-Hash; Payloadänderung nach Genehmigung macht die Freigabe ungültig. Löschungen, große Bestandskorrekturen, Datenimporte/-wiederherstellungen und andere kritische Aktionen erfordern explizite Bestätigung. Keine Regel darf Freigabeschranken herabsetzen.

**`engine_runs`** (optional, falls Logs nicht ausreichen)
- `id INTEGER PRIMARY KEY`, `run_type TEXT NOT NULL`, `started_at TEXT NOT NULL`, `finished_at TEXT`
- `status TEXT NOT NULL`, `summary_json TEXT NOT NULL`, `error TEXT`

## 4. API-Verträge

Bestehende Endpunkte bleiben mit identischer Bedeutung und Response-Struktur bestehen. Neue Endpunkte werden versioniert und in den vorhandenen Handler-Stil eingepasst; keine globale API-Umstellung in einem Schritt.

### 4.1 Engine-Status und Ereignisse

- `GET /api/engine/status` → Version der Engine, letzte Prüfung, Scheduler-Status, offene Warnungen, KI-Status (disabled/unavailable/ready). Keine sensiblen Pfade ausgeben.
- `GET /api/events?since=<event_id>` → begrenzte JSON-Seite mit Ereignissen und `next_event_id`; Polling-Fallback und Replay-Endpunkt.
- `GET /api/events/stream?since=<event_id>` → SSE mit `id: <event_id>`, `event: <type>`, `data: <json>`; unterstützt `Last-Event-ID` und `since`.
- Heartbeat-Kommentar regelmäßig; Client-Reconnect mit Backoff. SSE-Streams begrenzen, sauber schließen und unter Last keine DB-Transaktion offen halten.
- Wenn ein Cursor älter als die Journal-Aufbewahrung ist, antwortet Replay mit einem expliziten `reset_required`; Client lädt den relevanten aktuellen Snapshot neu. Kein stilles Überspringen.

### 4.2 Ressourcen

- `GET /api/resources/<id>/ledger` → Bewegungen und berechneter Bestand/Reservierung/verfügbarer Bestand.
- `POST /api/resources/<id>/movements` → validiert Buchung; akzeptiert `Idempotency-Key`; schreibt Buchung, Ereignis und Warnungs-Neuberechnung transaktional.
- `GET /api/resources/<id>/forecast?window_days=N` → Verbrauchsrate, Reichweitenschätzung, Datenqualität und verwendetes Zeitfenster.
- `PUT /api/resources/<id>/policy` → Mindestbestand/Regeln validieren und speichern.
- `POST /api/resources/<id>/movements/<movement_id>/reverse` → Gegenbuchung, nie historische Buchung stillschweigend löschen.

### 4.3 Aufgaben und Automatisierung

- Bestehende Aufgaben-Endpunkte behalten ihren Vertrag.
- `GET /api/tasks?updated_since=<timestamp>` optional für inkrementelles Polling; nur nach Prüfung bestehender Filter/Response.
- `PUT /api/tasks/<id>/schedule` → Fälligkeit, Aufwand und validierte Wiederholung.
- `POST /api/tasks/<id>/dependencies` und `DELETE /api/tasks/<id>/dependencies/<other_id>` → mit Zyklus- und FK-Prüfung.
- `GET /api/alerts`, `POST /api/alerts/<id>/acknowledge`, `POST /api/alerts/<id>/resolve`.
- `GET /api/automation/rules`, `POST /api/automation/rules`, `PATCH /api/automation/rules/<id>` — Regeln standardmäßig deaktiviert, bis validiert und explizit aktiviert.
- `POST /api/actions/<id>/approve` und `POST /api/actions/<id>/reject`; Freigabe mit Ablauf, Payload-Hash und einmaliger Ausführung.
- `GET /api/automation/runs` → Verlauf und Fehlergründe.

Alle Schreib-Requests validieren Typen, Größen, IDs und erlaubte Werte. Mutationen sind atomar, verwenden gebundene SQL-Parameter und erzeugen ein Ereignis erst nach erfolgreicher Validierung.

## 5. SSE, Polling und Replay — Zustandsmodell

1. Beim Start der UI liest der Client einen konsistenten Snapshot und dessen `event_id`.
2. Danach öffnet er SSE mit diesem Cursor.
3. Jedes Event enthält nur IDs/Änderungsart; die UI aktualisiert gezielt betroffene Daten oder lädt sie über die bestehende API neu.
4. Browser-Reconnect sendet `Last-Event-ID`; Server liefert alle verfügbaren Ereignisse nach diesem Cursor.
5. SSE-Ausfall aktiviert Polling von `GET /api/events?since=...` mit begrenztem Intervall und Backoff.
6. Nach SSE-Wiederverbindung stoppt Polling erst nach erfolgreicher Cursor-Synchronisierung.
7. Doppelte Ereignisse sind möglich und müssen clientseitig über `event_id` dedupliziert werden. Cursor wird nur nach erfolgreicher Verarbeitung vorgerückt.
8. Bei Journal-Lücke oder inkompatibler Ereignisversion fordert der Server einen vollständigen Snapshot-Reset an.

## 6. Core Engine und Zeitsteuerung

- Reine Berechnungsfunktionen ohne HTTP-, SQLite- oder KI-Abhängigkeit, z. B. `calculate_resource_balance()`, `calculate_available_stock()`, `calculate_consumption_rate()`, `evaluate_rule()`, `detect_dependency_cycles()`.
- Domain Services orchestrieren Transaktionen und rufen nach dem Commit die Ereignisveröffentlichung an.
- Ein einzelner integrierter Scheduler-Thread prüft fällige Jobs anhand UTC-Zeit, mit DB-Lease/Statuswechsel und idempotenten `job_key`-Werten gegen Doppelverarbeitung.
- Engine-Start führt einen Recovery-Scan für liegengebliebene Jobs aus. Laufzeitfehler blockieren nicht den HTTP-Server; sie werden protokolliert und beim nächsten Zyklus erneut behandelt, soweit sicher.
- Keine Ausführung von Shell-Befehlen, Python-Ausdrücken oder dynamischem Code aus gespeicherten Regeln.
- Zeitzonen: Speicherung intern als UTC ISO-8601; lokale Darstellung im Frontend. Wiederholungen werden als eingeschränkte strukturierte Regeln gespeichert, nicht als beliebige Cron-/Python-Syntax.

## 7. KI-Schnittstelle und spätere native llama.cpp-Laufzeit

Parallel zum Core wird nur ein Provider-Vertrag definiert, noch keine Pflichtabhängigkeit:
- `AIProvider`: `status()`, `generate(request, context)`, `close()`.
- `DisabledAIProvider` ist Standard und muss in der Standardinstallation immer verfügbar sein.
- Engine-/Domain-Services rufen niemals direkt ein Modell auf.
- KI erhält ausschließlich explizit freigegebene, minimierte Kontextdaten; keine direkten Schreibrechte auf SQLite.
- Vorschläge werden in `action_proposals` abgelegt und durch dieselben serverseitigen Aktionshandler/Bestätigungen geprüft wie manuell ausgelöste Vorschläge.
- llama.cpp wird später als optionales natives Modul bzw. gebündelte Bibliothek mit Lizenz- und Herkunftsprüfung eingebunden. Kein separater Serverprozess als Voraussetzung, keine automatische Modell-Download-Aktion ohne Zustimmung.
- Modell-Dateien sind getrennte optionale Assets, nicht Bestandteil des Standardpakets. Prüfsummen, Größenlimit, freie Speicherkapazität, RAM-Schätzung und explizite Nutzerwahl vor Download/Laden.
- Fehler, fehlender Speicher, fehlendes Modell oder deaktivierte KI beeinträchtigen niemals Core Engine, Live-Updates oder bestehende Module.

## 8. Migration, Backups und Rückwärtskompatibilität

1. Zuerst Schema-Inventar und bestehende Migrations-/Backup-Mechanik prüfen.
2. Vor jedem Schema-Schritt automatisch SQLite-Backup anlegen und Integrität prüfen.
3. Migrationen versioniert, vorwärtsgerichtet und idempotent implementieren; pro Version in einer Transaktion, soweit SQLite-DDL dies zulässt.
4. Nur additive Tabellen/Spalten/Indizes. Keine Tabelle löschen, umbenennen oder bestehende Spalten semantisch ändern.
5. Bestehende Datensätze unverändert lassen. Neue optionale Task-Felder erhalten neutrale Defaults/NULL.
6. Ressourcenmigration startet mit einem Snapshot des bisherigen Mengenwerts. Historische Verbräuche werden nicht erfunden. Eröffnungsbuchungen sind optional, dokumentiert und rückverfolgbar.
7. Fremdschlüsselprüfung und `PRAGMA integrity_check` nach Migration; bei Fehler Start abbrechen, Originalbackup behalten und klaren Wiederherstellungshinweis anzeigen.
8. JSON-Import/Export-Schema 2 bleibt lesbar. Neue Felder sind optional; Export erhält einen optionalen `engine`-Abschnitt für Regeln/Policies/Bewegungen, ohne alte Importer zu brechen.
9. Importvorschau zeigt Anzahl neuer Bewegungen/Regeln und Konflikte. Keine automatische Ausführung importierter Regeln; importierte Regeln bleiben deaktiviert. Kritische Import-/Restore-Aktionen erfordern Bestätigung.
10. Restore aus älterem Backup muss weiterhin funktionieren. Nach Restore führt die Engine Schema-Migration und Rebuild abgeleiteter Kennzahlen aus; keine KI wird dafür benötigt.
11. Deinstallation erhält weiterhin Datenbank, Backups, Geodaten und optionale Modell-Dateien, sofern der bestehende Vertrag dies für Nutzerdaten vorsieht; explizite Datenlöschung bleibt ein gesonderter, bestätigungspflichtiger Vorgang.

## 9. Testplan und Abnahmekriterien

### Datenbank und Migration
- Migration von frischer DB und realistisch befüllter 1.20.0-DB.
- Hash-/Row-count-/Referenzvergleich für vorhandene Tabellen vor und nach Migration.
- Fremdschlüsselprüfung, Integritätsprüfung, Wiederholung einer Migration und Rollback/Backup-Recovery.
- Alte JSON-Exporte importieren; alte Clients können neue optionale Felder ignorieren.
- Export → Import → Export bewahrt bestehende Daten und Verknüpfungen.

### Ressourcenbuchungen
- Zugang, Verbrauch, Korrektur, Reservierung, Freigabe und Gegenbuchung mit bekannten Sollwerten.
- Ungültige Einheiten, negative Mengen, Überreservierung und unbekannte IDs abweisen.
- Idempotency-Key verhindert doppelte Buchung bei wiederholtem POST.
- Parallelzugriffe verursachen keine verlorenen Updates; alle Buchungen und Ereignisse sind atomar.
- Verbrauchsprognose mit Daten, ohne Daten, Nullverbrauch und unzureichendem Zeitraum.

### Aufgaben, Regeln und Scheduler
- Fälligkeit, UTC/Zeitzonen-Darstellung, wiederkehrende Aufgaben und Abhängigkeiten.
- Zyklus wird abgelehnt; unvollständige Vorgänger blockieren nur definierte Folgeaktionen.
- Wiederholter Schedulerlauf erzeugt keine doppelten Aufgaben oder Warnungen.
- Routineaktionen werden automatisch ausgeführt; kritische Aktionen bleiben bis zu expliziter Freigabe unverändert.
- Freigabe nach Ablauf, veränderter Payload, doppelter Ausführung oder falscher Aktion wird abgelehnt.
- Scheduler-Ausfall/Neustart und liegengebliebene Jobs werden sicher wieder aufgenommen.

### SSE und Polling
- Ereignis nach Commit sichtbar; kein Ereignis bei Rollback.
- Mehrere Clients, langsamer Client, Verbindungsabbruch, Reconnect mit Last-Event-ID und Replay.
- Polling-Fallback und geordneter Wechsel zurück zu SSE ohne Lücken.
- Duplikate werden dedupliziert; Journal-Lücke erzwingt Snapshot-Reset.
- Client disconnect beendet Stream-Ressourcen; kein DB-Lock bleibt durch offenen Stream gehalten.
- Kein Internet erforderlich; nur Loopback-Bindung bleibt erhalten.

### KI-Isolation
- Sämtliche Core-Tests laufen bei deaktiviertem/fehlendem KI-Modul.
- Mock-Provider für Schnittstellen- und Fehlerfälle; keine Tests benötigen Modell-Download.
- KI-Ausgabe kann nur Vorschläge erzeugen, niemals SQL oder Shell ausführen.
- Ungültiges JSON, Timeout, Speichermangel und Modellfehler führen zu verständlichem Status, nicht zum Ausfall der Anwendung.
- Native llama.cpp-Integration erhält später eigene Hardware-/Speicher-/Lizenz-/Pakettests.

### Regression und Release
- Alle bestehenden 1.20.0-API-, Browser-, Atlas-, Import/Export-, Backup-, RSS-, Installations- und Arch-Pakettests bleiben grün.
- Quick-CI und kompletter Release-Gate.
- Native Arch-Linux-Paketinstallation in isolierter Umgebung, Start/Health/Doppelstart/Stop/Upgrade/Deinstallation.
- Manuelle Smoke-Prüfung: Atlas, Projekte, Archiv, Simulation, Datenbank, Nachrichten, Personal/Logistik, Werkbank und globale Command Palette.

## 10. Implementierungsreihenfolge

**Phase 0 — Inventar und Baseline**
- Bestehendes Schema, Endpunkte, Import/Export, Backup und Tests katalogisieren.
- Baseline-Tests auf Arbeitsbranch durchführen.
- Keine Datenänderung.

**Phase 1 — Fundament**
- Migrationsmanager (falls erforderlich), Event Journal, zentrale Domain-Services und reine Berechnungsfunktionen.
- Regressionstests für unveränderte bestehende APIs.
- Ereignisse zunächst nur serverseitig protokollieren.

**Phase 2 — Ressourcen-Ledger**
- Buchungen, Policies, Bestands-/Verfügbarkeitsberechnung und Ledger-API.
- Kompatible UI-Anzeige für Bestand, reserviert, verfügbar und Historie.

**Phase 3 — Live-Transport**
- SSE, Cursor-Replay, Polling-Fallback, clientseitige Deduplizierung und gezielte Aktualisierung.
- Erst Ressourcen- und Aufgabenbereiche, dann weitere Module.

**Phase 4 — Aufgaben-Engine**
- optionale Fälligkeiten, Abhängigkeiten, Wiederholung und Fortschrittsableitung.
- Zyklusprüfung und keine stillschweigende Statusänderung.

**Phase 5 — Überwachung und sichere Automatisierung**
- Regeln, Scheduler, Warnungen, Vorschläge, Bestätigung, Audit und Idempotenz.
- Standardregeln dokumentieren; alle Regeln zunächst deaktiviert oder nur lesend.

**Phase 6 — KI parallel vorbereiten**
- Provider-Schnittstelle, deaktivierter Standardprovider, Kontextbegrenzung und Vorschlagsformat.
- Contract-Tests mit Mock; keine llama.cpp-Laufzeit im kritischen Kern.

**Phase 7 — Native KI nach Kernstabilisierung**
- llama.cpp optional integrieren, Modellverwaltung und Speicherprüfung.
- Separater Test- und Paketpfad; Funktion ohne Modell beibehalten.

**Phase 8 — Verifikation und Pull Request**
- Gesamte Regression, Migration von Testdatenbank, Arch-Paket, Dokumentation und Upgrade-Pfad.
- PR gegen `main`; kein direkter Commit auf `main`.
- Merge erst nach grüner CI und Review.

## 11. Definition of Done

- Bestehende Nutzerdaten und Funktionen bleiben nach Upgrade, Import/Export, Backup/Restore und Deinstallationserwartung erhalten.
- Ressourcenbestände werden aus nachvollziehbaren Bewegungen berechnet.
- Live-Änderungen erscheinen über SSE; Polling und Replay decken Ausfälle ohne stille Lücken ab.
- Regeln und Routinen sind idempotent, protokolliert und serverseitig beschränkt.
- Kritische Aktionen benötigen bestätigte, unveränderte Aktionspayloads.
- Core Engine läuft ohne KI, Netzwerk und externe KI-Prozesse.
- llama.cpp ist optional und wird erst nach Stabilisierung des Kerns als native Laufzeit freigegeben.
- Alle bestehenden und neuen CI-Gates sind grün; keine Änderungen direkt auf `main`.
