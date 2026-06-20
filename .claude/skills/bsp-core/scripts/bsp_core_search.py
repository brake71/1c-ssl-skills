#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BSP Core search: lookup methods/modules in 1C configuration export.

Covers modules: ОбщегоНазначения*, СтроковыеФункции*, ФайловаяСистема*,
ДлительныеОперации*, РегламентныеЗадания*, ОбновлениеВерсииИБ*,
ПрефиксацияОбъектов*, and StandardSubsystems subsystem modules.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Force UTF-8 output on Windows console (otherwise Cyrillic -> mojibake)
for _stream in (sys.stdout, sys.stderr):
    _reconf = getattr(_stream, "reconfigure", None)
    if _reconf is not None:
        try:
            _reconf(encoding="utf-8")
        except (TypeError, ValueError):
            pass

MODULE_PREFIXES = [
    "ОбщегоНазначения",
    "СтроковыеФункции",
    "ФайловаяСистема",
    "ДлительныеОперации",
    "РегламентныеЗадания",
    "ОбновлениеВерсииИБ",
    "ОбновлениеКонфигурации",
    "ОбновлениеИнформационнойБазы",
    "ПрефиксацияОбъектов",
]

BSP_SUBSYSTEMS = [
    "СтандартныеПодсистемы",
    "БазоваяФункциональность",
    "ОбновлениеВерсииИБ",
    "ОбновлениеКонфигурации",
    "ОбновлениеИнформационнойБазы",
    "ПрефиксацияОбъектов",
    "РегламентныеЗадания",
]


def find_src_or_exit(src_arg):
    """Return validated --src path. No auto-detect: caller must pass --src."""
    if not src_arg:
        print("Error: --src <path> is required (path to configuration export root).",
              file=sys.stderr)
        sys.exit(2)
    if not Path(src_arg).is_dir():
        print(f"Error: --src path does not exist: {src_arg}", file=sys.stderr)
        sys.exit(1)
    cm = Path(src_arg) / "CommonModules"
    if not cm.is_dir():
        print(f"Error: --src path has no CommonModules/ subdir: {src_arg}",
              file=sys.stderr)
        sys.exit(1)
    return src_arg


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
    """Parse .bsl file, return list of (method_name, is_stable, region).

    Two-pass approach:
    1. First pass: scan region markers (`#Область`/`#КонецОбласти`) with a
       stack to know the current region label for every line. Nested
       sub-regions inherit the parent's stability.
    2. Second pass: scan `Функция`/`Процедура` declarations. For each, capture
       the declaration line plus subsequent lines until we see `Экспорт`
       (export) or `КонецФункции`/`КонецПроцедуры` (non-export). This handles
       multi-line signatures where `Экспорт` is on a later line.
    """
    if not bsl_path.is_file():
        return []
    text = bsl_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    # --- Pass 1: compute region label per line ---
    region_labels = [None] * len(lines)
    stack = []  # list of label strings
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#Область"):
            name = stripped.replace("#Область", "").strip()
            if name == "ПрограммныйИнтерфейс":
                stack.append("stable")
            elif name in ("СлужебныйПрограммныйИнтерфейс",
                          "СлужебныеПроцедурыИФункции",
                          "УстаревшиеПроцедурыИФункции"):
                stack.append("unstable")
            elif name == "Переопределение":
                stack.append("override")
            else:
                # Nested sub-region inherits parent label (or None)
                stack.append(stack[-1] if stack else None)
            # This line itself is a region marker, not a method
            region_labels[i] = None
        elif stripped.startswith("#КонецОбласти"):
            if stack:
                stack.pop()
            region_labels[i] = None
        else:
            region_labels[i] = stack[-1] if stack else None

    # --- Pass 2: find export methods ---
    methods = []
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        # Skip region markers and empty lines
        if stripped.startswith("#") or not stripped:
            i += 1
            continue
        m = re.match(r"^(Функция|Процедура)\s+(\w+)\s*\(", stripped)
        if not m:
            i += 1
            continue
        sig_keyword = m.group(1)
        method_name = m.group(2)
        end_keyword = "Конец" + sig_keyword
        region = region_labels[i]

        # Accumulate signature lines until Экспорт or end keyword
        sig_text = stripped
        j = i
        is_export = "Экспорт" in stripped
        if not is_export:
            # Scan forward up to ~30 lines for Экспорт before hitting
            # КонецФункции/КонецПроцедуры (which means non-export) or
            # a new function declaration (also means non-export).
            for j2 in range(i + 1, min(i + 30, n)):
                s2 = lines[j2].strip()
                # Stop if we hit the end of this function (non-export)
                if s2 == end_keyword or s2.startswith(end_keyword):
                    j = j2
                    break
                # Stop if a new function/procedure starts — previous wasn't export.
                # IMPORTANT: check this BEFORE Экспорт, because a new function's
                # declaration line may contain Экспорт itself.
                m2 = re.match(r"^(Функция|Процедура)\s+\w+\s*\(", s2)
                if m2:
                    is_export = False
                    j = j2 - 1  # let outer loop pick up this new declaration
                    break
                # Accumulate and check for Экспорт
                sig_text += "\n" + s2
                if "Экспорт" in s2:
                    is_export = True
                    j = j2
                    break
                j = j2
        if is_export and region is not None:
            is_stable = region == "stable"
            if not only_stable or is_stable:
                methods.append((method_name, is_stable, region))
        i = j + 1
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
    # --src must be after subcommand on this Python version
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--src", required=True,
                        help="Path to configuration export root (must contain CommonModules/)")

    parser = argparse.ArgumentParser(description="BSP Core module/method search")
    sub = parser.add_subparsers(dest="command")

    p_method = sub.add_parser("method", parents=[parent], help="Find module containing export method")
    p_method.add_argument("name", help="Method name (e.g. СообщитьПользователю)")

    p_module = sub.add_parser("module", parents=[parent], help="Show module path and stable API methods")
    p_module.add_argument("name", help="Module name (e.g. ОбщегоНазначения)")

    p_subsys = sub.add_parser("modules-by-subsystem", parents=[parent], help="List core modules in subsystem")
    p_subsys.add_argument("name", help="Subsystem name (e.g. БазоваяФункциональность)")

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
