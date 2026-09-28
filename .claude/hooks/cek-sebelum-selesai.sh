#!/usr/bin/env bash
# Hook Stop: sebelum Claude berhenti, jalankan scripts/cek.sh.
# Kalau gagal, exit 2 supaya Claude memperbaikinya dulu.
dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
input="$(cat)"

# Cegah loop tanpa akhir: kalau hook ini sudah memaksa Claude lanjut sekali, izinkan berhenti.
if grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true' <<<"$input"; then
  exit 0
fi

# Tidak ada perubahan file: tidak perlu cek.
if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1 && [[ -z "$(git -C "$dir" status --porcelain)" ]]; then
  exit 0
fi

[[ -x "$dir/scripts/cek.sh" ]] || exit 0

if ! output="$("$dir/scripts/cek.sh" 2>&1)"; then
  {
    echo "Cek otomatis (scripts/cek.sh) GAGAL. Perbaiki sebelum selesai. Jangan hapus atau lewati tes."
    echo "--- 40 baris terakhir ---"
    tail -n 40 <<<"$output"
  } >&2
  exit 2
fi
exit 0
