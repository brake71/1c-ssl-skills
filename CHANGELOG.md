# Changelog

## 2026-06-08 — BSP skills consolidation

### feat: 4 cluster umbrella skills

Replace 25 standalone BSP skills with 4 cluster skills + decision-tree routing.

| Cluster | Content | Leaf skills |
|---------|---------|-------------|
| `bsp-core` | Navigation, utilities, background jobs, prefixes, update | 5 |
| `bsp-data` | Exchange, e-signature, contact info, classifiers, currencies, external components | 6 |
| `bsp-ui-forms` | Connected commands, printing, form properties, multilang, files/versions, dedup | 6 |
| `bsp-ops` | Users/access, comms, business processes, admin tools, backup, monitoring, personal data | 7 |

Each cluster:
- SKILL.md (~70-80 lines) — frontmatter + decision tree + leaf index
- references/ — full leaf skill content (24 files, no frontmatter, no hardcoded paths)
- scripts/ — Python search script for 1C config export

### feat: Python search scripts (4)

Per-cluster script with `detect`, `method`, `module`, `modules-by-subsystem` commands.
Auto-detect --src by walking upward for CommonModules/.
Parse BSL files by #Область ПрограммныйИнтерфейс for stable API listing.

### fix: content restoration

bsp-bp-tasks.md and bsp-admin-tools.md lost Patterns/Anti-patterns/BSL examples during migration. Restored from originals.

### fix: key-methods.md links

bsp-commands-external and bsp-files-and-versions reference files had broken `references/key-methods.md` links. Updated to `bsp-*-key-methods.md`.

### fix: argparse --src in search scripts

Windows Python + subparsers + `--src` before subcommand = parse fail. Switched to `parents` pattern. All 4 scripts fixed.

### chore: .gitignore

Add `__pycache__/` and `*.pyc`.

### refactor: remove old standalone skills

Delete 25 old bsp-* directories. 8954 lines removed.

### docs: AGENTS.md

Update .claude/skills section. 25 entries → 4 clusters + 3 non-BSP skills.
