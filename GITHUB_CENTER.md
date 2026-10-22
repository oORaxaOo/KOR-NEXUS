# KOR-NEXUS GitHub Development Center

The GitHub Development Center is a local UI backed by the KOR-NEXUS loopback server. It can list repositories visible to the authenticated account, inspect branches/open issues/open pull requests/recent commits/Actions runs, create issues and working branches, open pull requests, and dispatch workflows configured with `workflow_dispatch`.

## Connect on Arch Linux

1. Install GitHub CLI (`gh`) if needed: `sudo pacman -S github-cli`.
2. Authenticate in a terminal as the same Linux user who launches KOR-NEXUS:

   ```sh
   gh auth login
   gh auth status
   ```

3. Restart KOR-NEXUS, then click **GITHUB** in the top bar.
4. Click **AKTUALISIEREN** to load repositories accessible to the authenticated account.

The application obtains the token from `gh auth token` at runtime. Alternatively, launch the application with `KOR_NEXUS_GITHUB_TOKEN` set in its environment. Prefer GitHub CLI's credential storage. Never paste tokens into the UI, source files, issues, logs, or screenshots. Tokens are not saved to the Nexus SQLite database and are never sent to the browser.

## Capabilities and guardrails

- Repository selection spans repositories the GitHub account is authorized to access (the GitHub API returns a paginated first batch of up to 100 repositories).
- View branch names, open issues, pull requests, recent commits and recent Actions runs.
- Create issues, create a named working branch from a selected existing branch, open pull requests, and manually dispatch a workflow.
- Every write action requires a confirmation prompt.
- The integration does not merge pull requests, push source files, delete branches, or change repository settings.
- Workflow dispatch only works for workflows that declare `workflow_dispatch` and where the token has sufficient permissions.
- GitHub permissions still apply. Prefer a fine-grained token with only the repository access and scopes needed if using an environment variable.

## Troubleshooting

- **Not connected:** run `gh auth login` and then `gh auth status` as the same Linux user running Nexus.
- **403:** check token scopes, repository access, organization SSO approval and API rate limits.
- **404:** the repository may not be accessible to the authenticated account, or the endpoint may be unavailable for that repository.
- **Workflow dispatch rejected:** confirm the workflow file exists under `.github/workflows/`, includes `on: workflow_dispatch`, and the account can run Actions.

GitHub access requires internet connectivity. The rest of KOR-NEXUS remains local-first when offline.
