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

## Cross-cluster routing

UI/forms subsystems overlap with other clusters:

| Trigger | Go to |
|---------|-------|
| sign a printed form with ЭП, attach file to exchange message | `bsp-data` |
| user who owns the print command, access to external report, RLS on file | `bsp-ops` |
| safe storage of report credentials, message-to-user from a print handler, common serialization | `bsp-core` → `bsp-base-common` |
| run heavy print / report generation in background (`ДлительныеОперации`) | `bsp-core` → `bsp-longs-and-jobs` |

**Ambiguous keywords** (first match wins, but consider both clusters):

- `Файл` (file) in a *versioning* context → stay here (`bsp-files-and-versions`).
  `Файл` in an *exchange attachment* context → `bsp-data` → `bsp-data-exchange`.
  `Файл` in a *user-attached* context (avatar, signature scan) → check
  `bsp-ops` → `bsp-users-access` or stay, depending on which module owns it.
- `Команда` (command) connected-command context → stay here
  (`bsp-commands-external`). `Команда` in a `РегламентныеЗадания` context →
  `bsp-core` → `bsp-longs-and-jobs`. Different concepts despite the word.
- `Версия` (version) of an object → stay here (`bsp-files-and-versions`).
  `Версия` of the configuration / infobase → `bsp-core` → `bsp-update`.
- `Свойства` (properties) form-property context → stay here
  (`bsp-forms-validation`). `Свойства` of a contact info / address →
  `bsp-data` → `bsp-contact-info`.

If no trigger matches, fall back to `bsp-fundamentals` and locate the
subsystem by the module map.

## Search tools

Use `scripts/bsp_ui_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_ui_search.py method СоздатьКоллекциюКомандПечати --src <path/to/cf>
python scripts/bsp_ui_search.py module УправлениеПечатью --src <path/to/cf>
python scripts/bsp_ui_search.py modules-by-subsystem Печать --src <path/to/cf>
python scripts/bsp_ui_search.py detect --src <path/to/cf>
```

`--src <path>` is **required**: path to the configuration export root
(directory containing `CommonModules/`). No auto-detection — the agent
must pass the path explicitly. If the path is invalid or has no
`CommonModules/` subdir, the script exits with a non-zero code.
