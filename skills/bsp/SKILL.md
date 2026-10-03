---
name: bsp
description: "1C:BSP 3.1.11 application development and code review. Use for BSP and its APIs even when the answer seems familiar: common modules, signatures, API regions, background/scheduled jobs, exchange, printing, files, access, upgrades, signatures/powers of attorney, multilingual code, duplicates and reference replacement. Also use for overridable hooks and public/internal/deprecated API choices. Do not use for plain 1C platform syntax unrelated to BSP. Windows: read references with native rg or Python UTF-8 stdout, not PowerShell content cmdlets/pipelines."
---

# Using 1C:BSP 3.1.11 in application code

This router is ASCII-only so that its initial read is safe even with a legacy
Windows stdout code page. The task references remain UTF-8 Russian, with exact
BSL names, signatures, regions, parameters, examples and pitfalls.

## Reading UTF-8 files on Windows

Use a native UTF-8 reader: `rg -n . -- "PATH"` reads a file; rg patterns and
`-A`/`-B`/`-C` select a section. Replace PATH with the installed file's path;
quote paths containing spaces. Alternatively, read with explicit Python UTF-8:

```bash
python -X utf8 -c "import sys; from pathlib import Path; sys.stdout.reconfigure(encoding='utf-8'); print(Path(sys.argv[1]).read_text(encoding='utf-8'))" "PATH"
```

`Get-Content -Encoding UTF8` controls input decoding, not captured stdout.
Avoid PowerShell content cmdlets and piping native readers through
`Select-String`, `Select-Object` or `Where-Object`: they may re-encode stdout.
Filter inside rg or Python instead. Apply UTF-8 reading to project files too;
do not combine a safe skill read with an unsafe README read. Do not change
global shell settings.

## Workflow

1. Select one primary reference from the task table. Add a second only for a
   genuinely cross-cutting task, such as printing in a background job.
2. Open the selected reference before answering; the router and remembered
   platform knowledge are insufficient. Locate the scenario using `rg -n`
   headings/keywords, then read its rules, signature, example and pitfalls
   with native rg context options or Python. This step is complete when the
   proposed answer is checked against that section. Read the whole file only
   if section reading is unavailable; avoid unrelated material.
3. If the user proposes a call or rule, check its original full `Module.Method`
   name and purpose. Explicitly identify any mismatch: a corrected example
   does not make the original advice correct.
4. Prefer the stable public programmatic-interface region. Internal or
   deprecated APIs require an explicit warning and no public alternative.
   Show overridable-module hooks as implementations: BSP calls them;
   application code implements them, not a direct qualified module call.
   Exact Russian region and suffix names are documented in `fundamentals.md`.
5. If a configuration XML export containing `CommonModules/` is available,
   additionally verify each recommended signature/region with `bsp_api.py`.
   Otherwise use the supplied reference and do not claim source verification.
6. Answer in the user's language: API, client/server execution context,
   minimal BSL example and important constraints. Check each full BSP call
   name and argument order against the reference or available export.
   Take application-specific object/handler names from the task or project;
   do not invent symmetric BSP methods. Discuss absent/internal/forbidden
   calls in prose or inline code, not a runnable fenced BSL example.

The skill is self-contained and needs no developer documentation or source
export. Resolve `references/` and `scripts/` relative to this installed
`SKILL.md`, not the project's working directory. `src/cf/` is only an example
export path, not a consumer project requirement.

## Task routing

| Primary task | Reference |
|---|---|
| Module suffixes, locating modules, subsystem map, stable API vs hooks | `references/fundamentals.md` |
| User messages (including binding to a field during server validation), XML/JSON, attributes by reference, secure storage, strings, dates, temporary directories | `references/base-common.md`; add `references/forms-validation.md` for additional-attribute validation |
| Background/long-running operations, progress, scheduled jobs | `references/longs-and-jobs.md` |
| Object numbering prefix, infobase prefix, data area | `references/prefixes.md` |
| Infobase upgrade/version, migration, update handler | `references/update.md` |
| Data exchange, exchange nodes, change registration | `references/data-exchange.md` |
| Electronic signatures, machine-readable powers of attorney (MCD), cryptography, DSS, signature checks | `references/esign-mcd.md` |
| Contact information, addresses, OKTMO/KLADR, address classifier | `references/contact-info.md` |
| Other classifiers, including countries | `references/classifiers.md` |
| Currencies, exchange rates, banks/accounts, work schedules/calendars | `references/currencies-banks.md` |
| External components, OData | `references/external-components.md` |
| Users, permissions, RLS, access groups/profiles | `references/users-access.md` |
| Email, SMS, message templates, discussions/interactions | `references/comms.md` |
| Business processes and tasks | `references/bp-tasks.md` |
| User-session termination, deleting marked objects, security profiles | `references/admin-tools.md` |
| Infobase backup | `references/backup.md` |
| Performance assessment, monitoring center, user activity | `references/perf-monitoring.md` |
| Personal-data protection/destruction dates, classification labels | `references/protection-pd.md` |
| Connected commands, external reports/processors | `references/commands-external.md` |
| Printing, print manager, report variants, data composition (SKD) | `references/print-reports.md` |
| Locking/unlocking form attributes, properties, change-prohibition dates | `references/forms-validation.md` |
| Files, volumes, versioning, writing a file | `references/files-and-versions.md` |
| Multilingual code, NStr, current language, localization | `references/multilang.md` |
| Duplicates, bulk modification, subordinate structure, reference replacement | `references/report-dedup.md` |

For an unmapped task, start with `fundamentals.md`. It also lists intentionally
uncovered subsystems. References are workflows, not just a searchable method
catalog: use the complete scenario, not an isolated matching name.

## Optional configuration-export verification

Replace SKILL_DIR with this installed skill directory, CF_EXPORT with the
export root containing `CommonModules/`, and MODULE/METHOD with real names.
The export is read-only and not bundled. Python UTF-8 mode keeps CLI output
readable on Windows without changing global settings.

```bash
# Signature, region, documentation, source path and line range.
python -X utf8 "SKILL_DIR/scripts/bsp_api.py" method METHOD --module MODULE --src "CF_EXPORT"

# One module's exported methods across all regions.
python -X utf8 "SKILL_DIR/scripts/bsp_api.py" module MODULE --src "CF_EXPORT"

# Modules exposing stable public API.
python -X utf8 "SKILL_DIR/scripts/bsp_api.py" modules --src "CF_EXPORT"
```

`--module` disambiguates same-named methods. `--src` is mandatory: no automatic
export discovery; missing paths or `CommonModules/` yield a nonzero exit code.
`module` includes all regions; `modules` lists stable API modules only. The
output marks hooks, internal and deprecated methods; retain these warnings.

A text search of subsystem XML can locate a common-module reference, but
assigning Catalog/Document objects to a subsystem requires parsing its
`Item` references, including nested subsystem XML, not a guessed grep match.
