#!/usr/bin/env bash
# publish-repo.sh — export a sanitized copy of ~/flashnext-opt and publish it as a NEW public repo
# with a fresh, single-commit history under a neutral identity.
# Bash (not fish) because it uses conditionals and heredocs.
#
# Required (nothing is taken from your global git or GitHub profile):
#   OWNER            GitHub account or organization that will own the repo
#   COPYRIGHT_HOLDER name written into LICENSE
#   GIT_NAME         commit author name
#   GIT_EMAIL        commit author email (it links commits to whichever account owns it)
# Run, e.g.:  env OWNER=... COPYRIGHT_HOLDER=... GIT_NAME=... GIT_EMAIL=... bash ~/flashnext-opt/publish-repo.sh
#
# An existing ~/flashnext-opt-public is moved aside, never deleted. The old GitHub repo is not touched.
set -euo pipefail

SRC="$HOME/flashnext-opt"
DST="$HOME/flashnext-opt-public"
REPO="flashnext-opt"
DESC="Measurement logs, harness and decisions for tuning Qwen3.8-Flash-Next 125B-A6B on a 16 GB RTX 5070 Ti with llama.cpp"
INCLUDE_CUDA_CORPUS="${INCLUDE_CUDA_CORPUS:-0}"   # 1 = also publish corpus/full128, full256, p32k (contain preprocessed NVIDIA CUDA headers)
: "${OWNER:?set OWNER}" "${COPYRIGHT_HOLDER:?set COPYRIGHT_HOLDER}" "${GIT_NAME:?set GIT_NAME}" "${GIT_EMAIL:?set GIT_EMAIL}"

command -v gh >/dev/null    || { echo "gh missing: sudo pacman -S github-cli"; exit 1; }
command -v rsync >/dev/null || { echo "rsync missing: sudo pacman -S rsync"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh not logged in: gh auth login"; exit 1; }

# --- 0. identity gate: every name that becomes public, checked against the private terms ---
TERMS_FILE="${PRIVATE_TERMS_FILE:-$HOME/.config/flashnext-opt/private-terms}"
[ -s "$TERMS_FILE" ] || { echo "ABORT: private-terms file missing or empty: $TERMS_FILE"; exit 1; }
GHUSER="$(gh api user -q .login)"
for label in "GitHub login (shown as the actor on every push and in GitHub's public event feed)=$GHUSER" \
             "OWNER=$OWNER" "COPYRIGHT_HOLDER=$COPYRIGHT_HOLDER" "GIT_NAME=$GIT_NAME" "GIT_EMAIL=$GIT_EMAIL"; do
  if printf '%s\n' "${label#*=}" | grep -qiE -f "$TERMS_FILE"; then
    echo "ABORT: ${label%%=*} matches a private term."; exit 1
  fi
done
echo "Publishing as: $OWNER/$REPO   pushed by: $GHUSER   author: $GIT_NAME <$GIT_EMAIL>   LICENSE: $COPYRIGHT_HOLDER"
read -rp "Continue? [y/N] " a; [[ "$a" == [yY] ]] || exit 1

if [ -e "$DST" ]; then
  OLD="$DST.old-$(date +%Y%m%d-%H%M%S)"; mv "$DST" "$OLD"; echo "Moved the previous local clone to $OLD"
fi

# --- 1. copy, excluding caches, pid files, binaries, build backups ---
EXCL=(--exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pid' --exclude='venv/'
      --exclude='build-backups/' --exclude='corpus/rejected-v2/' --exclude='april/probe/*/bin/' --exclude='april/probe/*/obj/')
if [ "$INCLUDE_CUDA_CORPUS" != "1" ]; then
  EXCL+=(--exclude='corpus/full128.txt' --exclude='corpus/full256.txt' --exclude='corpus/p32k.txt')
fi
rsync -a "${EXCL[@]}" "$SRC/" "$DST/"

# --- 1b. licenses ---
[ -f "$DST/LICENSE" ] && [ -f "$DST/LICENSE-DATA" ] || { echo "LICENSE or LICENSE-DATA missing in $SRC"; exit 1; }
python3 -c 'import sys; p=sys.argv[1]; t=open(p).read(); open(p,"w").write(t.replace("__COPYRIGHT_HOLDER__", sys.argv[2]))' "$DST/LICENSE" "$COPYRIGHT_HOLDER"

# --- 2. checksums for the corpus files, so a regenerated corpus can be verified ---
( cd "$SRC/corpus" && sha256sum p4k.txt p32k.txt full128.txt full256.txt session.json cold/*.json | LC_ALL=C sort -k2 ) > "$DST/corpus/SHA256SUMS"

# --- 3. redactions (logged in REDACTIONS.md) ---
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
- `april/`: see `april/README.md` for what was changed or left out there.
EOF
if [ "$INCLUDE_CUDA_CORPUS" = "1" ]; then
  echo "- (This copy DOES include those three corpus files.)" >> "$DST/REDACTIONS.md"
fi

printf '__pycache__/\n*.pyc\n*.pid\nvenv/\nbuild-backups/\nbin/\nobj/\n' > "$DST/.gitignore"

# --- 4. content leak gates ---
if grep -rIlE --exclude=publish-repo.sh --exclude=sync-repo.sh 'shell-snapshots|crashpad|crash-reporter|Zef-Desktop|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20}|hf_[A-Za-z0-9]{20}|sk-[A-Za-z0-9]{20}' "$DST"; then
  echo "ABORT: sensitive pattern found in the files above."; exit 1
fi
if grep -rIliE -f "$TERMS_FILE" "$DST"; then echo "ABORT: a private term is in the files above."; exit 1; fi
grep -q '__COPYRIGHT_HOLDER__' "$DST/LICENSE" && { echo "ABORT: LICENSE holder not filled"; exit 1; }
BIG="$(find "$DST" -type f -size +50M)"; [ -z "$BIG" ] || { echo "ABORT: file >50MB: $BIG"; exit 1; }
if find "$DST" -type f -exec file {} + | grep -q 'ELF'; then echo "ABORT: binary found"; exit 1; fi

# --- 5. fresh git history with a repo-local identity (sync-repo.sh reuses it) ---
cd "$DST"
git init -q -b main
git config user.name "$GIT_NAME"
git config user.email "$GIT_EMAIL"
git add -A
git commit -q -m "flashnext-opt: harness, raw logs, results and decisions (runs v1-v4, 2026-09-28 to 2026-10-06)"
gh repo create "$OWNER/$REPO" --public --source=. --remote=origin --push --description "$DESC"

echo
echo "Published: $(gh repo view "$OWNER/$REPO" --json url -q .url)"
echo "Files: $(git ls-files | wc -l)   Size: $(du -sh --exclude=.git . | cut -f1)"
echo "The old repo still exists. Delete it yourself only when ready (irreversible): gh repo delete <old-owner>/$REPO"
