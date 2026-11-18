# Hermes-Integration für KOR-NEXUS

Diese optionale Integration verbindet Hermes Agent über einen eigenständigen MCP-Server mit der lokalen KOR-NEXUS-Instanz.

## Sicherheits- und Architekturgrenzen

- MCP verwendet stdio. Hermes startet den Server als Kindprozess; es wird kein zusätzlicher Netzwerkport geöffnet.
- Der Adapter spricht ausschließlich mit der lokalen KOR-NEXUS-HTTP-API.
- Der Adapter öffnet niemals die SQLite-Datenbank, liest keine Backups und besitzt keine Shell- oder Dateisystemwerkzeuge.
- Die MCP-Schnittstelle stellt Lesezugriffe sowie klar begrenzte Erstellung/Bearbeitung von Aufgaben und strukturierten Einträgen bereit. Der API-Client erlaubt POST ausschließlich für `/api/tasks` und `/api/records`, PATCH ausschließlich für konkrete Aufgaben- und Eintrags-IDs. DELETE, PUT, Import, Restore, Ressourcenänderungen und Shell-Zugriffe sind nicht freigegeben.
- Inhalte aus KOR-NEXUS sind Daten und dürfen keine System- oder Toolrichtlinien überschreiben.
- Der Installer bearbeitet die Hermes-Konfiguration nicht automatisch.

## Voraussetzungen

- KOR-NEXUS muss lokal gestartet sein.
- Python 3.11 oder neuer.
- Hermes Agent mit MCP-Unterstützung.
- Internetzugriff während der einmaligen Installation des MCP-Python-SDK.

## Installation

Im KOR-NEXUS-Projektordner:

    bash integrations/hermes/install.sh

Der Installer legt eine separate virtuelle Umgebung und eine Konfigurationsvorlage unter dem KOR-NEXUS-Datenverzeichnis an (Standard: ~/.local/share/kor-workstation/hermes-integration/). Hermes selbst und die KOR-NEXUS-Core-Abhängigkeiten werden nicht verändert.

Öffne anschließend die erzeugte hermes-mcp-config.yaml und übernimm deren kor_nexus-Eintrag in den bestehenden mcp_servers-Abschnitt deiner ~/.hermes/config.yaml. Einen vorhandenen mcp_servers-Abschnitt nicht doppelt anlegen.

Die Vorlage setzt keine feste API-Adresse. Der MCP-Client liest runtime.json im KOR-NEXUS-Datenverzeichnis aus und erkennt dadurch auch einen automatisch ausgewählten Port. Optional kann KOR_NEXUS_BASE_URL im env-Abschnitt auf eine andere lokale Adresse gesetzt werden.

Anschließend:

    hermes mcp test kor_nexus

Danach eine neue Hermes-Sitzung öffnen oder /reload-mcp verwenden.

## Verfügbare Werkzeuge

| Werkzeug | Zweck |
|---|---|
| kor_get_status | Core-Status und Datenbankintegrität abrufen |
| kor_list_tasks | Aufgaben auflisten |
| kor_list_projects | Projekte auflisten |
| kor_list_records | Atlas-, Archiv-, Simulations- und Datenbankeinträge auflisten |
| kor_list_resources | Ressourcenbestand abrufen |
| kor_get_alerts | Engine-Warnmeldungen abrufen |
| kor_get_dashboard | Regionale Projektübersicht abrufen |
| kor_get_events | Ereignisse ab einem Journal-Cursor abrufen |
| kor_create_task | Aufgabe mit Titel, Bereich, Priorität und optionalem Fälligkeitsdatum anlegen |
| kor_update_task | Bestimmte Aufgabenfelder bearbeiten oder Aufgabe abschließen |
| kor_create_record | Eintrag in Atlas, Projekte, Archiv, Simulation oder Datenbank erstellen |
| kor_update_record | Bestehenden Eintrag anhand seiner ID bearbeiten |

Listenwerkzeuge liefern höchstens 200 Einträge; Ereignisabfragen höchstens 500 Ereignisse. Schreibwerkzeuge können ausschließlich Aufgaben und strukturierte Einträge anlegen oder bearbeiten. Es gibt keine Löschfunktion und keine Werkzeuge zum Import, Restore, direkten SQL-Zugriff oder zur Änderung von Ressourcenbeständen.

## Fehlerbehebung

- KOR-NEXUS ist lokal nicht erreichbar: KOR-NEXUS starten und anschließend runtime.json beziehungsweise KOR_NEXUS_BASE_URL prüfen.
- Das MCP-Paket fehlt: integrations/hermes/install.sh erneut ausführen.
- Der Server erscheint nicht: den Eintrag unter mcp_servers prüfen und MCP neu laden.
- Diagnosemeldungen werden an stderr ausgegeben; stdout bleibt dem MCP-Protokoll vorbehalten.

## Tests

    PYTHONPATH=integrations/hermes/mcp_server python3 -m unittest discover -s integrations/hermes/mcp_server/tests -v
    python3 -m py_compile integrations/hermes/mcp_server/kor_client.py integrations/hermes/mcp_server/server.py
    bash -n integrations/hermes/install.sh


## Vollständige HUD- und Kanalintegration (Variante C)

