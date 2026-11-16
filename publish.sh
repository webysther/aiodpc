#!/usr/bin/env bash
# Publish a release of aiodpc: a GitHub release whose notes are the version's
# section of CHANGELOG.md. Publishing it runs .github/workflows/release.yml,
# which tests, builds and uploads the package to PyPI.
#
# Usage: ./publish.sh VERSION [--dry-run]
#        ./publish.sh paper [--dry-run]
#
#   ./publish.sh 0.2.0            publish v0.2.0
#   ./publish.sh 0.1.0            v0.1.0 exists: only update its notes
#   ./publish.sh 0.2.0 --dry-run  show the notes and run the checks, change nothing
#   ./publish.sh paper            download the PDFs of the paper, as built by
#                                 .github/workflows/paper.yml from the pushed
#                                 commits, to paper-rN.pdf and
#                                 paper-rN-title-page.pdf (ignored by git)
#
# Before publishing, __version__ in src/aiodpc/__init__.py must be VERSION and
# CHANGELOG.md must have a "## [VERSION]" section; "Unreleased" in its title is
# replaced by today's date and committed.
set -euo pipefail

readonly CHANGELOG=CHANGELOG.md
readonly VERSION_FILE=src/aiodpc/__init__.py
readonly BRANCH=main
readonly PAPER_CHANGELOG=docs/paper/CHANGELOG.md
readonly PAPER_WORKFLOW=paper.yml
# What the paper is built from: a change here is a new revision of the paper.
readonly PAPER_FILES=(docs/paper docs/study/figures .github/workflows/paper.yml)

usage() {
  awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"
  exit "${1:-0}"
}
die() {
  echo "error: $*" >&2
  exit 1
}
step() { printf '\n==> %s\n' "$*"; }

