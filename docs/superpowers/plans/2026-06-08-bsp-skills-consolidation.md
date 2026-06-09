# BSP Skills Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 25 standalone BSP skills into 4 cluster umbrella skills with decision-tree routing, per-cluster Python search scripts, and leaf content in references/.

**Architecture:** Each cluster SKILL.md contains frontmatter + decision tree + leaf index. Leaf skills move to references/ as .md files with sections How to explore deeper and hardcoded paths removed. Per-cluster Python scripts search 1C configuration export XML/BSL files for methods, modules, and subsystems.

**Tech Stack:** Python 3 (stdlib only: os, re, xml.etree.ElementTree, pathlib, glob, argparse), Markdown, Bash

---

## Task 1: Create bsp-core cluster

**Files:**
- Create: `.claude/skills/bsp-core/SKILL.md`
- Create: `.claude/skills/bsp-core/scripts/bsp_core_search.py`

- [ ] **Step 1: Create bsp-core directory structure**

```bash
mkdir -p .claude/skills/bsp-core/references
mkdir -p .claude/skills/bsp-core/scripts
```

- [ ] **Step 2: Write bsp-core SKILL.md**

```markdown
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
```

- [ ] **Step 3: Write bsp_core_search.py script**

```python
#!/usr/bin/env python3
"""BSP Core search: lookup methods/modules in 1C configuration export.

Covers modules: ОбщегоНазначения*, СтроковыеФункции*, ФайловаяСистема*,
ДлительныеОперации*, РегламентныеЗадания*, ОбновлениеВерсииИБ*,
ПрефиксацияОбъектов*, and StandardSubsystems subsystem modules.
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MODULE_PREFIXES = [
    "ОбщегоНазначения",
    "СтроковыеФункции",
    "ФайловаяСистема",
    "ДлительныеОперации",
    "РегламентныеЗадания",
    "ОбновлениеВерсииИБ",
    "ОбновлениеКонфигурации",
    "ПрефиксацияОбъектов",
]

BSP_SUBSYSTEMS = [
    "СтандартныеПодсистемы",
    "БазоваяФункциональность",
    "ОбновлениеВерсииИБ",
    "ОбновлениеКонфигурации",
    "ПрефиксацияОбъектов",
    "РегламентныеЗадания",
]


def auto_detect_src(start_path="."):
    """Walk upward looking for directory containing CommonModules/."""
    p = Path(start_path).resolve()
    while True:
        if (p / "CommonModules").is_dir():
            return str(p)
        parent = p.parent
        if parent == p:
            break
        p = parent
    return None


def find_src_or_exit(src_arg):
    if src_arg:
        if not Path(src_arg).is_dir():
            print(f"Error: --src path does not exist: {src_arg}", file=sys.stderr)
            sys.exit(1)
        return src_arg
    detected = auto_detect_src()
    if detected:
        return detected
    candidates = []
    for root, dirs, _ in os.walk("."):
        if "CommonModules" in dirs:
            candidates.append(root)
            dirs.remove("CommonModules")
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        print("Multiple configuration export roots found:", file=sys.stderr)
        for c in candidates:
            print(f"  {c}", file=sys.stderr)
        print("Use --src <path> to specify.", file=sys.stderr)
        sys.exit(1)
    print("No configuration export root found. Use --src <path>.", file=sys.stderr)
    sys.exit(1)


def is_relevant_module(module_name):
    return any(module_name.startswith(prefix) for prefix in MODULE_PREFIXES)


def list_common_modules(src):
    cm_dir = Path(src) / "CommonModules"
    if not cm_dir.is_dir():
        return []
    result = []
    for entry in sorted(cm_dir.iterdir()):
        if entry.is_dir() and is_relevant_module(entry.name):
            bsl = entry / "Ext" / "Module.bsl"
            result.append((entry.name, bsl))
    return result


def parse_export_methods(bsl_path, only_stable=True):
    """Parse .bsl file, return list of (method_name, is_stable, region)."""
    if not bsl_path.is_file():
        return []
    text = bsl_path.read_text(encoding="utf-8-sig")
    methods = []
    current_region = None
    in_stable = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#Область"):
            region_name = stripped.replace("#Область", "").strip()
            if region_name == "ПрограммныйИнтерфейс":
                in_stable = True
                current_region = "stable"
            elif region_name == "СлужебныйПрограммныйИнтерфейс":
                in_stable = False
                current_region = "unstable"
            elif region_name == "СлужебныеПроцедурыИФункции":
                current_region = None
            elif region_name == "Переопределение":
                current_region = "override"
        elif stripped.startswith("#КонецОбласти"):
            current_region = None
            in_stable = False
        elif current_region is not None:
            m = re.match(r"^(Функция|Процедура)\s+(\w+)\s*\(", stripped)
            if m and "Экспорт" in stripped:
                method_name = m.group(2)
                is_stable = current_region == "stable"
                if not only_stable or is_stable:
                    methods.append((method_name, is_stable, current_region))
    return methods


def cmd_method(args):
    src = find_src_or_exit(args.src)
    target = args.name
    found = False
    for mod_name, bsl_path in list_common_modules(src):
        methods = parse_export_methods(bsl_path, only_stable=False)
        for method_name, is_stable, region in methods:
            if method_name.lower() == target.lower():
                stability = "stable" if is_stable else "⚠️ unstable"
                print(f"Module: {mod_name}")
                print(f"Method:  {method_name}")
                print(f"Region:  {stability}")
                print(f"Path:    {bsl_path}")
                found = True
                break
        if found:
            break
    if not found:
        print(f"Method '{target}' not found in core BSP modules.")


def cmd_module(args):
    src = find_src_or_exit(args.src)
    target = args.name
    for mod_name, bsl_path in list_common_modules(src):
        if mod_name.lower() == target.lower():
            print(f"Module: {mod_name}")
            print(f"Path:   {bsl_path}")
            methods = parse_export_methods(bsl_path, only_stable=True)
            if methods:
                print(f"\nStable API methods ({len(methods)}):")
                for method_name, _, _ in methods:
                    print(f"  {method_name}")
            else:
                print("No stable API methods found.")
            return
    print(f"Module '{target}' not found in core BSP modules.")


def cmd_modules_by_subsystem(args):
    src = find_src_or_exit(args.src)
    subsystem_name = args.name
    subsys_dir = Path(src) / "Subsystems" / "СтандартныеПодсистемы" / "Subsystems"
    xml_path = subsys_dir / f"{subsystem_name}.xml"
    if not xml_path.is_file():
        print(f"Subsystem '{subsystem_name}' not found at {xml_path}")
        return
    ns = {"xr": "http://v8.1c.ru/8.3/xcf/readable",
          "xsi": "http://www.w3.org/2001/XMLSchema-instance"}
    tree = ET.parse(xml_path)
    root = tree.getroot()
    modules = []
    for content in root.iter():
        tag = content.tag.split("}")[-1] if "}" in content.tag else content.tag
        if tag == "Item":
            ref = content.text
            if ref and "CommonModule." in ref:
                mod_name = ref.replace("CommonModule.", "").strip()
                if is_relevant_module(mod_name):
                    modules.append(mod_name)
    if modules:
        print(f"Core BSP modules in subsystem '{subsystem_name}':")
        for m in sorted(modules):
            print(f"  {m}")
    else:
        print(f"No core BSP modules found in subsystem '{subsystem_name}'.")


def cmd_detect(args):
    src = find_src_or_exit(args.src)
    cm_dir = Path(src) / "CommonModules"
    if not cm_dir.is_dir():
        print(f"No CommonModules/ directory at {src}")
        return
    total = len([d for d in cm_dir.iterdir() if d.is_dir()])
    bsp_count = len(list_common_modules(src))
    print(f"Configuration export root: {src}")
    print(f"Total common modules: {total}")
    print(f"Core BSP modules: {bsp_count}")
    config_xml = Path(src) / "Configuration.xml"
    version = "unknown"
    if config_xml.is_file():
        try:
            tree = ET.parse(config_xml)
            for elem in tree.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "Version":
                    version = elem.text or "unknown"
                    break
        except Exception:
            pass
    print(f"Configuration version: {version}")


def main():
    parser = argparse.ArgumentParser(description="BSP Core module/method search")
    parser.add_argument("--src", help="Path to configuration export root (auto-detected if omitted)")
    sub = parser.add_subparsers(dest="command")

    p_method = sub.add_parser("method", help="Find module containing export method")
    p_method.add_argument("name", help="Method name (e.g. СообщитьПользователю)")

    p_module = sub.add_parser("module", help="Show module path and stable API methods")
    p_module.add_argument("name", help="Module name (e.g. ОбщегоНазначения)")

    p_subsys = sub.add_parser("modules-by-subsystem", help="List core modules in subsystem")
    p_subsys.add_argument("name", help="Subsystem name (e.g. БазоваяФункциональность)")

    sub.add_parser("detect", help="Detect BSP version and module count")

    args = parser.parse_args()
    if args.command == "method":
        cmd_method(args)
    elif args.command == "module":
        cmd_module(args)
    elif args.command == "modules-by-subsystem":
        cmd_modules_by_subsystem(args)
    elif args.command == "detect":
        cmd_detect(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify script runs**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py detect --src src/cf
```