Der Installer richtet zusätzlich das native Hermes-Gateway-Platform-Plugin ein:

    ~/.hermes/plugins/kor-nexus-panel/

Das Plugin ergänzt Hermes um die Plattform kor_nexus. Nachrichten aus dem KOR-NEXUS-HUD werden dadurch über denselben GatewayRunner und denselben aktiven Lilith-Agenten verarbeitet wie WhatsApp, Discord und andere bereits verbundene Hermes-Kanäle. Der Chat-Sitzungsschlüssel des HUD bleibt separat; die Agentenidentität, Werkzeugfreigaben und das Hermes-Langzeitgedächtnis bleiben gemeinsam.

### Hermes-Konfiguration ergänzen

Die vom Installer erzeugte hermes-platform-config.yaml enthält:

    gateway:
      platforms:
        kor_nexus:
          enabled: true
          extra:
            port: 9876
            allowed_users:
              - local-owner

Diesen Abschnitt in den bestehenden gateway.platforms-Block der ~/.hermes/config.yaml übernehmen. Den bereits vorhandenen Block nicht überschreiben oder ein zweites gateway:-Element anlegen. Zusätzlich den MCP-Eintrag aus hermes-mcp-config.yaml unter den vorhandenen mcp_servers:-Abschnitt übernehmen.


Die Plattform nutzt eine explizite Hermes-Allowlist für die feste lokale Identität `local-owner`. Der Adapter erklärt eingehende Nachrichten ausdrücklich **nicht** zu vertrauenswürdigen Upstream-Nachrichten und umgeht damit keine normalen Gateway-Autorisierungsprüfungen. Die Liste muss auf `local-owner` beschränkt bleiben; keine Wildcards oder globale Freigabe eintragen.

Das installierte User-Plugin zusätzlich aktivieren:

    hermes plugins enable kor-nexus-panel

Anschließend das Hermes-Gateway neu starten. Beim erfolgreichen Start erzeugt das Plugin eine private Verbindungsdatei unter $XDG_CONFIG_HOME/kor-nexus/hermes-bridge.json (Standard: ~/.config/kor-nexus/hermes-bridge.json). Sie enthält ein zufälliges Zugriffstoken und wird mit Dateirechten 0600 geschrieben. Das Verzeichnis wird auf 0700 gesetzt. KOR-NEXUS liest diese Datei serverseitig; das Token wird niemals an den Browser ausgeliefert.

Hermes und KOR-NEXUS müssen dasselbe HOME/XDG_CONFIG_HOME verwenden. Bei abweichender Konfiguration kann KOR_NEXUS_HERMES_CONFIG auf beiden Prozessen auf denselben privaten Dateipfad gesetzt werden.

### Eingebettetes Chatfenster

Im KOR-NEXUS-HUD erscheint die Schaltfläche LILITH. Das Fenster verwendet:

- eine eigene HUD-Sitzung pro Browser-Profil;
- dieselbe Hermes-Gateway-Instanz und dieselbe Lilith-Agentenkonfiguration;
- die gleiche MCP-Werkzeugfreigabe wie andere Hermes-Kanäle;
- eine lokale, authentifizierte HTTP-Bridge zwischen KOR-NEXUS-Backend und Hermes-Plugin.

Der Browser kommuniziert nur mit der bestehenden KOR-NEXUS-API. Er erhält weder den Plugin-Port noch das Zugriffstoken. Chatnachrichten sind auf 12.000 Zeichen begrenzt; maximal acht gleichzeitige HUD-Anfragen werden angenommen. Antworten werden derzeit als vollständige Nachricht übergeben; Streaming-Text und proaktive Ereigniszustellung gehören zu einer späteren Ausbaustufe.

### Betriebsgrenzen der ersten Hybrid-Version

- KOR-NEXUS bleibt ohne Hermes voll funktionsfähig.
- Das MCP-Toolset liest Daten und darf ausschließlich Aufgaben sowie strukturierte Einträge über streng begrenzte KOR-NEXUS-API-Routen anlegen oder bearbeiten. Es kann weder löschen noch Bestände oder Sicherheits-/Backupeinstellungen verändern.
- Der Platform-Adapter leitet Chatnachrichten an Hermes weiter. Er führt selbst keine KOR-NEXUS-Datenbankoperationen aus.
- Die aktuelle Event-Journal-Funktion kann von Lilith abgefragt werden (kor_get_events). Automatische Push-Benachrichtigungen aus KOR-NEXUS an WhatsApp/HUD sind noch nicht aktiviert.
- Kritische KOR-Aktionen bleiben den vorhandenen Bestätigungsmechanismen der Core Engine unterworfen.

### Diagnose

- Hermes Plugin prüfen: hermes plugins list (Plugin muss als aktiviert erscheinen)
- MCP-Verbindung prüfen: hermes mcp test kor_nexus
- KOR-NEXUS-Verbindungsstatus: GET /api/lilith/status
- KOR-NEXUS-Chat: POST /api/lilith/message mit JSON-Feldern session_id und message

Der Installer kopiert das Plugin nach ~/.hermes/plugins/kor-nexus-panel/ und erzeugt Konfigurationsvorlagen, bearbeitet ~/.hermes/config.yaml aber nicht automatisch.
