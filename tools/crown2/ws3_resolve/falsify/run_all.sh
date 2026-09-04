#!/bin/sh
# Runs every falsifier; exit code 1 from a file means the counterexample REPRODUCES today.
cd "$(dirname "$0")" && for f in f0*.py; do echo "=== $f"; python3 "$f"; echo "exit=$?"; done
