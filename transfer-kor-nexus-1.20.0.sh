#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="https://github.com/oORaxaOo/KOR-NEXUS.git"
BRANCH="transfer/kor-nexus-1.20.0"
EXPECTED_BASE="cc5e9d005462e1214e59e02a4017ef621c131b58"
EXPECTED_ZIP_SHA="535499d9ff851dec75afaf8f61a51567c81656459888306c9a12346ee04e6188"
EXPECTED_GEO_SHA="8cde92ef2b36f541578c34947081fdb387677f8371134c6b49c11e9fc9e15f6d"
ZIP_PATH="${1:-}"

if [[ -z "$ZIP_PATH" || ! -f "$ZIP_PATH" ]]; then
  echo "Usage: $0 /path/to/KOR_NEXUS_1.20.0_transfer_candidate.zip" >&2
  exit 2
fi
command -v git >/dev/null || { echo "git is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 2; }
command -v sha256sum >/dev/null || { echo "sha256sum is required" >&2; exit 2; }
command -v unzip >/dev/null || { echo "unzip is required" >&2; exit 2; }

actual_zip_sha="$(sha256sum "$ZIP_PATH" | awk '{print $1}')"
if [[ "$actual_zip_sha" != "$EXPECTED_ZIP_SHA" ]]; then
  echo "ERROR: ZIP checksum mismatch." >&2
  echo "Expected: $EXPECTED_ZIP_SHA" >&2
  echo "Actual:   $actual_zip_sha" >&2
  exit 3
fi

TMP_ROOT="$(mktemp -d -t kor-nexus-transfer.XXXXXX)"
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

# Clone only the dedicated transfer branch; never check out or push main.
git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$TMP_ROOT/repo"
cd "$TMP_ROOT/repo"

branch_head="$(git rev-parse HEAD)"
if [[ "$branch_head" != "$EXPECTED_BASE" ]]; then
  echo "ERROR: transfer branch moved since this helper was prepared; refusing to continue." >&2
  echo "Expected base: $EXPECTED_BASE" >&2
  echo "Current head:  $branch_head" >&2
  exit 4
fi
remote_main="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
if [[ "$remote_main" != "$EXPECTED_BASE" ]]; then
  echo "ERROR: main has moved since the transfer candidate was prepared; refusing stale transfer." >&2
  echo "Expected main: $EXPECTED_BASE" >&2
  echo "Current main:  ${remote_main:-NOT FOUND}" >&2
  exit 5
fi

mkdir "$TMP_ROOT/unpack"
unzip -q "$ZIP_PATH" -d "$TMP_ROOT/unpack"
SOURCE="$TMP_ROOT/unpack/transfer-candidate-1.20.0/kor-nexus"
if [[ ! -d "$SOURCE" || ! -f "$SOURCE/README.md" || ! -f "$SOURCE/web/geodata/world.geojson" || ! -f "$SOURCE/.github/workflows/release.yml" ]]; then
  echo "ERROR: expected project structure, offline geodata, or workflow is missing." >&2
  exit 6
fi

actual_geo_sha="$(sha256sum "$SOURCE/web/geodata/world.geojson" | awk '{print $1}')"
if [[ "$actual_geo_sha" != "$EXPECTED_GEO_SHA" ]]; then
  echo "ERROR: offline GeoJSON checksum mismatch." >&2
  exit 7
fi

# Overlay the 36 reviewed project files. Existing remote archive files are preserved;
# README.md is intentionally replaced by the reviewed project README.
cp -a "$SOURCE/." "$TMP_ROOT/repo/"

cd "$TMP_ROOT/repo"
python3 -m unittest -v core.test_server
bash scripts/ci.sh quick

# Stage only project files listed by the checked archive; do not remove the existing archive files.
python3 - "$SOURCE" "$TMP_ROOT/repo" <<'PY'
import os, subprocess, sys
src, repo = sys.argv[1:]
for root, dirs, files in os.walk(src):
    dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".pytest_cache"}]
    for name in files:
        path = os.path.relpath(os.path.join(root, name), src)
        subprocess.run(["git", "add", "--", path], cwd=repo, check=True)
PY

if git diff --cached --quiet; then
  echo "ERROR: no staged changes; no commit created." >&2
  exit 8
fi

echo
echo "=== Proposed single commit ==="
git diff --cached --stat
echo
echo "=== Staged paths ==="
git diff --cached --name-status
printf '\n'
read -r -p "Type TRANSFER-1.20.0 to create one commit and push only $BRANCH: " confirmation
if [[ "$confirmation" != "TRANSFER-1.20.0" ]]; then
  echo "Cancelled before commit/push. No remote changes were made."
  exit 0
fi

git config user.name >/dev/null 2>&1 || git config user.name "KOR-NEXUS Transfer"
git config user.email >/dev/null 2>&1 || git config user.email "kor-nexus-transfer@users.noreply.github.com"
git commit -m "Transfer KOR-NEXUS 1.20.0 reviewed project"
new_commit="$(git rev-parse HEAD)"
# Lease check: only update the transfer branch if it still points at the known base.
git push --force-with-lease="refs/heads/$BRANCH:$EXPECTED_BASE" origin "HEAD:refs/heads/$BRANCH"
echo
echo "TRANSFER_PUSHED=1"
echo "COMMIT=$new_commit"
echo "BRANCH=$BRANCH"
echo "MAIN_WAS_NOT_CHECKED_OUT_OR_PUSHED=1"
echo "Verify the new commit and file tree on GitHub before merging anything."
