#!/usr/bin/env bash
# Hook PreToolUse: tolak edit file saat berada di branch main/master.
# Exit 2 = blokir aksi dan kirim pesan ke Claude.
dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Di luar git, atau repo belum punya commit: izinkan.
git -C "$dir" rev-parse --verify -q HEAD >/dev/null 2>&1 || exit 0

branch="$(git -C "$dir" symbolic-ref --short -q HEAD 2>/dev/null || true)"
if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  echo "Dilarang mengedit langsung di branch '$branch'. Buat branch dulu: git checkout -b nama-fitur" >&2
  exit 2
fi
exit 0
