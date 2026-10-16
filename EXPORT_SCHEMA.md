# KOR-NEXUS JSON-Exportformat

## Schema-Versionen

- **Schema 2** ist das aktuelle vollständige Format, exportiert von `GET /api/export` und importiert über `POST /api/import` mit `{ "data": <Exportobjekt> }`.
- **Schema 1** wird weiterhin angenommen. Es enthält üblicherweise `tasks`, `records`, `map_locations`, `settings` und `geodata`; es kann ältere Einträge ohne numerische IDs enthalten. Falls eine alte Marker-Verknüpfung nur über einen Namen auflösbar ist, muss der Name eindeutig sein.
- Unbekannte Schema-Versionen werden abgewiesen.

## Schema 2 Felder

| Feld | Inhalt |
|---|---|
| `schema_version` | Ganzzahl `2` |
| `app`, `exported_at`, `id_policy` | Herkunft und Erklärung der ID-Regel |
| `tasks[]` | Aufgaben: `id`, `title`, `area`, `done`, Zeitstempel |
| `records[]` | Alle Datensatzmodule: `id`, `module`, `title`, `body`, `region`, `tags`, Zeitstempel |
| `map_locations[]` | Marker: Koordinaten, Status, Fortschritt, Notizen, Zeitstempel und Referenzen `project_id`, `task_id`, `unit_id`, `resource_id`; lesbare `*_title`/`*_name`-Felder sind nur ergänzende Beschriftungen |
| `units[]` | Mitgliederprofile einschließlich `biography`, Rolle, Status, Region, Tags und Zeitstempel |
| `resources[]` | Ressourcen einschließlich Kategorie, Menge, Einheit, Ort, Notizen und Zeitstempel |
| `project_assignments[]` | Projekt-, Mitglieds- oder Ressourcenverknüpfungen, Menge, Notizen und Zeitstempel |
| `settings` | Schlüssel/Wert-Objekt der Anwendungseinstellungen |
| `geodata` | GeoJSON-Objekte; der interne Schlüssel `germany-states` wird im JSON aus Kompatibilitätsgründen als `germany_states` geschrieben |
| `news.items[]` | Lokal zwischengespeicherte RSS-Meldungen |
| `news.sources[]` | Status der RSS-Quellen |

## ID- und Beziehungsregeln

1. Die IDs im Export sind **Paket-IDs**. Sie dienen dazu, Referenzen innerhalb derselben Datei zu verbinden und sind keine Aufforderung, diese SQLite-IDs in einer anderen Installation zu übernehmen.
2. Der Import baut für jede Entität eine Zuordnung von Paket-ID auf neu erzeugte lokale SQLite-ID auf. Marker und Projektzuweisungen werden ausschließlich durch diese Zuordnung verknüpft.
3. Schema 2 erfordert eindeutige, nichtleere IDs für jeden Eintrag der strukturierten Entitätslisten. Doppelte IDs, fehlende Ziele, Projektverweise auf Nicht-Projekte und ungültige Mengen/Koordinaten führen zum Abbruch.
4. Bei Schema 1 darf ein fehlender/unpassender Fremdschlüssel nur dann anhand von Titel oder Name rekonstruiert werden, wenn der Zielname eindeutig ist. Mehrdeutige Zuordnungen werden nicht geraten.
5. Das Programm validiert die gesamte Datei vor dem Backup und vor Änderungen. Danach wird ein Sicherheitsbackup angelegt, der Austausch läuft in einer SQLite-Transaktion und `PRAGMA foreign_key_check` wird ausgeführt. Bei einem Fehler wird die Transaktion zurückgerollt.
6. Schema 2 ersetzt die exportabgedeckten Tabellen und Geodaten. Ein Schema-1-Import bleibt auf die von diesem älteren Format dargestellten Daten begrenzt; Mitglieder-/Ressourcenlisten werden nicht aus einem fehlenden Feld erfunden.

## Größen- und Inhaltsgrenzen

Der lokale API-Request ist auf 12 MiB begrenzt; die Oberfläche akzeptiert JSON-Dateien bis 10 MiB. Titel, Tags, Koordinaten, Geometrien, Mengen und Referenzen werden serverseitig geprüft. Große/ungültige Dateien sind vor dem Import entsprechend zu verkleinern oder zu korrigieren. Das JSON enthält personenbezogene Biografien und Notizen: Exporte sind entsprechend vertraulich zu behandeln.


## Importvorschau (ab Anwendungsversion 1.8.0)

`POST /api/import/preview` erwartet `{ "data": <Exportobjekt> }` und liefert `{ "ok": true, "valid": boolean, "summary": ..., "issues": [...], "note": ... }`. `summary` zählt Schema-Version, Aufgaben, Datensätze gesamt und je Modul, Kartenmarker, Profile, Ressourcen, Projektzuweisungen, Einstellungen, Geodatenobjekte und Features sowie News-Einträge und -Quellen. `issues` enthält stabile Konfliktcodes und datenschutzbewusste Meldungen, unter anderem `duplicate_ids`, `ambiguous_legacy_mapping`, `missing_reference`, `invalid_fields` und `validation_failed`. Es werden keine Rohinhalte von Biografien/Notizen oder konkrete Paket-ID-Werte im Konfliktbericht ausgegeben.

Die Vorschau liest und validiert ausschließlich den übermittelten JSON-Inhalt; sie verändert weder die SQLite-Datenbank noch legt sie ein Sicherheitsbackup an. Der endgültige `POST /api/import`-Aufruf validiert unabhängig erneut. Erst nach erfolgreicher Validierung wird das Integritäts-geprüfte Sicherheitsbackup erstellt, bevor die transaktionale Ersetzung beginnt. Die Vorschau ist keine Reservierung und keine Garantie, dass der spätere Import ohne Fehler gelingt (z. B. bei einem zwischenzeitlichen Datenbank- oder Dateisystemfehler).
