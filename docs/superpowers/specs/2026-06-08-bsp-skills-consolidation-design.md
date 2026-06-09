# BSP Skills Consolidation Design

**Date:** 2026-06-08
**Status:** Approved
**Scope:** 25 BSP skills → 4 clustered umbrella skills + per-cluster Python search scripts

## Problem

25 BSP skills flood the agent's system prompt with description strings at every session start. The list is hard to navigate and wastes context. Individual SKILL.md files (30-60 KB each) are loaded in full when invoked, but the core pain is the sheer number of skills in the registry.

## Solution

Consolidate 25 leaf skills into **4 cluster umbrella skills** with decision-tree routing inside each SKILL.md. Leaf skill content moves to `references/`. Per-cluster Python search scripts provide method/module lookup in target repository configuration exports.

## Architecture

### Cluster Map

| Cluster | Description (for system prompt) | Leaf skills |
|---------|--------------------------------|-------------|
| `bsp-core` | Navigation, utilities, background jobs, prefixes, infobase updates | bsp-fundamentals, bsp-base-common, bsp-longs-and-jobs, bsp-prefixes, bsp-update |
| `bsp-data` | Data exchange, e-signature/MChD, contact info, classifiers, currencies/banks, external components | bsp-data-exchange, bsp-esign-mcd, bsp-contact-info, bsp-classifiers, bsp-currencies-banks, bsp-external-components |
| `bsp-ui-forms` | Connected commands, printing, form properties, multilang, files/versions, dedup | bsp-commands-external, bsp-print-reports, bsp-forms-validation, bsp-multilang, bsp-files-and-versions, bsp-report-dedup |
| `bsp-ops` | Users/access, email/SMS/chat, business processes, admin tools, backup, perf monitoring, personal data | bsp-users-access, bsp-comms, bsp-bp-tasks, bsp-admin-tools, bsp-backup, bsp-perf-monitoring, bsp-protection-pd |

### Directory Structure (after migration)

```
.claude/skills/
  bsp-core/
    SKILL.md                        # 3-6 KB: frontmatter + decision tree + leaf list
    scripts/
      bsp_core_search.py            # method/module lookup for core subsystems
    references/
      bsp-fundamentals.md           # former SKILL.md content
      bsp-base-common.md
      bsp-longs-and-jobs.md
      bsp-prefixes.md
      bsp-update.md

  bsp-data/
    SKILL.md                        # 3-6 KB
    scripts/
      bsp_data_search.py            # lookup for data subsystems
    references/
      bsp-data-exchange.md
      bsp-esign-mcd.md
      bsp-contact-info.md
      bsp-classifiers.md
      bsp-currencies-banks.md
      bsp-external-components.md

  bsp-ui-forms/
    SKILL.md                        # 3-6 KB
    scripts/
      bsp_ui_search.py              # lookup for UI subsystems
    references/
      bsp-commands-external.md
      bsp-print-reports.md
      bsp-forms-validation.md
      bsp-multilang.md
      bsp-files-and-versions.md
      bsp-report-dedup.md

  bsp-ops/
    SKILL.md                        # 3-6 KB
    scripts/
      bsp_ops_search.py             # lookup for ops subsystems
    references/
      bsp-users-access.md
      bsp-comms.md
      bsp-bp-tasks.md
      bsp-admin-tools.md
      bsp-backup.md
      bsp-perf-monitoring.md
      bsp-protection-pd.md

  # Unchanged (non-BSP skills):
  agents-best-practices/
  opencode-runner/
  prompt-crafting-guide/
```

### Cluster SKILL.md Format

Each cluster SKILL.md follows this structure:

```yaml
---
name: bsp-core
description: "Navigation, utilities, background jobs, prefixes, infobase updates in 1C BSP"
metadata:
  scope: bsp
  version: "3.1.11+"
  layer: umbrella
  leaf_skills:
    - bsp-fundamentals
    - bsp-base-common
    - bsp-longs-and-jobs
    - bsp-prefixes
    - bsp-update
---
```

