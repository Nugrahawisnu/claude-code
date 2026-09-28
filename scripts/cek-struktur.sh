#!/usr/bin/env bash
# Cek struktur: semua file harus cocok dengan pola di .claude/struktur-izin.txt.
# Pakai:
#   scripts/cek-struktur.sh              cek seluruh repo (dipanggil scripts/cek.sh)
#   scripts/cek-struktur.sh --path P     exit 0 kalau path relatif P diizinkan, 1 kalau tidak
# Kalau branch dasar (origin/main, main, ...) ada, rename/hapus file dan perubahan
# daftar pola juga ditolak, kecuali IZINKAN_UBAH_STRUKTUR=1 (keputusan manusia).
set -euo pipefail

cd "$(dirname "$0")/.."
daftar=".claude/struktur-izin.txt"

if [[ ! -f "$daftar" ]]; then
  echo "Tidak ada $daftar. Lewati cek struktur."
  exit 0
fi

# Ubah pola glob menjadi regex: ** = apa saja, * dan ? = tanpa "/".
pola_ke_regex() {
  local p="$1" r="" c i=0
  while (( i < ${#p} )); do
    c="${p:i:1}"
    case "$c" in
      '*')
        if [[ "${p:i+1:1}" == '*' ]]; then r+='.*'; i=$((i + 1)); else r+='[^/]*'; fi ;;
      '?') r+='[^/]' ;;
      '.'|'+'|'^'|'$'|'('|')'|'['|']'|'{'|'}'|'|'|'\') r+="\\$c" ;;
      *) r+="$c" ;;
    esac
    i=$((i + 1))
  done
  printf '^%s$' "$r"
}

regexes=()
while IFS= read -r baris || [[ -n "$baris" ]]; do
  baris="${baris%%#*}"
  baris="$(sed 's/^[[:space:]]*//; s/[[:space:]]*$//' <<<"$baris")"
  [[ -n "$baris" ]] && regexes+=("$(pola_ke_regex "$baris")")
done <"$daftar"

diizinkan() {
  local r
  for r in "${regexes[@]}"; do
    [[ "$1" =~ $r ]] && return 0
  done
  return 1
}

if [[ "${1:-}" == "--path" ]]; then
  diizinkan "${2:?path wajib diisi}"
  exit
fi

gagal=0

# 1. Setiap file (tercatat git atau baru, kecuali yang di-.gitignore) harus cocok pola.
while IFS= read -r f; do
  [[ -e "$f" ]] || continue
  if ! diizinkan "$f"; then
    echo "✘ Lokasi tidak sesuai ARSITEKTUR.md: $f"
    gagal=1
  fi
done < <(git ls-files --cached --others --exclude-standard | sort -u)

# 2. Dibanding branch dasar: tolak rename, hapus, dan perubahan daftar pola.
base=""
for b in "${CEK_STRUKTUR_BASE:-}" origin/main main origin/master master; do
  [[ -n "$b" ]] && git rev-parse --verify -q "$b^{commit}" >/dev/null && { base="$b"; break; }
done

if [[ "${IZINKAN_UBAH_STRUKTUR:-0}" == "1" ]]; then
  echo "IZINKAN_UBAH_STRUKTUR=1: rename/hapus tidak dicek."
elif [[ -z "$base" ]]; then
  echo "Branch dasar tidak ditemukan: rename/hapus tidak dicek."
else
  mb="$(git merge-base "$base" HEAD)"
  while IFS=$'\t' read -r status a b; do
    case "$status" in
      D) echo "✘ File dihapus tanpa izin: $a"; gagal=1 ;;
      R*) echo "✘ File dipindah/ganti nama tanpa izin: $a -> $b"; gagal=1 ;;
    esac
    if [[ "$a" == "$daftar" || "${b:-}" == "$daftar" ]]; then
      echo "✘ $daftar diubah. Hanya manusia yang boleh mengubahnya."
      gagal=1
    fi
  done < <(git diff --name-status -M "$mb")
fi

if [[ $gagal -ne 0 ]]; then
  echo "Pindahkan file ke lokasi yang sesuai ARSITEKTUR.md, atau minta manusia mengubah pola."
  echo "Kalau perubahan struktur sudah disetujui manusia: IZINKAN_UBAH_STRUKTUR=1 ./scripts/cek.sh"
  exit 1
fi
echo "✔ Struktur sesuai ARSITEKTUR.md."
