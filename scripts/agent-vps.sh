#!/usr/bin/env bash
# Runner Claude Code headless untuk VPS.
# Alur: branch baru agent/* dari origin/main -> claude -p -> scripts/cek.sh -> commit
# -> push -> buka PR. Tidak pernah push atau merge ke main; manusia yang me-review.
# Pakai:
#   scripts/agent-vps.sh "tugas"
#   scripts/agent-vps.sh -f tugas.txt
# Variabel opsional: AGENT_BASE (default main), AGENT_MAX_TURNS (30), AGENT_LOG_DIR.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "${1:-}" == "-f" ]]; then
  tugas="$(cat "${2:?Pakai: scripts/agent-vps.sh -f tugas.txt}")"
else
  tugas="${1:?Pakai: scripts/agent-vps.sh \"tugas\"}"
fi
[[ -n "${tugas//[[:space:]]/}" ]] || { echo "Tugas kosong. Batal."; exit 1; }

base="${AGENT_BASE:-main}"
maks="${AGENT_MAX_TURNS:-30}"
log_dir="${AGENT_LOG_DIR:-$HOME/.claude-agent/log}"
mkdir -p "$log_dir"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Folder kerja tidak bersih. Periksa dulu dengan 'git status'. Batal."
  exit 1
fi

slug="$(head -n 1 <<<"$tugas" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | cut -c 1-40 | sed 's/^-*//; s/-*$//')"
branch="agent/$(date +%Y%m%d-%H%M%S)-${slug:-tugas}"
log="$log_dir/${branch#agent/}"
judul="agent: $(head -n 1 <<<"$tugas" | cut -c 1-60)"

# Hasil yang gagal tetap disimpan sebagai commit lokal (tidak di-push) supaya bisa diperiksa,
# lalu kembali ke origin/main agar folder kerja bersih untuk run berikutnya.
simpan_gagal() {
  echo "✘ $1. Tidak di-push. Log: $log.*"
  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    git commit -q --no-verify -m "$judul (GAGAL: $1)"
    echo "Perubahan disimpan di branch lokal $branch."
  fi
  git checkout -q --detach "origin/$base"
  exit 1
}

git fetch -q origin "$base"
git checkout -q -B "$branch" "origin/$base"
echo "▶ Branch $branch"

prompt="$tugas

Aturan run otomatis:
- Ikuti CLAUDE.md dan ARSITEKTUR.md. File baru hanya di lokasi yang sesuai pola.
- Jangan memindahkan, mengganti nama, atau menghapus file yang sudah ada.
- Jalankan ./scripts/cek.sh sampai lulus. Jangan commit atau push; runner yang melakukannya.
- Kalau tugas tidak bisa dikerjakan tanpa melanggar aturan, berhenti dan jelaskan alasannya."

echo "▶ claude -p (maks $maks giliran)"
if ! claude -p "$prompt" --permission-mode acceptEdits --max-turns "$maks" \
    --output-format json >"$log.claude.json" 2>"$log.claude.err"; then
  simpan_gagal "claude berhenti dengan error"
fi

if [[ -z "$(git status --porcelain)" ]]; then
  echo "Tidak ada perubahan. Selesai."
  git checkout -q --detach "origin/$base"
  git branch -q -D "$branch"
  exit 0
fi

# Gerbang terakhir, di luar kendali Claude: tanpa izin ubah struktur.
echo "▶ scripts/cek.sh"
if ! env -u IZINKAN_UBAH_STRUKTUR CEK_STRUKTUR_BASE="origin/$base" ./scripts/cek.sh >"$log.cek.log" 2>&1; then
  tail -n 20 "$log.cek.log"
  simpan_gagal "scripts/cek.sh gagal"
fi

git add -A
git commit -q -m "$judul" -m "$tugas"
git push -q -u origin "$branch"
echo "✔ Di-push ke $branch"

badan="Dibuat otomatis oleh scripts/agent-vps.sh.

## Tugas
$tugas

## Cek
scripts/cek.sh lulus di VPS. Review perubahan sebelum merge."

if command -v gh >/dev/null 2>&1; then
  gh pr create --base "$base" --head "$branch" --title "$judul" --body "$badan"
else
  echo "gh tidak terpasang. Buka PR manual dari branch $branch."
fi
git checkout -q --detach "origin/$base"
