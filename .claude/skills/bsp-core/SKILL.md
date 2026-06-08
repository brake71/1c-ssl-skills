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

## Search tools

Use `scripts/bsp_core_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_core_search.py method СообщитьПользователю [--src <path>]
python scripts/bsp_core_search.py module ОбщегоНазначения [--src <path>]
python scripts/bsp_core_search.py modules-by-subsystem БазоваяФункциональность [--src <path>]
python scripts/bsp_core_search.py detect [--src <path>]
```

If `--src` is omitted, the script auto-detects the configuration
export root by searching upward for a directory containing `CommonModules/`.
If multiple candidates found, it prints them to stderr and exits with code 1.
