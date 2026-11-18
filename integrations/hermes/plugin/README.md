# KOR-NEXUS Hermes platform plugin

This plugin adds KOR-NEXUS as a local messaging channel inside the Hermes Gateway.
It uses the supported Hermes community-plugin path (plugin.yaml, adapter.py,
register(ctx)) and does not patch Hermes core files.

## Message flow

1. KOR-NEXUS writes a user's chat message to its local SQLite queue.
2. The plugin polls the authenticated loopback bridge and forwards the message
   into the normal Hermes Gateway message handler.
3. Hermes processes the turn using its normal tools, skills, model/provider and
   existing platform routing.
4. The plugin's send() callback writes the assistant reply into the matching
   KOR-NEXUS conversation.

The KOR-NEXUS chat is an additional Hermes channel. Telegram, WhatsApp, Discord
and other already configured Hermes channels remain configured and operated by
Hermes; this plugin does not replace or modify them. Each platform keeps its
normal Hermes session identity.

## Security model

- The KOR-NEXUS API remains bound to loopback.
- The plugin accepts only loopback HTTP endpoints and rejects redirects.
- Every bridge request carries a private bearer token stored in user
  configuration files with mode 0600.
- KOR-NEXUS compares tokens with constant-time comparison.
- MCP and platform plugin code do not open a LAN listener or write directly to
  the SQLite database.
- Chat messages are bounded to 20,000 characters and bridge batches to 20 rows.

## Setup

Run bash integrations/hermes/setup.sh from the repository or installed
KOR-NEXUS application directory. The script installs the platform plugin into
~/.hermes/plugins/kor-nexus, creates or updates the token in ~/.hermes/.env,
and prints the gateway.platforms.kor_nexus configuration block.

Add the printed block to ~/.hermes/config.yaml, start KOR-NEXUS, then restart
the Hermes Gateway. Setup does not overwrite the rest of the user's Hermes
configuration.

The MCP server is separate and read-only. It exposes KOR-NEXUS status, tasks,
projects, records, resources, system health and cached news to Hermes tools.
See the parent integrations/hermes/README.md.
