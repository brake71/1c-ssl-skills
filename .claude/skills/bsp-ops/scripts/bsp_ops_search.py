#!/usr/bin/env python3
"""BSP Operations search: lookup methods/modules in 1C configuration export.

Covers modules: Пользователи*, УправлениеДоступом*, РаботаСПочтовымиСообщениями*,
ОтправкаSMS*, ШаблоныСообщений*, Обсуждения*, Взаимодействия*,
БизнесПроцессыИЗадачи*, ЗавершениеРаботыПользователей*,
УдалениеПомеченныхОбъектов*, РезервноеКопированиеИБ*,
ОценкаПроизводительности*, ЦентрМониторинга*, ЗащитаПерсональныхДанных*,
and corresponding subsystem modules.
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

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


def auto_detect_src(start_path="."):
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
        print(f"Method '{target}' not found in Operations BSP modules.")


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
    print(f"Module '{target}' not found in Operations BSP modules.")


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
        print(f"Operations BSP modules in subsystem '{subsystem_name}':")
        for m in sorted(modules):
            print(f"  {m}")
    else:
        print(f"No Operations BSP modules found in subsystem '{subsystem_name}'.")


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
    print(f"Operations BSP modules: {bsp_count}")
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
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--src", help="Path to configuration export root (auto-detected if omitted)")

    parser = argparse.ArgumentParser(description="BSP Operations module/method search")
    sub = parser.add_subparsers(dest="command")

    p_method = sub.add_parser("method", parents=[parent], help="Find module containing export method")
    p_method.add_argument("name", help="Method name (e.g. ТекущийПользователь)")
    p_module = sub.add_parser("module", parents=[parent], help="Show module path and stable API methods")
    p_module.add_argument("name", help="Module name (e.g. Пользователи)")
    p_subsys = sub.add_parser("modules-by-subsystem", parents=[parent], help="List ops modules in subsystem")
    p_subsys.add_argument("name", help="Subsystem name (e.g. Пользователи)")
    sub.add_parser("detect", parents=[parent], help="Detect BSP version and module count")

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