Expected: prints configuration root, module counts, version.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/bsp-core/SKILL.md .claude/skills/bsp-core/scripts/bsp_core_search.py
git commit -m "feat: add bsp-core cluster skill with search script"
```

---

## Task 2: Create bsp-data cluster

**Files:**
- Create: `.claude/skills/bsp-data/SKILL.md`
- Create: `.claude/skills/bsp-data/scripts/bsp_data_search.py`

- [ ] **Step 1: Create bsp-data directory structure**

```bash
mkdir -p .claude/skills/bsp-data/references
mkdir -p .claude/skills/bsp-data/scripts
```

- [ ] **Step 2: Write bsp-data SKILL.md**

```markdown
---
name: bsp-data
description: "Data exchange, e-signature/MChD, contact info, classifiers, currencies/banks, external components in 1C BSP"
metadata:
  scope: bsp
  version: "3.1.11+"
  layer: umbrella
  leaf_skills:
    - bsp-data-exchange
    - bsp-esign-mcd
    - bsp-contact-info
    - bsp-classifiers
    - bsp-currencies-banks
    - bsp-external-components
---

# BSP Data

Routing skill for data-handling BSP subsystems. Read the decision tree,
determine the correct leaf skill, then load `references/<leaf>.md` for
full API details.

## When to use

Task involves BSP data subsystems: exchange, e-signature, contact info,
classifiers, currencies/banks, or external components.

Determine the leaf skill by trigger words (first match wins):

1. **bsp-data-exchange** — exchange, ОбменДанными, sync,
   ПланыОбмена, EnterpriseData, synchronization,
   ОбменДаннымиСервер, узел плана обмена, регистрация изменений
2. **bsp-esign-mcd** — signature, ЭлектроннаяПодпись, МЧД,
   crypto, certificate, ЭЦП, МашиночитаемыеДоверенности,
   ЭлектроннаяПодписьКлиент, подпись документа
3. **bsp-contact-info** — address, КонтактнаяИнформация,
   KLADR, FIAS, ОКТМО, ОКАТО, phone (contact context),
   email (contact context), АдресныйКлассификатор,
   РаботаСАдресами, УправлениеКонтактнойИнформацией
4. **bsp-classifiers** — calendar, production calendar,
   ПроизводственныйКалендарь, working days, ГрафикиРаботы,
   КалендарныеГрафики, business date, рабочий день
5. **bsp-currencies-banks** — currency, Валюты,
   exchange rate, bank, Банки, БИК, amount in words,
   курс валюты, СуммаПрописью, Организации
6. **bsp-external-components** — external component,
   ВнешниеКомпоненты, Native API, COM, OData,
   ИнтерфейсOData, install component

## Leaf skills

| Leaf | File | Brief |
|------|------|-------|
| bsp-data-exchange | references/bsp-data-exchange.md | Data exchange, sync, change registration |
| bsp-esign-mcd | references/bsp-esign-mcd.md | E-signature, MChD, crypto certificates |
| bsp-contact-info | references/bsp-contact-info.md | Contact info, addresses, KLADR/FIAS |
| bsp-classifiers | references/bsp-classifiers.md | Production calendars, work schedules |
| bsp-currencies-banks | references/bsp-currencies-banks.md | Currencies, banks, exchange rates |
| bsp-external-components | references/bsp-external-components.md | External components, OData |

## Search tools

Use `scripts/bsp_data_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_data_search.py method СформироватьПечатныеФормы [--src <path>]
python scripts/bsp_data_search.py module ОбменДаннымиСервер [--src <path>]
python scripts/bsp_data_search.py modules-by-subsystem ОбменДанными [--src <path>]
python scripts/bsp_data_search.py detect [--src <path>]
```

