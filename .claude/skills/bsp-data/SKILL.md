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

## Cross-cluster routing

Data subsystems have natural overlaps with other clusters. If the task
fits another cluster better, load that umbrella:

| Trigger | Go to |
|---------|-------|
| print a data document, attach file to exchange message, form validation on a data object | `bsp-ui-forms` |
| user who owns the data, RLS on exchange node, access to classifier | `bsp-ops` |
| safe storage of exchange credentials, message-to-user from exchange, common serialization | `bsp-core` → `bsp-base-common` |
| run heavy exchange in background (`ДлительныеОперации`) | `bsp-core` → `bsp-longs-and-jobs` |

**Ambiguous keywords** (first match wins, but consider both clusters):

- `phone` / `email` in a *contact-info* context → stay here (`bsp-contact-info`).
  `phone` / `email` in a *send message* context → `bsp-ops` → `bsp-comms`.
  If the task is «store a phone number for a counterparty», stay; if it is
  «send SMS to the counterparty», go to `bsp-ops`.
- `Подпись` (signature) on an exchange message → `bsp-esign-mcd` (here, data
  cluster). `Подпись` on a printed form / outgoing document → check
  `bsp-ui-forms` → `bsp-print-reports` first.
- `Валюты` / `Банки` (here) vs `Организации` (which is referenced from
  `bsp-currencies-banks` but lives in a separate subsystem not covered by
  any cluster): if the task is «read currency rate», stay; if it is
  «find organisation's bank account», still here, but note `Организации`
  module is not in any current leaf skill — use `bsp-fundamentals` map.

If no trigger matches, fall back to `bsp-fundamentals` and locate the
subsystem by the module map.

## Search tools

Use `scripts/bsp_data_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_data_search.py method УзелПланаОбменаПоКоду --src <path/to/cf>
python scripts/bsp_data_search.py module ОбменДаннымиСервер --src <path/to/cf>
python scripts/bsp_data_search.py modules-by-subsystem ОбменДанными --src <path/to/cf>
python scripts/bsp_data_search.py detect --src <path/to/cf>
```

`--src <path>` is **required**: path to the configuration export root
(directory containing `CommonModules/`). No auto-detection — the agent
must pass the path explicitly. If the path is invalid or has no
`CommonModules/` subdir, the script exits with a non-zero code.
