#!/usr/bin/env bash
set -euo pipefail

repository="${SKILLS_REPOSITORY:-brake71/1c-ssl-skills}"
ref="${SKILLS_REF:-main}"
agent="${SKILLS_AGENT:-claude}"
target="${SKILLS_TARGET:-}"
skill="${SKILLS_NAME:-bsp}"
source_dir="${SKILLS_SOURCE_DIR:-}"

usage() {
  cat <<'EOF'
Install or update a skill from brake71/1c-ssl-skills.

Usage:
  install.sh [options]

Options:
  --agent <claude|codex|opencode>  Select the default installation directory.
  --target <directory>             Install into an explicit skills directory.
  --skill <name>                   Skill to install (default: bsp).
  --ref <git-ref>                  Branch, tag, or commit (default: main).
  --repository <owner/repo>        GitHub repository to download.
  --source <directory>             Use a local repository checkout (for testing).
  -h, --help                       Show this help.

The same values can be supplied with SKILLS_AGENT, SKILLS_TARGET, SKILLS_NAME,
SKILLS_REF, SKILLS_REPOSITORY, and SKILLS_SOURCE_DIR.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      agent="${2:?missing value for --agent}"
      shift 2
      ;;
    --target)
      target="${2:?missing value for --target}"
      shift 2
      ;;
    --skill)
      skill="${2:?missing value for --skill}"
      shift 2
      ;;
    --ref)
      ref="${2:?missing value for --ref}"
      shift 2
      ;;
    --repository)
      repository="${2:?missing value for --repository}"
      shift 2
      ;;
    --source)
      source_dir="${2:?missing value for --source}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

agent_lower="$(printf '%s' "$agent" | tr '[:upper:]' '[:lower:]')"
case "$agent_lower" in
  claude)
    default_target="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
    ;;
  codex)
    default_target="${CODEX_HOME:-$HOME/.codex}/skills"
    ;;
  opencode)
    default_target="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills"
    ;;
  *)
    echo "Unsupported agent '$agent'. Use claude, codex, opencode, or --target." >&2
    exit 2
    ;;
esac

target="${target:-$default_target}"

if [[ ! "$skill" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Invalid skill name '$skill'." >&2
  exit 2
fi
if [[ ! "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "Invalid GitHub repository '$repository'." >&2
  exit 2
fi
if [[ -z "$ref" || "$ref" =~ [[:space:]] ]]; then
  echo "Invalid git ref '$ref'." >&2
  exit 2
fi

case "$target" in
  ""|"/")
    echo "Refusing to use '$target' as the skills directory." >&2
    exit 2
    ;;
esac

download_dir=""
transaction_dir=""
destination=""
backup=""

cleanup() {
  if [[ -n "$backup" && -e "$backup" && -n "$destination" && ! -e "$destination" ]]; then
    mv "$backup" "$destination"
  fi
  if [[ -n "$transaction_dir" && -d "$transaction_dir" ]]; then
    rm -rf -- "$transaction_dir"
  fi
  if [[ -n "$download_dir" && -d "$download_dir" ]]; then
    rm -rf -- "$download_dir"
  fi
}
trap cleanup EXIT

if [[ -n "$source_dir" ]]; then
  repository_root="$source_dir"
else
  for command_name in curl tar; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      echo "Required command not found: $command_name" >&2
      exit 1
    fi
  done

  download_dir="$(mktemp -d)"
  archive="$download_dir/repository.tar.gz"
  extracted="$download_dir/extracted"
  mkdir -p "$extracted"
  curl --fail --silent --show-error --location --retry 3 \
    "https://codeload.github.com/$repository/tar.gz/$ref" \
    --output "$archive"
  tar -xzf "$archive" -C "$extracted"
  repository_root=""
  for candidate in "$extracted"/*; do
    if [[ -d "$candidate" ]]; then
      repository_root="$candidate"
      break
    fi
  done
  if [[ -z "$repository_root" ]]; then
    echo "Downloaded archive has no repository root directory." >&2
    exit 1
  fi
fi

source_skill="$repository_root/skills/$skill"
if [[ ! -f "$source_skill/SKILL.md" ]]; then
  echo "Skill '$skill' not found at $source_skill." >&2
  exit 1
fi

mkdir -p "$target"
transaction_dir="$(mktemp -d "$target/.skill-install.XXXXXX")"
staged="$transaction_dir/$skill"
cp -R "$source_skill" "$staged"

destination="$target/$skill"
backup="$transaction_dir/previous"
if [[ -e "$destination" || -L "$destination" ]]; then
  mv "$destination" "$backup"
fi
mv "$staged" "$destination"

rm -rf -- "$transaction_dir"
transaction_dir=""
backup=""

echo "Installed '$skill' from '$repository@$ref' to '$destination'."