# In a dry run, report what would stop the release and go on.
problems=0
check() {
  if $dry_run; then
    echo "[dry-run] would stop: $*" >&2
    problems=$((problems + 1))
  else
    die "$*"
  fi
}
# In a dry run, print the commands that change something instead of running them.
run() {
  if $dry_run; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

version=""
dry_run=false
for arg in "$@"; do
  case $arg in
    -n | --dry-run) dry_run=true ;;
    -h | --help) usage ;;
    -*)
      echo "Unknown option: $arg" >&2
      usage 2
      ;;
    *)
      [[ -z $version ]] || usage 2
      version=${arg#v}
      ;;
  esac
done
[[ -n $version ]] || usage 2

# Download the PDFs of the paper that GitHub Actions built from the last
# pushed commit that changed it; build them first when no run did.
publish_paper() {
  local revision commit run_id downloads
  revision=$(sed -n 's/^## r\([0-9][0-9]*\) .*/\1/p' "$PAPER_CHANGELOG" | head -n 1)
  [[ -n $revision ]] || die "$PAPER_CHANGELOG has no revision: add a '## r1 - DATE' section"

  step "Checking the repository"
  [[ -z $(git status --porcelain -- "${PAPER_FILES[@]}") ]] ||
    check "uncommitted changes to the paper: commit them as a new revision first"
  git fetch --quiet origin "$BRANCH"
  git merge-base --is-ancestor HEAD "origin/$BRANCH" ||
    check "HEAD is not on origin/$BRANCH: push first, GitHub Actions builds the PDFs"
  commit=$(git log -1 --format=%H -- "${PAPER_FILES[@]}")
  echo "Revision r$revision, last changed by $(git log -1 --format='%h %s' "$commit")"

  if ! gh workflow view "$PAPER_WORKFLOW" >/dev/null 2>&1; then
    check "the Paper workflow is not on GitHub: push .github/workflows/$PAPER_WORKFLOW"
    echo >&2
    die "dry run: $problems problem(s) would stop the download"
  fi
  run_id=$(gh run list --workflow "$PAPER_WORKFLOW" --commit "$commit" \
    --status success --limit 1 --json databaseId --jq '.[0].databaseId // empty')
  if [[ -z $run_id ]]; then
    step "No build of $(git rev-parse --short "$commit") yet: building origin/$BRANCH"
    if $dry_run; then
      echo "[dry-run] gh workflow run $PAPER_WORKFLOW --ref $BRANCH, then wait for it"
    else
      local head
      head=$(git rev-parse "origin/$BRANCH")
      gh workflow run "$PAPER_WORKFLOW" --ref "$BRANCH"
      for _ in {1..20}; do
        run_id=$(gh run list --workflow "$PAPER_WORKFLOW" --commit "$head" \
          --event workflow_dispatch --limit 1 --json databaseId \
          --jq '.[0].databaseId // empty')
        [[ -n $run_id ]] && break
        sleep 3
      done
      [[ -n $run_id ]] || die "the Paper workflow did not start: check GitHub Actions"
      gh run watch "$run_id" --exit-status
    fi
  fi

  if ((problems)); then
    echo >&2
    die "dry run: $problems problem(s) would stop the download"
  fi
  step "Downloading the PDFs of revision r$revision"
  if $dry_run; then
    echo "[dry-run] gh run download ${run_id:-RUN} --name paper:" \
      "paper-r$revision.pdf, paper-r$revision-title-page.pdf"
    echo
    echo "Dry run: nothing was changed."
    return
  fi
  downloads=$(mktemp -d)
  gh run download "$run_id" --name paper --dir "$downloads"
  mv "$downloads/manuscript.pdf" "paper-r$revision.pdf"
  mv "$downloads/title-page.pdf" "paper-r$revision-title-page.pdf"
  rm -rf "$downloads"
  echo "Done: paper-r$revision.pdf and paper-r$revision-title-page.pdf"
}

if [[ $version == paper ]]; then
  cd "$(dirname "$0")"
  command -v gh >/dev/null || die "the GitHub CLI (gh) is required"
  gh auth status >/dev/null 2>&1 || die "gh is not logged in: run 'gh auth login'"
  publish_paper
  exit 0
fi

[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  die "invalid version '$version', expected X.Y.Z (e.g. 0.2.0)"
readonly tag="v$version"
readonly heading="## [$version]"

cd "$(dirname "$0")"
command -v gh >/dev/null || die "the GitHub CLI (gh) is required"
gh auth status >/dev/null 2>&1 || die "gh is not logged in: run 'gh auth login'"

# The section of the version in the changelog, without its heading.
changelog_notes() {
  awk -v heading="$heading" '
    index($0, heading) == 1 { found = 1; next }
    /^## \[/ || /^\[[0-9]/ { found = 0 }
    found
  ' "$CHANGELOG" | sed '/./,$!d'
}

notes_file=$(mktemp)
trap 'rm -f "$notes_file"' EXIT
changelog_notes >"$notes_file"
[[ -n $(tr -d '[:space:]' <"$notes_file") ]] ||
  die "$CHANGELOG has no notes for $version: add a '$heading - Unreleased' section"

step "Notes of $tag"
cat "$notes_file"

# An existing release only gets its notes updated.
if gh release view "$tag" >/dev/null 2>&1; then
  step "$tag is already published: updating its notes"
  run gh release edit "$tag" --notes-file "$notes_file"
  $dry_run || echo "Done: $(gh release view "$tag" --json url --jq .url)"
  exit 0
fi

step "Checking the repository"
[[ $(git branch --show-current) == "$BRANCH" ]] ||
  check "not on the $BRANCH branch"
[[ -z $(git status --porcelain) ]] ||
  check "uncommitted changes: commit or stash them first"
git fetch --quiet origin "$BRANCH"
git merge-base --is-ancestor "origin/$BRANCH" HEAD ||
  check "$BRANCH is behind origin/$BRANCH: pull first"
code_version=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$VERSION_FILE")
[[ $code_version == "$version" ]] ||
  check "$VERSION_FILE has version $code_version, not $version"
git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null &&
  check "the tag $tag already exists on GitHub"

step "Running the checks"
bin=""
[[ -x .venv/bin/python ]] && bin=.venv/bin/
"${bin}ruff" format --check .
"${bin}ruff" check .
"${bin}mypy"
"${bin}pytest" -q

if ((problems)); then
  echo >&2
  die "dry run: $problems problem(s) would stop the release"
fi

if grep -qxF "$heading - Unreleased" "$CHANGELOG"; then
  step "Dating the $version section of $CHANGELOG"
  if $dry_run; then
    echo "[dry-run] '$heading - Unreleased' -> '$heading - $(date +%F)', commit"
  else
    dated=$(mktemp)
    awk -v from="$heading - Unreleased" -v to="$heading - $(date +%F)" \
      '$0 == from { $0 = to } { print }' "$CHANGELOG" >"$dated"
    mv "$dated" "$CHANGELOG"
    git commit --quiet -m "Release $version" -- "$CHANGELOG"
  fi
fi

step "Publishing $tag"
run git push --quiet origin "$BRANCH"
run gh release create "$tag" --title "$tag" --notes-file "$notes_file" \
  --target "$(git rev-parse HEAD)"
if $dry_run; then
  echo
  echo "Dry run: nothing was changed."
  exit 0
fi

step "Waiting for the PyPI publication"
run_id=""
for _ in {1..20}; do
  run_id=$(gh run list --workflow release.yml --branch "$tag" --limit 1 \
    --json databaseId --jq '.[0].databaseId // empty')
  [[ -n $run_id ]] && break
  sleep 3
done
[[ -n $run_id ]] || die "the Release workflow did not start: check GitHub Actions"
gh run watch "$run_id" --exit-status
echo
echo "Published: https://pypi.org/project/aiodpc/$version/"