If `--src` is omitted, the script auto-detects the configuration
export root by searching upward for a directory containing `CommonModules/`.
If multiple candidates found, it prints them to stderr and exits with code 1.
```

- [ ] **Step 3: Write bsp_data_search.py script**

Same structure as bsp_core_search.py but with MODULE_PREFIXES set to:
```python
MODULE_PREFIXES = [
    "ОбменДанными",
    "ЭлектроннаяПодпись",
    "МашиночитаемыеДоверенности",
    "УправлениеКонтактнойИнформацией",
    "АдресныйКлассификатор",
    "РаботаСАдресами",
    "КалендарныеГрафики",
    "ГрафикиРаботы",
    "Валюты",
    "Банки",
    "ВнешниеКомпоненты",
    "ИнтерфейсOData",
]
```
and BSP_SUBSYSTEMS:
```python
BSP_SUBSYSTEMS = [
    "ОбменДанными",
    "ЭлектроннаяПодпись",
    "МашиночитаемыеДоверенности",
    "КонтактнаяИнформация",
    "АдресныйКлассификатор",
    "КалендарныеГрафики",
    "ГрафикиРаботы",
    "Валюты",
    "Банки",
    "ВнешниеКомпоненты",
    "ИнтерфейсOData",
]
```
All other logic (auto_detect_src, parse_export_methods, etc.) identical to bsp_core_search.py.

- [ ] **Step 4: Verify script runs**

```bash
python .claude/skills/bsp-data/scripts/bsp_data_search.py detect --src src/cf
```

Expected: prints configuration root, module counts, version.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/bsp-data/
git commit -m "feat: add bsp-data cluster skill with search script"
```

---

## Task 3: Create bsp-ui-forms cluster

**Files:**
- Create: `.claude/skills/bsp-ui-forms/SKILL.md`
- Create: `.claude/skills/bsp-ui-forms/scripts/bsp_ui_search.py`

- [ ] **Step 1: Create bsp-ui-forms directory structure**

```bash
mkdir -p .claude/skills/bsp-ui-forms/references
mkdir -p .claude/skills/bsp-ui-forms/scripts
```

- [ ] **Step 2: Write bsp-ui-forms SKILL.md**

```markdown
---
name: bsp-ui-forms
description: "Connected commands, printing, form properties, multilang, files/versions, dedup in 1C BSP"
metadata:
  scope: bsp
  version: "3.1.11+"
  layer: umbrella
  leaf_skills:
    - bsp-commands-external
    - bsp-print-reports
    - bsp-forms-validation
    - bsp-multilang
    - bsp-files-and-versions
    - bsp-report-dedup
---

# BSP UI & Forms

Routing skill for UI and form-related BSP subsystems. Read the decision
tree, determine the correct leaf skill, then load `references/<leaf>.md`
for full API details.

## When to use

Task involves BSP UI subsystems: connected commands, printing,
form properties, multilang, files/versions, or dedup.

Determine the leaf skill by trigger words (first match wins):

1. **bsp-commands-external** — connected command, ПодключаемыеКоманды,
   external report, ДополнительныеОтчетыИОбработки,
   CreateOnBasis, СозданиеНаОсновании, command kind,
   ПриСозданииНаСервере (command context), fill object,
   external data processor
2. **bsp-print-reports** — print, Печать, print form,
   УправлениеПечатью, report variant, ВариантыОтчетов,
   КомандыПечати, СформироватьПечатныеФормы, ДобавитьКомандыПечати,
   ТабличныйДокумент (print context), MXL
3. **bsp-forms-validation** — lock edit, ЗапретРедактирования,
   additional attribute, Свойства, form property,
   ДополнительныеРеквизиты, ДополнительныеСведения,
   unlock command, ПриЗаписи form validation
4. **bsp-files-and-versions** — attach file, РаботаСФайлами,
   versioning, ВерсионированиеОбъектов, file attach,
   ПрисоединенныеФайлы, file dialog, version history
5. **bsp-multilang** — multilingual, Мультиязычность,
   language suffix, translation in form, ПереводТекста,
   НастройкиЯзыков, fill multilang attributes
6. **bsp-report-dedup** — duplicate, ПоискИУдалениеДублей,
   merge objects, replace reference, bulk edit,
   ГрупповоеИзменениеОбъектов, find similar

## Leaf skills

| Leaf | File | Brief |
|------|------|-------|
| bsp-commands-external | references/bsp-commands-external.md | Connected commands, external reports/processors |
| bsp-print-reports | references/bsp-print-reports.md | Print forms, report variants |
| bsp-forms-validation | references/bsp-forms-validation.md | Lock edit, additional attributes, form validation |
| bsp-files-and-versions | references/bsp-files-and-versions.md | File attachments, object versioning |
| bsp-multilang | references/bsp-multilang.md | Multilingual attributes, translations |
| bsp-report-dedup | references/bsp-report-dedup.md | Duplicate search, merge, bulk edit |

## Search tools

Use `scripts/bsp_ui_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_ui_search.py method ДобавитьКомандыПечати [--src <path>]
python scripts/bsp_ui_search.py module УправлениеПечатью [--src <path>]
python scripts/bsp_ui_search.py modules-by-subsystem Печать [--src <path>]
python scripts/bsp_ui_search.py detect [--src <path>]
```

If `--src` is omitted, the script auto-detects the configuration
export root by searching upward for a directory containing `CommonModules/`.
If multiple candidates found, it prints them to stderr and exits with code 1.
```

- [ ] **Step 3: Write bsp_ui_search.py script**

Same structure as bsp_core_search.py but with MODULE_PREFIXES set to:
```python
MODULE_PREFIXES = [
    "ПодключаемыеКоманды",
    "ДополнительныеОтчетыИОбработки",
    "УправлениеПечатью",
    "ВариантыОтчетов",
    "ЗапретРедактирования",
    "Свойства",
    "РаботаСФайлами",
    "ВерсионированиеОбъектов",
    "Мультиязычность",
    "ПереводТекста",
    "ПоискИУдалениеДублей",
    "ГрупповоеИзменениеОбъектов",
]
```
and BSP_SUBSYSTEMS:
```python
BSP_SUBSYSTEMS = [
    "ПодключаемыеКоманды",
    "ДополнительныеОтчетыИОбработки",
    "Печать",
    "ВариантыОтчетов",
    "ЗапретРедактированияРеквизитовОбъектов",
    "Свойства",
    "РаботаСФайлами",
    "ВерсионированиеОбъектов",
    "ВыгрузкаОбъектовВФайлы",
    "Мультиязычность",
    "ПереводТекста",
    "ПоискИУдалениеДублей",
    "ГрупповоеИзменениеОбъектов",
]
```

- [ ] **Step 4: Verify script runs**

