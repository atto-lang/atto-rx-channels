#!/usr/bin/env bash
# Exact Git commit + pristine source snapshot preflight. No guest-runtime claim.
set -euo pipefail
export LC_ALL=C

deny() { printf 'CI_SOURCE_HEAD_DENIED: %s\n' "$1" >&2; exit 65; }

expected="${EXPECTED_HEAD:-}"
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || deny 'expected commit must be a lowercase SHA-1'

# An inherited Git control variable could make git report identity for a
# different repository, even with a trustworthy working-directory argument.
while IFS='=' read -r name _; do
  [[ "$name" != GIT_* ]] || deny 'Git control environment is not allowed'
done < <(env)

root="$(pwd -P)"
top="$(/usr/bin/git -C "$root" rev-parse --show-toplevel 2>/dev/null)" || deny 'not a Git checkout'
[[ "$(cd "$top" && pwd -P)" == "$root" ]] || deny 'must run at the checkout root'

actual="$(/usr/bin/git -C "$root" rev-parse --verify 'HEAD^{commit}' 2>/dev/null)" || deny 'missing HEAD commit'
[[ "$actual" == "$expected" ]] || deny 'HEAD does not equal the original event commit'
tree="$(/usr/bin/git -C "$root" rev-parse --verify 'HEAD^{tree}' 2>/dev/null)" || deny 'missing HEAD tree'
[[ "$tree" =~ ^[0-9a-f]{40}$ ]] || deny 'invalid Git tree identity'

/usr/bin/git -C "$root" diff --quiet --exit-code || deny 'dirty working tree'
/usr/bin/git -C "$root" diff --cached --quiet --exit-code || deny 'dirty index'
[[ -z "$(/usr/bin/git -C "$root" ls-files --others --exclude-standard)" ]] || deny 'untracked checkout files'
[[ -z "$(/usr/bin/git -C "$root" ls-files --others --ignored --exclude-standard)" ]] || deny 'ignored shadow files'

printf 'CI_SOURCE_HEAD_VERIFIED commit=%s tree=%s\n' "$actual" "$tree"
