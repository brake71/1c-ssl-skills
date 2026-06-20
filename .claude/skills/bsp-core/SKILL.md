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

# BSP Core

Routing skill for core BSP subsystems. Read the decision tree, determine
the correct leaf skill, then load `references/<leaf>.md` for full API details.

## When to use

Task involves BSP core utilities: navigation, common functions,
background/reglament jobs, number prefixing, or infobase updates.

Determine the leaf skill by trigger words (first match wins):

1. **bsp-update** — update, infobase update, ОбновлениеВерсииИБ,
   ОбновлениеКонфигурации, migration, version of IB, update handler
2. **bsp-longs-and-jobs** — background job, long operation,
   ДлительныеОперации, reglament job, РегламентныеЗадания,
   async, ДлительныеОперации.Выполнить, scheduled job
3. **bsp-prefixes** — prefix, ПрефиксацияОбъектов,
   number prefix, document number (prefix context), infobase prefix
4. **bsp-base-common** — СообщитьПользователю, serialization,
   XML, JSON, safe storage, ОбщегоНазначения,
   СтроковыеФункции, ФайловаяСистема, СообщитьПользователю,
   ЗначениеВJSON, ЭтоСсылка, ПодсистемаСуществует,
   ЗаписатьДанныеВБезопасноеХранилище, ПодставитьПараметрыВСтроку
5. **bsp-fundamentals** — find module, which module,
   module suffix, subsystem navigation, stable API vs internal,
   BSP structure, CommonModules, how to find module,
   ПрограммныйИнтерфейс, СлужебныйПрограммныйИнтерфейс

## Leaf skills

| Leaf | File | Brief |
|------|------|-------|
| bsp-update | references/bsp-update.md | Infobase update handlers, version migration |
| bsp-longs-and-jobs | references/bsp-longs-and-jobs.md | Background jobs, long operations, scheduled jobs |
| bsp-prefixes | references/bsp-prefixes.md | Object number prefixes, stripping, infobase prefix |
| bsp-base-common | references/bsp-base-common.md | General utilities: messages, serialization, safe storage |
| bsp-fundamentals | references/bsp-fundamentals.md | BSP navigation map, module suffixes, subsystem index |

## Cross-cluster routing

Core subsystems are used by every other BSP cluster. If the task clearly
belongs to another cluster, load that umbrella instead:

| Trigger | Go to |
|---------|-------|
| print, external report/processor, file attach, versioning, form property, dedup, multilang | `bsp-ui-forms` |
| data exchange, e-signature/MChD, contact info/address, classifier, currency/bank, external component/OData | `bsp-data` |
| user/access/role, email/SMS/chat, business process/task, admin tools, backup, monitoring, personal data | `bsp-ops` |

**Ambiguous keywords** (first match wins, but consider both clusters):

- `ДлительныеОперации.ВыполнитьФункцию` is a core utility, but it is typically
  called *from* a UI/ops context (print in background, exchange in background,
  backup in background). If the task is «run X in background», load
  `bsp-longs-and-jobs` (here) for the API, but also check the *calling*
  cluster for what X is.
- `РегламентныеЗадания` (here) vs `УдалениеПомеченныхОбъектов` /
  `РезервноеКопированиеИБ` (in `bsp-ops`): both involve scheduled jobs, but
  the ops-side subsystems register their own scheduled handlers. If the task
  is «configure backup schedule», go to `bsp-ops` → `bsp-backup`; if it is
  «add a custom scheduled job», stay here in `bsp-longs-and-jobs`.

If no trigger matches, fall back to `bsp-fundamentals` and locate the
subsystem by the module map.

## Search tools

Use `scripts/bsp_core_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_core_search.py method СообщитьПользователю --src <path/to/cf>
python scripts/bsp_core_search.py module ОбщегоНазначения --src <path/to/cf>
python scripts/bsp_core_search.py modules-by-subsystem БазоваяФункциональность --src <path/to/cf>
python scripts/bsp_core_search.py detect --src <path/to/cf>
```

`--src <path>` is **required**: path to the configuration export root
(directory containing `CommonModules/`). No auto-detection — the agent
must pass the path explicitly. If the path is invalid or has no
`CommonModules/` subdir, the script exits with a non-zero code.