```bash
python .claude/skills/bsp-ui-forms/scripts/bsp_ui_search.py detect --src src/cf
```

Expected: prints configuration root, module counts, version.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/bsp-ui-forms/
git commit -m "feat: add bsp-ui-forms cluster skill with search script"
```

---

## Task 4: Create bsp-ops cluster

**Files:**
- Create: `.claude/skills/bsp-ops/SKILL.md`
- Create: `.claude/skills/bsp-ops/scripts/bsp_ops_search.py`

- [ ] **Step 1: Create bsp-ops directory structure**

```bash
mkdir -p .claude/skills/bsp-ops/references
mkdir -p .claude/skills/bsp-ops/scripts
```

- [ ] **Step 2: Write bsp-ops SKILL.md**

```markdown
---
name: bsp-ops
description: "Users/access, email/SMS, business processes, admin tools, backup, monitoring, personal data in 1C BSP"
metadata:
  scope: bsp
  version: "3.1.11+"
  layer: umbrella
  leaf_skills:
    - bsp-users-access
    - bsp-comms
    - bsp-bp-tasks
    - bsp-admin-tools
    - bsp-backup
    - bsp-perf-monitoring
    - bsp-protection-pd
---

# BSP Operations

Routing skill for operational BSP subsystems. Read the decision tree,
determine the correct leaf skill, then load `references/<leaf>.md` for
full API details.

## When to use

Task involves BSP operational subsystems: users, access, communications,
business processes, admin tools, backup, monitoring, or personal data.

Determine the leaf skill by trigger words (first match wins):

1. **bsp-users-access** — user, Пользователи, access,
   УправлениеДоступом, role, RLS, administrator,
   ВнешниеПользователи, ТекущийПользователь,
   доступ, права, роль
2. **bsp-comms** — email, Почта, SMS, ОтправкаSMS,
   ШаблоныСообщений, chat, Обсуждения, 1C:Dialogue,
   РаботаСПочтовымиСообщениями, Взаимодействия,
   send email, send SMS, message template
3. **bsp-bp-tasks** — business process, БизнесПроцессы,
   task, Задача, redirect task, overdue,
   БизнесПроцессыИЗадачи, execute task, leading task
4. **bsp-admin-tools** — connection lock, ЗавершениеРаботыПользователей,
   delete marked, УдалениеПомеченныхОбъектов,
   scheduled deletion, active connections,
   administration parameters, put session to termination
5. **bsp-backup** — backup, РезервноеКопированиеИБ,
   auto backup, backup schedule, next backup date,
   backup settings, backup form
6. **bsp-perf-monitoring** — performance, ОценкаПроизводительности,
   key operation, monitoring center, ЦентрМониторинга,
   benchmark, замер, timing, business statistics
7. **bsp-protection-pd** — personal data, ЗащитаПерсональныхДанных,
   152-FZ, consent, data subject, ПДн,
   разрушение персональных данных, subject consent

## Leaf skills

| Leaf | File | Brief |
|------|------|-------|
| bsp-users-access | references/bsp-users-access.md | Users, access control, RLS, roles |
| bsp-comms | references/bsp-comms.md | Email, SMS, chat, message templates |
| bsp-bp-tasks | references/bsp-bp-tasks.md | Business processes, tasks, overdue |
| bsp-admin-tools | references/bsp-admin-tools.md | Connection locks, deletion, admin |
| bsp-backup | references/bsp-backup.md | Infobase backup, schedules |
| bsp-perf-monitoring | references/bsp-perf-monitoring.md | Performance benchmarks, monitoring |
| bsp-protection-pd | references/bsp-protection-pd.md | Personal data protection, consent |

## Search tools

Use `scripts/bsp_ops_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_ops_search.py method ТекущийПользователь [--src <path>]
python scripts/bsp_ops_search.py module Пользователи [--src <path>]
python scripts/bsp_ops_search.py modules-by-subsystem Пользователи [--src <path>]
python scripts/bsp_ops_search.py detect [--src <path>]
```

If `--src` is omitted, the script auto-detects the configuration
export root by searching upward for a directory containing `CommonModules/`.
If multiple candidates found, it prints them to stderr and exits with code 1.
```

- [ ] **Step 3: Write bsp_ops_search.py script**

Same structure as bsp_core_search.py but with MODULE_PREFIXES set to:
```python
MODULE_PREFIXES = [
    "Пользователи",
    "ВнешниеПользователи",
    "УправлениеДоступом",
    "РаботаСПочтовымиСообщениями",
    "ОтправкаSMS",
    "ШаблоныСообщений",
    "Обсуждения",
    "Взаимодействия",
    "БизнесПроцессыИЗадачи",
    "ЗавершениеРаботыПользователей",
    "УдалениеПомеченныхОбъектов",
    "РезервноеКопированиеИБ",
    "ОценкаПроизводительности",
    "ЦентрМониторинга",
    "ЗащитаПерсональныхДанных",
]
```
and BSP_SUBSYSTEMS:
```python
BSP_SUBSYSTEMS = [
    "Пользователи",
    "УправлениеДоступом",
    "ВнешниеПользователи",
    "РаботаСПочтовымиСообщениями",
    "ОтправкаSMS",
    "ШаблоныСообщений",
    "Обсуждения",
    "Взаимодействия",
    "БизнесПроцессыИЗадачи",
    "ЗавершениеРаботыПользователей",
    "УдалениеПомеченныхОбъектов",
    "РезервноеКопированиеИБ",
    "ОценкаПроизводительности",
    "ЦентрМониторинга",
    "ЗащитаПерсональныхДанных",
]
```

- [ ] **Step 4: Verify script runs**

```bash
python .claude/skills/bsp-ops/scripts/bsp_ops_search.py detect --src src/cf
```

Expected: prints configuration root, module counts, version.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/bsp-ops/
git commit -m "feat: add bsp-ops cluster skill with search script"
```

---

## Task 5: Migrate leaf skills to references/ (bsp-core)

**Files:**
- Create: `.claude/skills/bsp-core/references/bsp-fundamentals.md`
- Create: `.claude/skills/bsp-core/references/bsp-base-common.md`
- Create: `.claude/skills/bsp-core/references/bsp-longs-and-jobs.md`
- Create: `.claude/skills/bsp-core/references/bsp-prefixes.md`
- Create: `.claude/skills/bsp-core/references/bsp-update.md`

For each of the 5 leaf skills in bsp-core, read the current SKILL.md, apply these transformations:

