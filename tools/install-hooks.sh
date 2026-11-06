#!/usr/bin/env bash
set -e
root="$(git rev-parse --show-toplevel)"
ln -sf ../../tools/precommit-scan.sh "$root/.git/hooks/pre-commit"
echo "pre-commit scan installed. Put private literals (email, customer ids) in .personal-denylist (gitignored)."
