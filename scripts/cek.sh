#!/usr/bin/env bash
# Satu pintu untuk lint + tes. Deteksi stack otomatis.
# Dipakai oleh manusia, oleh Claude, dan oleh hook Stop.
set -euo pipefail

cd "$(dirname "$0")/.."
ada_cek=0

jalankan() {
  echo "▶ $*"
  "$@"
  ada_cek=1
}

# Struktur folder sesuai ARSITEKTUR.md
if [[ -x scripts/cek-struktur.sh ]]; then
  jalankan scripts/cek-struktur.sh
fi

# Node.js
if [[ -f package.json ]]; then
  if grep -q '"lint"[[:space:]]*:' package.json; then
    jalankan npm run --silent lint
  fi
  if grep -q '"test"[[:space:]]*:' package.json && ! grep -q 'no test specified' package.json; then
    jalankan npm run --silent test
  fi
fi

# Python
if [[ -f pyproject.toml || -f requirements.txt || -f setup.py ]]; then
  if command -v ruff >/dev/null 2>&1; then
    jalankan ruff check .
  fi
  if command -v pytest >/dev/null 2>&1 && { compgen -G "tests/*.py" >/dev/null || compgen -G "test_*.py" >/dev/null; }; then
    jalankan pytest -q
  fi
fi

# Go
if [[ -f go.mod ]]; then
  jalankan go vet ./...
  jalankan go test ./...
fi

# Rust
if [[ -f Cargo.toml ]]; then
  jalankan cargo test --quiet
fi

# PHP
if [[ -f composer.json ]] && grep -q '"test"[[:space:]]*:' composer.json; then
  jalankan composer test
fi

if [[ $ada_cek -eq 0 ]]; then
  echo "Belum ada tes atau lint yang terdeteksi. Lewati."
else
  echo "✔ Semua cek lulus."
fi
