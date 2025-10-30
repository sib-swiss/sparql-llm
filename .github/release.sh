#!/bin/bash

# Validate version bump type
BUMP_TYPE=$1
if [ -z "$BUMP_TYPE" ] || { [ "$BUMP_TYPE" != "fix" ] && [ "$BUMP_TYPE" != "minor" ] && [ "$BUMP_TYPE" != "major" ]; }; then
    echo "Error: Version bump type is required and must be one of: fix, minor, major"
    echo "Usage: $0 <fix|minor|major>"
    exit 1
fi

uvx hatch version $BUMP_TYPE

VERSION=$(uvx hatch version)

uvx git-cliff -o CHANGELOG.md --tag v$VERSION
git add CHANGELOG.md src/*/__init__.py
git commit -m "Bump to v$VERSION"
git tag -a "v$VERSION" -m "Release v$VERSION"
git push origin "v$VERSION"

rm -rf dist
uv build
uv publish

# If `uv publish` is broken:
# uvx hatch build && uvx hatch publish
