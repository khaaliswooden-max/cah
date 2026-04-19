#!/usr/bin/env bash
# Add every public repo from github.com/alexwg and github.com/karpathy
# as a shallow git submodule under experiments/<owner>/<repo>.
#
# Idempotent: if a submodule path already exists (either in .gitmodules or
# on disk), the entry is skipped. Individual clone failures do not abort
# the batch; a summary is printed at the end.

set -u

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

mkdir -p experiments/alexwg experiments/karpathy

ALEXWG_REPOS=(
  cpython
)

KARPATHY_REPOS=(
  nanochat
  karpathy.github.io
  autoresearch
  jobs
  rustbpe
  cpython
  hn-time-capsule
  llm-council
  reader3
  nanoGPT
  rendergit
  llm.c
  nn-zero-to-hero
  minGPT
  build-nanogpt
  micrograd
  llama2.c
  LLM101n
  minbpe
  makemore
  calorie
  lecun1989-repro
  ng-video-lecture
  char-rnn
  notpygamejs
  researchpooler
  karpathy
  arxiv-sanity-lite
  randomfun
  convnetjs
  transformers
  arxiv-sanity-preserver
  deep-vector-quantization
  optim
  cryptos
  neuraltalk
  ulogme
  covid-sanity
  gitstats
  sqlitedict
  pytorch-normalizing-flows
  tsnejs
  reinforcejs
  pytorch-made
  examples
  svmjs
  find-birds
  neuraltalk2
  tf-agent
  nipspreview
  paper-notes
  recurrentjs
  EigenLibSVM
  nn
  simple-amt
  scholaroctopus
  Random-Forest-Matlab
  researchlei
  twoolpy
  forestjs
  MatlabWrapper
  lifejs
  scriptsbots
)

declare -a FAILED=()
added=0
skipped=0

add_submodule() {
  local owner="$1"
  local repo="$2"
  local path="experiments/${owner}/${repo}"
  local url="https://github.com/${owner}/${repo}.git"

  if [ -e "$path/.git" ] || grep -q "path = ${path}\$" .gitmodules 2>/dev/null; then
    echo "SKIP  ${owner}/${repo} (already present)"
    skipped=$((skipped + 1))
    return 0
  fi

  echo "ADD   ${owner}/${repo}"
  if git submodule add --depth=1 "$url" "$path" >/dev/null 2>&1; then
    added=$((added + 1))
  else
    echo "FAIL  ${owner}/${repo}"
    FAILED+=("${owner}/${repo}")
    rm -rf "$path" ".git/modules/${path}" 2>/dev/null || true
  fi
}

for repo in "${ALEXWG_REPOS[@]}"; do
  add_submodule alexwg "$repo"
done

for repo in "${KARPATHY_REPOS[@]}"; do
  add_submodule karpathy "$repo"
done

total=$((${#ALEXWG_REPOS[@]} + ${#KARPATHY_REPOS[@]}))
echo
echo "-------------------------------------------"
echo "Submodules added:   ${added}"
echo "Submodules skipped: ${skipped}"
echo "Submodules failed:  ${#FAILED[@]}"
echo "Total requested:    ${total}"
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo
  echo "Failed repos:"
  for r in "${FAILED[@]}"; do echo "  - $r"; done
fi