1. **Remove frontmatter** (the `---` YAML block at the top)
2. **Remove `## How to explore deeper` section** and everything after it until the next `##` or end of file
3. **Remove all hardcoded repository paths** — replace references to `bsp3111_md/`, `src/cf/`, `ОбщиеМодули/` (Russian path name for the same) with generic relative path `CommonModules/` from config export root
4. **Remove the `# BSP <Name> (subsystem)` title line** if it repeats the file name — keep only section headers
5. **Add at the end** a short note: `Для поиска методов/модулей в выгрузке конфигурации используйте python scripts/bsp_core_search.py method <имя>.`

- [ ] **Step 1: Migrate bsp-fundamentals**

Read `.claude/skills/bsp-fundamentals/SKILL.md`, apply transformations, write to `.claude/skills/bsp-core/references/bsp-fundamentals.md`.

The key change beyond removing frontmatter/How to explore deeper: all references to `bsp3111_md/` and specific repo paths must be removed. The section "Где искать исходники в целевом репо" should be kept but paths should be generic (`CommonModules/<ИмяМодуля>/Ext/Module.bsl` without prefixing with a specific repo path).

- [ ] **Step 2: Migrate bsp-base-common**

Read `.claude/skills/bsp-base-common/SKILL.md`, apply transformations, write to `.claude/skills/bsp-core/references/bsp-base-common.md`.

- [ ] **Step 3: Migrate bsp-longs-and-jobs**

Read `.claude/skills/bsp-longs-and-jobs/SKILL.md`, apply transformations, write to `.claude/skills/bsp-core/references/bsp-longs-and-jobs.md`.

- [ ] **Step 4: Migrate bsp-prefixes**

Read `.claude/skills/bsp-prefixes/SKILL.md`, apply transformations, write to `.claude/skills/bsp-core/references/bsp-prefixes.md`.

- [ ] **Step 5: Migrate bsp-update**

Read `.claude/skills/bsp-update/SKILL.md`, apply transformations, write to `.claude/skills/bsp-core/references/bsp-update.md`.

Note: bsp-update has a `references/key-methods.md` file. Copy it to bsp-core/references/bsp-update-key-methods.md and update any references in the leaf .md accordingly.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/bsp-core/references/
git commit -m "feat: migrate bsp-core leaf skills to references"
```

---

## Task 6: Migrate leaf skills to references/ (bsp-data)

**Files:**
- Create: `.claude/skills/bsp-data/references/bsp-data-exchange.md`
- Create: `.claude/skills/bsp-data/references/bsp-esign-mcd.md`
- Create: `.claude/skills/bsp-data/references/bsp-contact-info.md`
- Create: `.claude/skills/bsp-data/references/bsp-classifiers.md`
- Create: `.claude/skills/bsp-data/references/bsp-currencies-banks.md`
- Create: `.claude/skills/bsp-data/references/bsp-external-components.md`

Same transformation rules as Task 5 (remove frontmatter, How to explore deeper, hardcoded paths; add search script note at end). Note about existing references/ subdirs:

- `bsp-admin-tools/references/key-methods.md` — not in this cluster (in ops)
- `bsp-esign-mcd/references/key-methods.md` — copy to `bsp-data/references/bsp-esign-mcd-key-methods.md`
- `bsp-commands-external/references/key-methods.md` — not in this cluster (in ui-forms)
- `bsp-files-and-versions/references/key-methods.md` — not in this cluster (in ui-forms)
- `bsp-update/references/key-methods.md` — already handled in Task 5

- [ ] **Step 1-6: Migrate each of the 6 leaf skills**

Apply same transformation, write to bsp-data/references/.

Search note at end: `Для поиска методов/модулей в выгрузке конфигурации используйте python scripts/bsp_data_search.py method <имя>.`

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/bsp-data/references/
git commit -m "feat: migrate bsp-data leaf skills to references"
```

---

## Task 7: Migrate leaf skills to references/ (bsp-ui-forms)

**Files:**
- Create: `.claude/skills/bsp-ui-forms/references/bsp-commands-external.md`
- Create: `.claude/skills/bsp-ui-forms/references/bsp-print-reports.md`
- Create: `.claude/skills/bsp-ui-forms/references/bsp-forms-validation.md`
- Create: `.claude/skills/bsp-ui-forms/references/bsp-multilang.md`
- Create: `.claude/skills/bsp-ui-forms/references/bsp-files-and-versions.md`
- Create: `.claude/skills/bsp-ui-forms/references/bsp-report-dedup.md`

Same transformation rules. Existing references/ files to carry over:
- `bsp-commands-external/references/key-methods.md` → `bsp-ui-forms/references/bsp-commands-external-key-methods.md`
- `bsp-files-and-versions/references/key-methods.md` → `bsp-ui-forms/references/bsp-files-and-versions-key-methods.md`

Search note: `Для поиска методов/модулей в выгрузке конфигурации используйте python scripts/bsp_ui_search.py method <имя>.`

- [ ] **Step 1-6: Migrate each of the 6 leaf skills**
- [ ] **Step 7: Commit**

```bash
git add .claude/skills/bsp-ui-forms/references/
git commit -m "feat: migrate bsp-ui-forms leaf skills to references"
```

---

## Task 8: Migrate leaf skills to references/ (bsp-ops)

**Files:**
- Create: `.claude/skills/bsp-ops/references/bsp-users-access.md`
- Create: `.claude/skills/bsp-ops/references/bsp-comms.md`
- Create: `.claude/skills/bsp-ops/references/bsp-bp-tasks.md`
- Create: `.claude/skills/bsp-ops/references/bsp-admin-tools.md`
- Create: `.claude/skills/bsp-ops/references/bsp-backup.md`
- Create: `.claude/skills/bsp-ops/references/bsp-perf-monitoring.md`
- Create: `.claude/skills/bsp-ops/references/bsp-protection-pd.md`

Same transformation rules. Existing references/ files:
- `bsp-admin-tools/references/key-methods.md` → `bsp-ops/references/bsp-admin-tools-key-methods.md`

Search note: `Для поиска методов/модулей в выгрузке конфигурации используйте python scripts/bsp_ops_search.py method <имя>.`

- [ ] **Step 1-7: Migrate each of the 7 leaf skills**
- [ ] **Step 8: Commit**

```bash
git add .claude/skills/bsp-ops/references/
git commit -m "feat: migrate bsp-ops leaf skills to references"
```

---

## Task 9: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

Remove all references to old standalone BSP skill names. Add section about 4 cluster skills. Key changes:

1. In `## Структура` → `.claude/skills/` section: replace old list with cluster descriptions
2. Remove references to individual `bsp-*` skill names from narrative text
3. Add note: BSP skills now organized as 4 cluster umbrella skills with decision-tree routing
4. Keep references to non-BSP skills (`agents-best-practices`, `opencode-runner`, `prompt-crafting-guide`)

