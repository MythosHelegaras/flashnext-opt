#!/usr/bin/env bash
# publish-repo.sh — export a sanitized copy of ~/flashnext-opt and push it to a new public GitHub repo.
# Bash (not fish) because it uses conditionals and heredocs. Run:  bash ~/flashnext-opt/publish-repo.sh
# Your working folder is never modified; everything happens in $DST.
set -euo pipefail

SRC="$HOME/flashnext-opt"
DST="$HOME/flashnext-opt-public"
REPO="flashnext-opt"
DESC="Measurement logs, harness and decisions for tuning Qwen3.8-Flash-Next 125B-A6B on a 16 GB RTX 5070 Ti with llama.cpp"
INCLUDE_CUDA_CORPUS="${INCLUDE_CUDA_CORPUS:-0}"   # 1 = also publish corpus/full128, full256, p32k (contain preprocessed NVIDIA CUDA headers)

command -v gh >/dev/null    || { echo "gh missing: sudo pacman -S github-cli"; exit 1; }
command -v rsync >/dev/null || { echo "rsync missing: sudo pacman -S rsync"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh not logged in: gh auth login"; exit 1; }
[ -e "$DST" ] && { echo "$DST already exists. Remove it first: rm -rf $DST"; exit 1; }

# --- git identity: commits are public forever, so check the email first ---
EMAIL="$(git config --get user.email || true)"
GHUSER="$(gh api user -q .login)"
echo "GitHub account: $GHUSER"
echo "Commit email:   ${EMAIL:-<unset>}"
if [[ "$EMAIL" != *users.noreply.github.com ]]; then
  echo "WARNING: this email will be public in the commit history."
  echo "Your private noreply address is shown at https://github.com/settings/emails"
  read -rp "Continue with this email anyway? [y/N] " a; [[ "$a" == [yY] ]] || exit 1
fi

# --- 1. copy, excluding caches, pid files, binaries, build backups ---
EXCL=(--exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pid' --exclude='venv/'
      --exclude='build-backups/' --exclude='corpus/rejected-v2/')
if [ "$INCLUDE_CUDA_CORPUS" != "1" ]; then
  EXCL+=(--exclude='corpus/full128.txt' --exclude='corpus/full256.txt' --exclude='corpus/p32k.txt')
fi
rsync -a "${EXCL[@]}" "$SRC/" "$DST/"

# --- 2. checksums for the corpus files, so a regenerated corpus can be verified ---
( cd "$SRC/corpus" && sha256sum p4k.txt p32k.txt full128.txt full256.txt session.json cold/*.json ) > "$DST/corpus/SHA256SUMS"

# --- 3. redactions (logged in REDACTIONS.md) ---
# preflight.txt: process list leaked a desktop-app crash-reporter ID and a shell-snapshot path
sed -i -E '/claude-desktop|shell-snapshots/d' "$DST/logs/v4/preflight.txt"

cat > "$DST/REDACTIONS.md" <<'EOF'
# Redactions and omissions

Everything in this repo is the unedited working folder, except:

- `logs/v4/preflight.txt`: two lines of the GPU/process listing removed (an unrelated desktop app's
  process line with a per-install device ID, and an agent's temp-file path). No measurement data was in them.
- Not published: `__pycache__/`, `*.pid`, `build-backups/` (a compiled `llama-server` binary and a
  `CMakeCache.txt` with the machine's hostname), `corpus/rejected-v2/` (corpus rejected during v2).
- `corpus/full128.txt`, `corpus/full256.txt`, `corpus/p32k.txt` are not published unless noted below:
  they are preprocessed compiler output that includes NVIDIA CUDA toolkit headers, which I do not have
  the right to redistribute. `harness.py:build_corpus()` regenerates them from a llama.cpp build tree;
  `corpus/SHA256SUMS` lists the hashes of the files used in every run.
EOF
if [ "$INCLUDE_CUDA_CORPUS" = "1" ]; then
  echo "- (This copy DOES include those three corpus files.)" >> "$DST/REDACTIONS.md"
fi

cat > "$DST/.gitignore" <<'EOF'
__pycache__/
*.pyc
*.pid
venv/
build-backups/
EOF

# --- 4. final leak gate: abort if anything sensitive survived ---
if grep -rIlE --exclude=publish-repo.sh 'shell-snapshots|crashpad|crash-reporter|Zef-Desktop|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20}|hf_[A-Za-z0-9]{20}|sk-[A-Za-z0-9]{20}' "$DST"; then
  echo "ABORT: sensitive pattern found in the files above."; exit 1
fi
BIG="$(find "$DST" -type f -size +50M)"; [ -z "$BIG" ] || { echo "ABORT: file >50MB: $BIG"; exit 1; }
if find "$DST" -type f -exec file {} + | grep -q 'ELF'; then echo "ABORT: binary found"; exit 1; fi

# --- 5. git + GitHub ---
cd "$DST"
git init -q -b main
git add -A
git commit -q -m "flashnext-opt: harness, raw logs, results and decisions (runs v1-v4, 2026-09-28 to 2026-10-06)"
gh repo create "$REPO" --public --source=. --remote=origin --push --description "$DESC"

echo
echo "Published: $(gh repo view "$GHUSER/$REPO" --json url -q .url)"
echo "Files: $(git ls-files | wc -l)   Size: $(du -sh --exclude=.git . | cut -f1)"
