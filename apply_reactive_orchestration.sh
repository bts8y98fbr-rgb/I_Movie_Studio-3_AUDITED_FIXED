#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(pwd)"
BUNDLE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Reactive Prompt Orchestration: SAFE ONE-SHOT INSTALL ==="
echo "Project: $PROJECT_ROOT"
echo

if [ ! -d "$PROJECT_ROOT/.git" ]; then
  echo "ERROR: run this script from the Git project root."
  exit 1
fi
if [ ! -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
  echo "ERROR: .venv not found in project root."
  exit 1
fi

echo "=== GIT STATE ==="
git status --short --branch
BRANCH="$(git branch --show-current)"
if [ "$BRANCH" != "main" ]; then
  echo "ERROR: expected branch main, got: $BRANCH"
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is not clean. Nothing changed."
  exit 1
fi

echo
echo "=== SYNC WITH ORIGIN ==="
git fetch origin
git diff --quiet HEAD origin/main || {
  echo "ERROR: local main differs from origin/main. Nothing changed."
  exit 1
}

echo
echo "=== CREATE WORK BRANCH ==="
git switch -c feature/reactive-prompt-orchestration

echo
echo "=== INSTALL CORE ORCHESTRATOR ==="
mkdir -p "$PROJECT_ROOT/core/ai_core/orchestration" "$PROJECT_ROOT/tests"
cp "$BUNDLE_DIR/core/ai_core/orchestration/reactive_orchestrator.py" \
   "$PROJECT_ROOT/core/ai_core/orchestration/reactive_orchestrator.py"
cp "$BUNDLE_DIR/tests/test_reactive_orchestrator.py" \
   "$PROJECT_ROOT/tests/test_reactive_orchestrator.py"

echo
echo "=== INTEGRATE PROJECT ==="
python3 "$BUNDLE_DIR/integrate_project.py" "$PROJECT_ROOT"

echo
echo "=== TEST ==="
source "$PROJECT_ROOT/.venv/bin/activate"
python -m pytest -q tests/test_reactive_orchestrator.py

echo
echo "=== RESULT ==="
git status --short
git diff --stat
echo
echo "Prepared on branch: $(git branch --show-current)"
echo "Nothing was pushed or merged automatically."