```markdown
# BSP Core

Routing skill for core BSP subsystems. Read the decision tree, determine
the correct leaf skill, then load references/<leaf>.md for full API details.

## When to use

Task involves BSP core utilities: navigation, common functions,
background/reglament jobs, number prefixing, or infobase updates.

Determine the leaf skill by trigger words (first match wins):

1. **bsp-update** — "update", "infobase update", "ОбновлениеВерсииИБ",
   "ОбновлениеКонфигурации", "migration", "version of IB"
2. **bsp-longs-and-jobs** — "background job", "long operation",
   "ДлительныеОперации", "reglament job", "РегламентныеЗадания",
   "async", "ДлительныеОперации.Выполнить"
3. **bsp-prefixes** — "prefix", "ПрефиксацияОбъектов",
   "number prefix", "document number" (prefix context)
4. **bsp-base-common** — "СообщитьПользователю", "serialization",
   "XML", "JSON", "safe storage", "ОбщегоНазначения",
   "СтроковыеФункции", "ФайловаяСистема"
5. **bsp-fundamentals** — "find module", "which module",
   "module suffix", "subsystem navigation", "stable API vs internal",
   "BSP structure"

## Leaf skills

| Leaf | File | Brief |
|------|------|-------|
| bsp-fundamentals | references/bsp-fundamentals.md | BSP navigation map, module suffixes, subsystem index |
| bsp-base-common | references/bsp-base-common.md | General utilities: messages, serialization, safe storage |
| bsp-longs-and-jobs | references/bsp-longs-and-jobs.md | Background jobs, long operations, scheduled jobs |
| bsp-prefixes | references/bsp-prefixes.md | Object number prefixes, stripping, infobase prefix |
| bsp-update | references/bsp-update.md | Infobase update handlers, version migration |

## Search tools

Use `scripts/bsp_core_search.py` to look up methods and modules
in the target repository's configuration export:

  python scripts/bsp_core_search.py method СообщитьПользователю [--src <path>]
  python scripts/bsp_core_search.py module ОбщегоНазначения [--src <path>]
  python scripts/bsp_core_search.py modules-by-subsystem БазоваяФункциональность [--src <path>]
  python scripts/bsp_core_search.py detect [--src <path>]

If `--src` is omitted, the script auto-detects the configuration
export root by globbing for `**/CommonModules/` upward from CWD.
If multiple candidates found, it prints them to stderr and asks
for clarification.
```

### Decision trees for other clusters

**bsp-data:**

1. **bsp-data-exchange** — "exchange", "ОбменДанными", "sync", "ПланыОбмена", "EnterpriseData"
2. **bsp-esign-mcd** — "signature", "ЭлектроннаяПодпись", "МЧД", "crypto", "certificate", "ЭЦП"
3. **bsp-contact-info** — "address", "КонтактнаяИнформация", "KLADR", "FIAS", "ОКТМО", "phone", "email" (contact context)
4. **bsp-classifiers** — "calendar", "production calendar", "ПроизводственныйКалендарь", "working days", "ГрафикиРаботы"
5. **bsp-currencies-banks** — "currency", "Валюты", "exchange rate", "bank", "Банки", "БИК", "amount in words"
6. **bsp-external-components** — "external component", "ВнешниеКомпоненты", "Native API", "COM", "OData"

**bsp-ui-forms:**

1. **bsp-commands-external** — "connected command", "ПодключаемыеКоманды", "external report", "ДополнительныеОтчетыИОбработки", "CreateOnBasis", "СозданиеНаОсновании"
2. **bsp-print-reports** — "print", "Печать", "print form", "УправлениеПечатью", "report variant", "ВариантыОтчетов"
3. **bsp-forms-validation** — "lock edit", "ЗапретРедактирования", "additional attribute", "Свойства", "form property"
4. **bsp-files-and-versions** — "attach file", "РаботаСФайлами", "versioning", "ВерсионированиеОбъектов", "file attach"
5. **bsp-multilang** — "multilingual", "Мультиязычность", "language suffix", "translation in form"
6. **bsp-report-dedup** — "duplicate", "ПоискИУдалениеДублей", "merge objects", "replace reference", "bulk edit"

**bsp-ops:**

1. **bsp-users-access** — "user", "Пользователи", "access", "УправлениеДоступом", "role", "RLS", "administrator"
2. **bsp-comms** — "email", "Почта", "SMS", "ОтправкаSMS", "ШаблоныСообщений", "chat", "Обсуждения", "1C:Dialogue"
3. **bsp-bp-tasks** — "business process", "БизнесПроцессы", "task", "Задача", "redirect task", "overdue"
4. **bsp-admin-tools** — "connection lock", "ЗавершениеРаботыПользователей", "delete marked", "УдалениеПомеченныхОбъектов", "scheduled deletion"
5. **bsp-backup** — "backup", "РезервноеКопированиеИБ", "auto backup", "backup schedule"
6. **bsp-perf-monitoring** — "performance", "ОценкаПроизводительности", "key operation", "monitoring center", "benchmark"
7. **bsp-protection-pd** — "personal data", "ЗащитаПерсональныхДанных", "152-FZ", "consent", "data subject"

### Leaf skill content (references/*.md)

