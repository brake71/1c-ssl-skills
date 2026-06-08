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
