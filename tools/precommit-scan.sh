#!/usr/bin/env bash
# Blocks commits that contain secrets or personal data.
# Generic patterns are built in. Add your own literals (email, customer ids, paths),
# one per line, to the UNTRACKED file .personal-denylist (gitignored).
set -u
root="$(git rev-parse --show-toplevel)"
fail=0

# 1. forbidden file names
while IFS= read -r f; do
  case "$f" in
    *client_secret*.json|*adc.json|*google-ads.yaml|*mcp-google-ads.yaml|*.pem|*.env|.env*|*credentials*.json)
      echo "BLOCKED file: $f"; fail=1;;
  esac
done < <(git diff --cached --name-only --diff-filter=ACM)

# 2. generic secret / personal patterns in added lines
patterns='AIza[0-9A-Za-z_-]{30,}|ya29\.[0-9A-Za-z_-]+|1//0[0-9A-Za-z_-]{20,}|GOCSPX-[0-9A-Za-z_-]+|[0-9]+-[0-9a-z]{20,}\.apps\.googleusercontent\.com|"refresh_token"|"client_secret"|-----BEGIN [A-Z ]*PRIVATE KEY-----|/Users/[A-Za-z0-9._-]+/|[A-Za-z0-9._%+-]+@(gmail|pm|proton|protonmail|outlook|hotmail|icloud|yahoo)\.[a-z]+'
added="$(git diff --cached -U0 --diff-filter=ACM -- . ':!tools/precommit-scan.sh' | grep -E '^\+[^+]' || true)"
if echo "$added" | grep -nE "$patterns" >/dev/null; then
  echo "BLOCKED: secret/personal pattern in staged changes:"
  echo "$added" | grep -nE "$patterns" | sed 's/^/  /' | cut -c1-160
  fail=1
fi

# 3. user-specific literals (untracked denylist)
if [ -f "$root/.personal-denylist" ]; then
  while IFS= read -r lit; do
    [ -z "$lit" ] && continue
    case "$lit" in \#*) continue;; esac
    if echo "$added" | grep -qiF -- "$lit"; then
      echo "BLOCKED: denylisted literal staged: $lit"; fail=1
    fi
  done < "$root/.personal-denylist"
fi

# 4. commit identity must not be a personal address
email="$(git config user.email)"
case "$email" in
  *@gmail.*|*@pm.me|*@proton*|*@outlook.*|*@hotmail.*|*@icloud.*|*@yahoo.*)
    echo "BLOCKED: git user.email '$email' looks personal. Use a noreply address (git config user.email ...)"; fail=1;;
esac
exit $fail