Each leaf skill file is the former `SKILL.md` of the standalone skill, with the following modifications:

1. **Remove** `## How to explore deeper` section entirely.
2. **Remove** all references to `bsp3111_md/`, `src/cf/`, or any hardcoded repository paths.
3. **Remove** frontmatter (not needed in references).
4. **Add** at the end: a short note pointing to the cluster's search script for live method/module lookup.
5. All other sections (When to use, Core concepts, Key methods, Patterns, Anti-patterns) remain unchanged.

### Python Search Scripts

Each cluster has a `scripts/` directory with a per-cluster Python script.

**Common CLI interface:**

```
python scripts/<cluster>_search.py <command> [args] [--src <path>]
```

**Commands:**

| Command | Description |
|---------|-------------|
| `method <name>` | Find module containing an export method matching `<name>` |
| `module <name>` | Show path to module in export + list stable API methods (from `#Область ПрограммныйИнтерфейс`) |
| `modules-by-subsystem <name>` | List common modules belonging to a subsystem (from `Subsystems/*.xml`) |
| `detect` | Detect BSP version and return summary info |

**Auto-detection of `--src`:**

1. Walk upward from CWD looking for directories containing `CommonModules/`.
2. If exactly one found — use it.
3. If multiple found — print candidates to stderr, exit with code 1.
4. User re-runs with explicit `--src <path>`.

**Per-cluster module scope:**

Each script only indexes modules relevant to its cluster. This keeps searches fast and results relevant.

- `bsp_core_search.py`: ОбщегоНазначения*, СтроковыеФункции*, ФайловаяСистема*, ДлительныеОперации*, РегламентныеЗадания*, ОбновлениеВерсииИБ*, ПрефиксацияОбъектов*, and modules from StandardSubsystems subsystem
- `bsp_data_search.py`: ОбменДанными*, ЭлектроннаяПодпись*, КонтактнаяИнформация*, АдресныйКлассификатор*, КалендарныеГрафики*, ГрафикиРаботы*, Валюты*, Банки*, ВнешниеКомпоненты*, and corresponding subsystem modules
- `bsp_ui_search.py`: УправлениеПечатью*, ВариантыОтчетов*, ПодключаемыеКоманды*, ДополнительныеОтчетыИОбработки*, ЗапретРедактирования*, Свойства*, РаботаСФайлами*, ВерсионированиеОбъектов*, Мультиязычность*, ПоискИУдалениеДублей*
- `bsp_ops_search.py`: Пользователи*, УправлениеДоступом*, РаботаСПочтовымиСообщениями*, ОтправкаSMS*, ШаблоныСообщений*, Обсуждения*, БизнесПроцессы*, ЗавершениеРаботыПользователей*, УдалениеПомеченныхОбъектов*, РезервноеКопированиеИБ*, ОценкаПроизводительности*, ЗащитаПерсональныхДанных*

**Implementation notes:**

- Python 3, no external dependencies (stdlib only: `os`, `re`, `xml.etree.ElementTree`, `pathlib`, `glob`, `argparse`).
- Parses XML from 1C configuration export (standard format).
- Extracts export method names by parsing BSL files (`.bsl`) looking for `Процедура`/`Функция` + `Экспорт` in `#Область ПрограммныйИнтерфейс`.
- Returns compact text output suitable for agent consumption.

### Preserved artifacts

The following existing skills and files are NOT affected:

- `agents-best-practices/` — remains standalone
- `opencode-runner/` — remains standalone
- `prompt-crafting-guide/` — remains standalone
- `AGENTS.md` — needs update (remove references to old skill names, add cluster names)
- `bsp3111_md/` and `bsp321_md/` — not referenced by skills anymore (remain in repo for developer use)

### Impact on system prompt

| Metric | Before | After |
|--------|--------|-------|
| BSP skill descriptions in prompt | 25 entries (~2 KB) | 4 entries (~400 B) |
| SKILL.md size per invocation | 30-60 KB | 3-6 KB (cluster) + 30-60 KB (leaf, on demand) |
| Routing steps | 1 (direct) | 2 (cluster → leaf) |
| Total skills in registry | 28 (25 BSP + 3 other) | 7 (4 BSP clusters + 3 other) |

### Migration plan (high-level)

1. Create 4 cluster directories with SKILL.md and scripts/
2. For each leaf skill: copy current SKILL.md → references/<name>.md, apply modifications (remove sections, paths)
3. Implement 4 Python search scripts
4. Update AGENTS.md (skill names, navigation instructions)
5. Remove old 25 standalone skill directories
6. Test: agent loads cluster → navigates to leaf → gets API details → uses search script