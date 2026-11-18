# KOR-NEXUS Hermes platform plugin

This plugin exposes the KOR-NEXUS local HUD as a native Hermes Gateway platform.

- Platform name: kor_nexus
- Listener: 127.0.0.1 only
- Transport: standard-library HTTP server on a local port
- Authentication: random 384-bit token, written owner-only to the XDG config directory at kor-nexus/hermes-bridge.json
- Message routing: BasePlatformAdapter.handle_message() and the active GatewayRunner; no secondary agent or copied memory
- Reply handling: correlated by request ID and session chat ID; final notify sends complete the pending HTTP request
- The adapter never opens the KOR-NEXUS SQLite database

## Enable in Hermes

Copy this plugin into ~/.hermes/plugins/kor-nexus-panel/, then add the following under the existing gateway.platforms section in ~/.hermes/config.yaml:

    kor_nexus:
      enabled: true
      extra:
        port: 9876

Use port 0 to let the operating system allocate a port; the actual port is published in the private bridge file. The recommended default is 9876.

Restart the Hermes gateway. When connected, KOR-NEXUS reads the private bridge file and reports the agent as available. The KOR-NEXUS backend proxies chat requests to the adapter, and the browser never receives the bridge token.

The optional plugin is not needed for KOR-NEXUS itself to run. If Hermes is offline, the rest of KOR-NEXUS remains fully functional.
