#!/usr/bin/env bash
# Hook PreToolUse (Write): tolak pembuatan file baru di lokasi yang tidak sesuai
# .claude/struktur-izin.txt. Menimpa file yang sudah ada tetap diizinkan.
# Exit 2 = blokir aksi dan kirim pesan ke Claude.
dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
input="$(cat)"

path="$(grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' <<<"$input" | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/')"
[[ -n "$path" ]] || exit 0
[[ "$path" == /* ]] || path="$dir/$path"

# File sudah ada: ini edit isi, bukan penambahan struktur.
[[ -e "$path" ]] && exit 0

if command -v realpath >/dev/null 2>&1; then
  dir="$(realpath -m "$dir" 2>/dev/null || echo "$dir")"
  path="$(realpath -m "$path" 2>/dev/null || echo "$path")"
fi

# Di luar proyek: bukan urusan hook ini.
case "$path" in
  "$dir"/*) rel="${path#"$dir"/}" ;;
  *) exit 0 ;;
esac

[[ -x "$dir/scripts/cek-struktur.sh" ]] || exit 0

if ! "$dir/scripts/cek-struktur.sh" --path "$rel"; then
  echo "Lokasi '$rel' tidak sesuai ARSITEKTUR.md (.claude/struktur-izin.txt). Pilih lokasi yang sesuai pola, atau berhenti dan tanya manusia. Jangan mengubah daftar pola." >&2
  exit 2
fi
exit 0