- [ ] **Step 1: Read current AGENTS.md**
- [ ] **Step 2: Edit AGENTS.md to reference 4 cluster skills instead of 25 leaf skills**
- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md for clustered BSP skills"
```

---

## Task 10: Remove old standalone BSP skills

**Files:**
- Delete: `.claude/skills/bsp-fundamentals/` (entire directory)
- Delete: `.claude/skills/bsp-base-common/`
- Delete: `.claude/skills/bsp-long-and-jobs/`
- Delete: `.claude/skills/bsp-prefixes/`
- Delete: `.claude/skills/bsp-update/`
- Delete: `.claude/skills/bsp-data-exchange/`
- Delete: `.claude/skills/bsp-esign-mcd/`
- Delete: `.claude/skills/bsp-contact-info/`
- Delete: `.claude/skills/bsp-classifiers/`
- Delete: `.claude/skills/bsp-currencies-banks/`
- Delete: `.claude/skills/bsp-external-components/`
- Delete: `.claude/skills/bsp-commands-external/`
- Delete: `.claude/skills/bsp-print-reports/`
- Delete: `.claude/skills/bsp-forms-validation/`
- Delete: `.claude/skills/bsp-multilang/`
- Delete: `.claude/skills/bsp-files-and-versions/`
- Delete: `.claude/skills/bsp-report-dedup/`
- Delete: `.claude/skills/bsp-users-access/`
- Delete: `.claude/skills/bsp-comms/`
- Delete: `.claude/skills/bsp-bp-tasks/`
- Delete: `.claude/skills/bsp-admin-tools/`
- Delete: `.claude/skills/bsp-backup/`
- Delete: `.claude/skills/bsp-perf-monitoring/`
- Delete: `.claude/skills/bsp-protection-pd/`

All 25 old directories. Content already migrated to references/ in Tasks 5-8.

- [ ] **Step 1: Delete all 25 old standalone skill directories**

```bash
rm -rf .claude/skills/bsp-fundamentals .claude/skills/bsp-base-common .claude/skills/bsp-longs-and-jobs .claude/skills/bsp-prefixes .claude/skills/bsp-update .claude/skills/bsp-data-exchange .claude/skills/bsp-esign-mcd .claude/skills/bsp-contact-info .claude/skills/bsp-classifiers .claude/skills/bsp-currencies-banks .claude/skills/bsp-external-components .claude/skills/bsp-commands-external .claude/skills/bsp-print-reports .claude/skills/bsp-forms-validation .claude/skills/bsp-multilang .claude/skills/bsp-files-and-versions .claude/skills/bsp-report-dedup .claude/skills/bsp-users-access .claude/skills/bsp-comms .claude/skills/bsp-bp-tasks .claude/skills/bsp-admin-tools .claude/skills/bsp-backup .claude/skills/bsp-perf-monitoring .claude/skills/bsp-protection-pd
```

- [ ] **Step 2: Verify only cluster skills and non-BSP skills remain**

```bash
ls .claude/skills/
```

Expected output: `agents-best-practices  bsp-core  bsp-data  bsp-ops  bsp-ui-forms  opencode-runner  prompt-crafting-guide`

- [ ] **Step 3: Commit**

```bash
git add -A .claude/skills/
git commit -m "refactor: remove 25 standalone BSP skills, replaced by 4 cluster umbrellas"
```

---

## Task 11: Python scripts — thorough verification

Each of the 4 Python scripts must pass a full command matrix against `src/cf/`
before the migration is considered safe. Run every subcommand, check output
content, exit codes, and edge cases.

**Files:**
- Verify: `.claude/skills/bsp-core/scripts/bsp_core_search.py`
- Verify: `.claude/skills/bsp-data/scripts/bsp_data_search.py`
- Verify: `.claude/skills/bsp-ui-forms/scripts/bsp_ui_search.py`
- Verify: `.claude/skills/bsp-ops/scripts/bsp_ops_search.py`

- [ ] **Step 1: Verify bsp_core_search.py — detect**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py detect --src src/cf
```

Expected: prints "Configuration export root: src/cf" (or resolved path), non-zero "Total common modules", non-zero "Core BSP modules", version string. Exit code 0.

- [ ] **Step 2: Verify bsp_core_search.py — method (stable method)**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py method СообщитьПользователю --src src/cf
```

Expected: prints "Module: ОбщегоНазначения", "Method: СообщитьПользователю", "Region: stable". Exit code 0.

- [ ] **Step 3: Verify bsp_core_search.py — method (nonexistent)**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py method НесуществующийМетод --src src/cf
```

Expected: prints "Method 'НесуществующийМетод' not found in core BSP modules." Exit code 0.

- [ ] **Step 4: Verify bsp_core_search.py — module**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py module ОбщегоНазначения --src src/cf
```

Expected: prints "Module: ОбщегоНазначения", path to Module.bsl, list of stable API methods including СообщитьПользователю. Exit code 0.

- [ ] **Step 5: Verify bsp_core_search.py — modules-by-subsystem**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py modules-by-subsystem БазоваяФункциональность --src src/cf
```

Expected: prints list including ОбщегоНазначения modules. Exit code 0.

- [ ] **Step 6: Verify bsp_core_search.py — auto-detect --src**

```bash
cd src/cf && python ../../.claude/skills/bsp-core/scripts/bsp_core_search.py detect && cd ../..
```

Expected: auto-detects `src/cf` as root, same output as Step 1. Exit code 0.

- [ ] **Step 7: Repeat Steps 1-6 for bsp_data_search.py**

Replace method with `СформироватьПечатныеФормы` (if in data modules) or use a known data method like any ОбменДаннымиСервер export. Test module: `ОбменДаннымиСервер`. Test subsystem: `ОбменДанными`.

```bash
python .claude/skills/bsp-data/scripts/bsp_data_search.py detect --src src/cf
python .claude/skills/bsp-data/scripts/bsp_data_search.py module ОбменДаннымиСервер --src src/cf
python .claude/skills/bsp-data/scripts/bsp_data_search.py modules-by-subsystem ОбменДанными --src src/cf
```

Each must return exit code 0 with meaningful content.

- [ ] **Step 8: Repeat Steps 1-6 for bsp_ui_search.py**

Test module: `УправлениеПечатью`. Test subsystem: `Печать`. Test method: pick any export method from УправлениеПечатью visible in the script output.

