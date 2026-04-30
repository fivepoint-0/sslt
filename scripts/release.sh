#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <version>"
  echo "Example: $0 0.1.0"
}

if [[ "${1:-}" == "" ]]; then
  usage
  exit 1
fi

VERSION="$1"
TAG="v$VERSION"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$ ]]; then
  echo "Invalid version: $VERSION"
  echo "Use semantic version format, e.g. 1.2.3 or 1.2.3-rc1"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository."
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes before releasing."
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists locally."
  exit 1
fi

if git ls-remote --tags origin "refs/tags/$TAG" | rg -q "$TAG"; then
  echo "Tag $TAG already exists on origin."
  exit 1
fi

echo "Creating tag: $TAG"
git tag "$TAG"

echo "Pushing tag to origin: $TAG"
git push origin "$TAG"

echo "Release started. Track progress in the GitHub Actions 'Release' workflow."
