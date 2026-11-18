# KOR-NEXUS x Hermes — MCP-Verbindung (Phase I)

Diese Integration stellt Hermes Agent zunächst ausschließlich lesende KOR-NEXUS-Werkzeuge über einen lokalen MCP-Server bereit. KOR-NEXUS bleibt ohne Hermes vollständig funktionsfähig.

## Architektur und Sicherheitsgrenzen

- mcp_server.py stellt MCP-Werkzeuge über STDIO bereit. Hermes startet den Prozess lokal; es wird kein zusätzlicher Netzwerk-Port geöffnet.
- kor_client.py spricht ausschließlich die bestehende KOR-NEXUS-HTTP-API an. Direkter SQLite-Zugriff ist ausgeschlossen.
- Es werden nur Loopback-Adressen (127.0.0.1, localhost, ::1) akzeptiert.
- Vor Datenabfragen prüft der Client /api/health und vergleicht das gemeldete Datenverzeichnis mit dem erwarteten KOR-NEXUS-Benutzerprofil.
- Endpunkte, Ergebnisgrößen und Listenlängen sind begrenzt. Nachrichten werden aus dem vorhandenen RSS-Cache gelesen; MCP löst keinen externen Feed-Abruf aus.
- Alle Werkzeuge sind lesend. Schreiben, Löschen, Restore, Shell-Ausführung und direkte Datenbankzugriffe sind nicht Teil dieser Phase.

## Bereitgestellte Werkzeuge

| MCP-Werkzeug | Zweck |
|---|---|
| kor_get_status | Programmversion, Datenbankstatus und Backup-Anzahl lesen |
| kor_get_system_health | lokale Systemmetriken lesen |
| kor_list_tasks | Aufgaben auflisten |
| kor_list_projects | Projektübersicht mit optionalen Filtern lesen |
| kor_list_records | Atlas-, Projekt-, Archiv-, Simulations- oder Datenbankeinträge lesen |
| kor_list_resources | Ressourcenbestand lesen |
| kor_list_news | lokal zwischengespeicherte RSS-Meldungen lesen |

## Installation

Voraussetzungen: Python 3.11 oder neuer sowie eine laufende lokale KOR-NEXUS-Installation. Die Hermes-MCP-Abhängigkeit wird in einer eigenen virtuellen Umgebung installiert, nicht in der KOR-NEXUS- oder Hermes-Python-Umgebung.

Aus dem Repository- oder Installationsordner ausführen:

    bash integrations/hermes/setup.sh

Das Setup installiert mcp>=2,<3 in einer isolierten Umgebung und gibt den erforderlichen mcp_servers-Konfigurationsblock aus. Es bearbeitet ~/.hermes/config.yaml absichtlich nicht automatisch. Den ausgegebenen Block unter mcp_servers: in diese Datei eintragen und anschließend das Hermes Gateway neu starten.

Wenn KOR-NEXUS per Benutzerinstallation eingerichtet wurde, verwendet das Setup automatisch den installierten App-Ordner unter ~/.local/share/kor-workstation-app, sofern dessen Integrationsdatei vorhanden ist. Bei abweichendem XDG_DATA_HOME wird dieses Verzeichnis verwendet. Mit KOR_NEXUS_APP_ROOT=/absoluter/pfad kann der App-Ordner explizit festgelegt werden.

## Diagnose

Nach dem Setup die vom Setup ausgegebene Python- und doctor.py-Adresse ausführen. Die Diagnose gibt nur Verbindungsstatus und freigegebene Statusdaten aus, keine lokalen Datenverzeichnispfade.

## Tests

Die normalen KOR-NEXUS-Tests benötigen keine MCP-Abhängigkeit:

    python3 -m unittest -v tests.test_hermes_mcp_client

Die MCP-Protokolltests benötigen die isolierte Entwicklungsabhängigkeit:

    python3 -m pip install -r integrations/hermes/requirements.txt
    PYTHONPATH=. python3 -m unittest discover -s integrations/hermes/tests -v

## Noch nicht enthalten

Diese Phase integriert noch kein Chatfenster in das KOR-HUD und registriert noch keinen Hermes-Platform-Adapter. Sie bildet die sichere, lesende Datenschnittstelle. Das HUD/Platform-Plugin und kontrollierte Schreibwerkzeuge folgen als separate Phasen, damit Hermes-Version, Sitzungszuordnung und Bestätigungsabläufe gezielt getestet werden können.