```bash
python .claude/skills/bsp-ui-forms/scripts/bsp_ui_search.py detect --src src/cf
python .claude/skills/bsp-ui-forms/scripts/bsp_ui_search.py module УправлениеПечатью --src src/cf
python .claude/skills/bsp-ui-forms/scripts/bsp_ui_search.py modules-by-subsystem Печать --src src/cf
```

- [ ] **Step 9: Repeat Steps 1-6 for bsp_ops_search.py**

Test module: `Пользователи`. Test subsystem: `Пользователи`. Test method: `ТекущийПользователь`.

```bash
python .claude/skills/bsp-ops/scripts/bsp_ops_search.py detect --src src/cf
python .claude/skills/bsp-ops/scripts/bsp_ops_search.py method ТекущийПользователь --src src/cf
python .claude/skills/bsp-ops/scripts/bsp_ops_search.py module Пользователи --src src/cf
python .claude/skills/bsp-ops/scripts/bsp_ops_search.py modules-by-subsystem Пользователи --src src/cf
```

- [ ] **Step 10: Verify cross-cluster isolation — method not found**

For each script, search for a method that belongs to a DIFFERENT cluster to confirm it's correctly excluded:

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py method ТекущийПользователь --src src/cf
```

Expected: "Method 'ТекущийПользователь' not found in core BSP modules." (it's in ops, not core)

- [ ] **Step 11: Verify invalid --src gracefully errors**

```bash
python .claude/skills/bsp-core/scripts/bsp_core_search.py detect --src /nonexistent/path 2>&1; echo "Exit: $?"
```

Expected: stderr message, exit code 1.

- [ ] **Step 12: Fix any failures found, re-verify, commit fix**

If any step above fails, debug the Python script, fix the issue, re-run the failing step, then commit.

```bash
git add .claude/skills/*/scripts/
git commit -m "fix: resolve Python script issues found during verification"
```

Only if fixes were needed. Skip this step if all passed.

---

## Task 12: Cross-review — leaf migration integrity

Verify that every leaf skill was migrated correctly: no content lost, no forbidden paths remaining,
all sections preserved (except How to explore deeper), search script note added.

**Files:**
- Review: `.claude/skills/bsp-core/references/*.md`
- Review: `.claude/skills/bsp-data/references/*.md`
- Review: `.claude/skills/bsp-ui-forms/references/*.md`
- Review: `.claude/skills/bsp-ops/references/*.md`

- [ ] **Step 1: Verify no bsp3111_md references in any references/*.md**

```bash
grep -rl "bsp3111_md" .claude/skills/bsp-*/references/ || echo "PASS: no bsp3111_md references"
```

Expected: "PASS" message.

- [ ] **Step 2: Verify no src/cf references in any references/*.md**

```bash
grep -rl "src/cf" .claude/skills/bsp-*/references/ || echo "PASS: no src/cf references"
```

Expected: "PASS" message.

- [ ] **Step 3: Verify no "## How to explore deeper" section in any references/*.md**

```bash
grep -rl "How to explore deeper" .claude/skills/bsp-*/references/ || echo "PASS: no How to explore deeper sections"
```

Expected: "PASS" message.

- [ ] **Step 4: Verify no YAML frontmatter in any references/*.md**

```bash
grep -rl "^---$" .claude/skills/bsp-*/references/ | head -5
```

Expected: no files listed (no frontmatter blocks). If any found — check whether `---` is used inside a markdown table code block (acceptable) or as frontmatter delimiter (must remove).

- [ ] **Step 5: Verify search script note exists at end of every references/*.md**

```bash
for f in .claude/skills/bsp-*/references/*.md; do
  if ! grep -q "bsp_.*_search.py" "$f"; then
    echo "MISSING: $f"
  fi
done
```

Expected: no "MISSING" lines. Every file must reference its cluster's search script.

- [ ] **Step 6: Verify key sections preserved — spot-check bsp-fundamentals**

Read `.claude/skills/bsp-core/references/bsp-fundamentals.md`. Verify these sections exist:

- `## When to use`
- `## Не использовать, если`
- `## Core concepts` (with subsections: Именование общих модулей, Иерархия подсистем)
- `## Patterns`
- `## Anti-patterns`

Verify these sections do NOT exist:
- `## How to explore deeper`

- [ ] **Step 7: Verify key sections preserved — spot-check bsp-print-reports**

Read `.claude/skills/bsp-ui-forms/references/bsp-print-reports.md`. Verify sections exist:

- `## When to use`
- `## Core concepts`
- `## Key methods` (with method table)
- `## Patterns`
- `## Anti-patterns`

Verify section does NOT exist:
- `## How to explore deeper`

- [ ] **Step 8: Verify key sections preserved — spot-check bsp-users-access**

Read `.claude/skills/bsp-ops/references/bsp-users-access.md`. Verify sections exist:

- `## When to use`
- `## Core concepts`
- `## Key methods`
- `## Patterns`
- `## Anti-patterns`

- [ ] **Step 9: Verify key sections preserved — spot-check bsp-data-exchange**

Read `.claude/skills/bsp-data/references/bsp-data-exchange.md`. Verify sections exist:

- `## When to use`
- `## Core concepts`
- `## Key methods`
- `## Patterns`
- `## Anti-patterns`

- [ ] **Step 10: Compare line counts — new references vs old SKILL.md**

For each migrated leaf, verify the new references/*.md is NOT significantly shorter (>=80% of original line count) to catch accidental content loss:

```bash
for cluster in bsp-core bsp-data bsp-ui-forms bsp-ops; do
  echo "=== $cluster ==="
  for ref in .claude/skills/$cluster/references/*.md; do
    name=$(basename "$ref" .md)
    new_lines=$(wc -l < "$ref")
    echo "  $name: $new_lines lines"
  done
done
```

Expected: each file should have roughly 80-100% of its original SKILL.md line count (minus How to explore deeper and frontmatter).

- [ ] **Step 11: Fix any issues found, commit**

If any check fails, fix the issue in the affected references/*.md file and commit.

```bash
git add .claude/skills/bsp-*/references/
git commit -m "fix: resolve leaf migration issues found during cross-review"
```

Only if fixes were needed. Skip this step if all passed.

---

## Task 13: Cross-review — decision tree routing accuracy

Verify that each cluster's decision tree correctly routes representative
queries to the right leaf skill. Run simulated queries and check the output.

**Files:**
- Review: `.claude/skills/bsp-core/SKILL.md`
- Review: `.claude/skills/bsp-data/SKILL.md`
- Review: `.claude/skills/bsp-ui-forms/SKILL.md`
- Review: `.claude/skills/bsp-ops/SKILL.md`

- [ ] **Step 1: Test bsp-core routing — 5 queries**

For each query below, manually trace through the decision tree in bsp-core/SKILL.md
and confirm the expected leaf:

| Query | Expected leaf |
|-------|---------------|
| "Нужно обновить версию ИБ" | bsp-update |
| "Запустить фоновое задание" | bsp-longs-and-jobs |
| "Какой общий модуль отвечает за печать?" | bsp-fundamentals |
| "Сериализовать данные в JSON" | bsp-base-common |
| "Убрать префикс из номера документа" | bsp-prefixes |

If any query routes to wrong leaf — the decision tree triggers are incorrect. Fix SKILL.md.

- [ ] **Step 2: Test bsp-data routing — 6 queries**

| Query | Expected leaf |
|-------|---------------|
| "Зарегистрировать изменения в плане обмена" | bsp-data-exchange |
| "Подписать документ ЭЦП" | bsp-esign-mcd |
| "Получить ФИАС-код по адресу" | bsp-contact-info |
| "Посчитать рабочие дни между датами" | bsp-classifiers |
| "Получить курс валюты на дату" | bsp-currencies-banks |
| "Подключить Native API компоненту" | bsp-external-components |

- [ ] **Step 3: Test bsp-ui-forms routing — 6 queries**

| Query | Expected leaf |
|-------|---------------|
| "Добавить команду заполнения в форму" | bsp-commands-external |
| "Зарегистрировать печатную форму" | bsp-print-reports |
| "Заблокировать реквизиты объекта после записи" | bsp-forms-validation |
| "Прикрепить файл к справочнику" | bsp-files-and-versions |
| "Заполнить реквизит на нескольких языках" | bsp-multilang |
| "Найти дубли контрагентов" | bsp-report-dedup |

- [ ] **Step 4: Test bsp-ops routing — 7 queries**

| Query | Expected leaf |
|-------|---------------|
| "Проверить есть ли у пользователя роль" | bsp-users-access |
| "Отправить email по шаблону" | bsp-comms |
| "Перенаправить задачу БП другому исполнителю" | bsp-bp-tasks |
| "Удалить помеченные объекты с контролем ссылок" | bsp-admin-tools |
| "Рассчитать дату следующего автобэкапа" | bsp-backup |
| "Начать замер времени ключевой операции" | bsp-perf-monitoring |
| "Записать согласие субъекта ПДн" | bsp-protection-pd |

- [ ] **Step 5: Test cross-cluster disambiguation — tricky queries**

These queries could match multiple clusters. Verify they land in the correct one:

| Query | Expected cluster | Reason |
|-------|-----------------|--------|
| "ПодключаемыеКоманды.ПриСозданииНаСервере" | bsp-ui-forms → bsp-commands-external | commands, not core |
| "ОбщегоНазначения.СообщитьПользователю" | bsp-core → bsp-base-common | common utility |
| "РаботаСФайлами.ДобавитьФайл" | bsp-ui-forms → bsp-files-and-versions | files, not data |
| "Пользователи.ТекущийПользователь" | bsp-ops → bsp-users-access | users, not core |
| "ДлительныеОперации.ВыполнитьФункцию" | bsp-core → bsp-longs-and-jobs | background ops |

If any routes incorrectly, add/adjust trigger words in the decision tree.

- [ ] **Step 6: Fix any routing issues, commit**

```bash
git add .claude/skills/bsp-*/SKILL.md
git commit -m "fix: adjust decision tree trigger words for routing accuracy"
```

Only if fixes were needed. Skip this step if all passed.

---

## Task 14: End-to-end smoke test

Full integration test simulating the real agent workflow: cluster → leaf → API details → search script.

- [ ] **Step 1: Simulate workflow — "напечатать документ из формы"**

1. Agent sees cluster descriptions, picks **bsp-ui-forms** (trigger: "напечатать", "print")
2. Loads bsp-ui-forms/SKILL.md, decision tree routes to **bsp-print-reports** (trigger: "напечатать", "Печать")
3. Reads `references/bsp-print-reports.md` — should contain `УправлениеПечатьюКлиент.ВыполнитьКомандуПечати` in Key methods
4. Runs `python scripts/bsp_ui_search.py method ВыполнитьКомандуПечати --src src/cf` — should find the method

Verify each step completes correctly by reading the actual files and running the script.

- [ ] **Step 2: Simulate workflow — "сохранить пароль API в безопасное хранилище"**

1. Agent picks **bsp-core** (trigger: "безопасное хранилище")
2. Decision tree routes to **bsp-base-common** (trigger: "ЗаписатьДанныеВБезопасноеХранилище")
3. Reads `references/bsp-base-common.md` — should contain safe storage methods
4. Runs `python scripts/bsp_core_search.py method ЗаписатьДанныеВБезопасноеХранилище --src src/cf`

- [ ] **Step 3: Simulate workflow — "подписать документ ЭЦП и проверить МЧД"**

1. Agent picks **bsp-data** (trigger: "ЭЦП", "МЧД")
2. Decision tree routes to **bsp-esign-mcd** (trigger: "ЭлектроннаяПодпись", "МЧД")
3. Reads `references/bsp-esign-mcd.md` — should contain e-signature API
4. Runs `python scripts/bsp_data_search.py module ЭлектроннаяПодпись --src src/cf`

- [ ] **Step 4: Simulate workflow — "проверить доступ пользователя к объекту"**

1. Agent picks **bsp-ops** (trigger: "доступ", "пользователь")
2. Decision tree routes to **bsp-users-access** (trigger: "Пользователи", "УправлениеДоступом")
3. Reads `references/bsp-users-access.md` — should contain RLS/access methods
4. Runs `python scripts/bsp_ops_search.py module Пользователи --src src/cf`

- [ ] **Step 5: Verify total file integrity — all 24 leaf files exist and are non-empty**

```bash
for cluster in bsp-core bsp-data bsp-ui-forms bsp-ops; do
  for ref in .claude/skills/$cluster/references/*.md; do
    lines=$(wc -l < "$ref")
    if [ "$lines" -lt 10 ]; then
      echo "SUSPECT: $ref has only $lines lines"
    fi
  done
done
echo "Integrity check done"
```

Expected: no "SUSPECT" lines (every file > 10 lines).

- [ ] **Step 6: Verify skill count reduced**

```bash
ls .claude/skills/ | wc -l
```

Expected: 7 (4 clusters + agents-best-practices + opencode-runner + prompt-crafting-guide)

- [ ] **Step 7: Commit final state if any fixes were needed**

```bash
git add -A .claude/skills/
git commit -m "fix: final adjustments from e2e smoke test"
```

Only if fixes were needed.