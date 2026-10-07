#!/usr/bin/env bash
# sync-repo.sh — rebuild the sanitized export of ~/flashnext-opt and push the changes to the
# existing GitHub repo. Same exclusions, redactions and leak checks as publish-repo.sh.
# Bash (not fish) because it uses conditionals and heredocs. Run:  bash ~/flashnext-opt/sync-repo.sh
set -euo pipefail

SRC="$HOME/flashnext-opt"
REPO_DIR="$HOME/flashnext-opt-public"
INCLUDE_CUDA_CORPUS="${INCLUDE_CUDA_CORPUS:-0}"
MSG="${1:-Add MIT (code) and CC BY 4.0 (data) licenses; README: repetition notes, missing-artifact disclosure}"

[ -d "$REPO_DIR/.git" ] || { echo "$REPO_DIR is not a git repo"; exit 1; }
command -v gh >/dev/null && gh auth status >/dev/null 2>&1 || { echo "gh not ready: gh auth login"; exit 1; }
for f in LICENSE LICENSE-DATA README.md; do [ -f "$SRC/$f" ] || { echo "missing $SRC/$f"; exit 1; }; done

# --- 0. bring the local clone up to date; refuse if it has uncommitted edits ---
cd "$REPO_DIR"
[ -z "$(git status --porcelain)" ] || { echo "Uncommitted changes in $REPO_DIR — commit or discard them first."; git status --short; exit 1; }
git pull --ff-only -q

# --- 1. fresh export into a temp dir ---
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
DST="$TMP/export"
EXCL=(--exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pid' --exclude='venv/'
      --exclude='build-backups/' --exclude='corpus/rejected-v2/')
if [ "$INCLUDE_CUDA_CORPUS" != "1" ]; then
  EXCL+=(--exclude='corpus/full128.txt' --exclude='corpus/full256.txt' --exclude='corpus/p32k.txt')
fi
rsync -a "${EXCL[@]}" "$SRC/" "$DST/"

HOLDER="${COPYRIGHT_HOLDER:-$(gh api user -q '.name // .login')}"
python3 -c 'import sys; p=sys.argv[1]; t=open(p).read(); open(p,"w").write(t.replace("__COPYRIGHT_HOLDER__", sys.argv[2]))' "$DST/LICENSE" "$HOLDER"
echo "MIT copyright holder: $HOLDER"

( cd "$SRC/corpus" && sha256sum p4k.txt p32k.txt full128.txt full256.txt session.json cold/*.json ) > "$DST/corpus/SHA256SUMS"
sed -i -E '/claude-desktop|shell-snapshots/d' "$DST/logs/v4/preflight.txt"

# REDACTIONS.md and .gitignore are generated, not kept in $SRC: carry the published copies over
cp "$REPO_DIR/REDACTIONS.md" "$DST/REDACTIONS.md"
cp "$REPO_DIR/.gitignore" "$DST/.gitignore" 2>/dev/null || printf '__pycache__/\n*.pyc\n*.pid\nvenv/\nbuild-backups/\n' > "$DST/.gitignore"

# --- 2. leak gates (same as publish-repo.sh) ---
if grep -rIlE --exclude=publish-repo.sh --exclude=sync-repo.sh 'shell-snapshots|crashpad|crash-reporter|Zef-Desktop|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20}|hf_[A-Za-z0-9]{20}|sk-[A-Za-z0-9]{20}' "$DST"; then
  echo "ABORT: sensitive pattern found in the files above."; exit 1
fi
grep -q '__COPYRIGHT_HOLDER__' "$DST/LICENSE" && { echo "ABORT: LICENSE holder not filled"; exit 1; }
BIG="$(find "$DST" -type f -size +50M)"; [ -z "$BIG" ] || { echo "ABORT: file >50MB: $BIG"; exit 1; }
if find "$DST" -type f -exec file {} + | grep -q 'ELF'; then echo "ABORT: binary found"; exit 1; fi

# --- 3. mirror into the repo, show what changes, confirm, push ---
rsync -a --delete --exclude='.git/' "$DST/" "$REPO_DIR/"
git add -A
if git diff --cached --quiet; then echo "Nothing changed. Repo already up to date."; exit 0; fi
echo; git diff --cached --stat; echo
read -rp "Commit and push these changes? [y/N] " a
[[ "$a" == [yY] ]] || { git reset -q --hard HEAD; echo "Aborted; local clone reset to the last pushed commit."; exit 1; }
git commit -q -m "$MSG"
git push -q
echo "Pushed: $(gh repo view --json url -q .url)"
