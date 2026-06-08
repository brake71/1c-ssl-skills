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
