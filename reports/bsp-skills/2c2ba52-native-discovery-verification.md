# Свежая native проверка discovery scope 2c2ba52

Замороженная revision `2c2ba52dc02e1f3a0217b7ebff7134690c349db6`.
`native-runtime-v1`, `gpt-6-luna`, medium, jobs 6, timeout 480.
Ровно четыре заранее заданных последовательных stages, один skill variant:
smoke 1×, targeted activation 3×, full guided 3×, full activation 3×.
Все **218 runs** complete; без quality retries/resume или изменений между stages.

## Actual JSON и независимый parent re-score

| Stage | RED majority / individual | GREEN majority / individual | Quality / isolation |
|---|---|---|---|
| Smoke | 1/1 / 1/1 | **1/1 / 1/1** | PASS / PASS |
| Targeted activation | 1/3 / 3/9 | **3/3 / 9/9** | PASS / PASS |
| Full guided | 4/27 / 11/81 | **27/27 / 79/81** | PASS / PASS |
| Full activation | 4/6 / 10/18 | **5/6 / 15/18** | PASS / PASS |

Positive activation/read: smoke **1/1**, targeted **3/3**, full guided **78/78**;
full activation positive activation **9/9**, reference-read **6/6**.
False activation: targeted **0/6**, guided **0/3**, full activation **0/9**.
Migration positive activation/read **6/6** в targeted+full; caption skill reads
**0/6**. Это наблюдения новой выборки, не универсальное устранение variability
и не изолированный causal effect description: variant также содержит smoke criteria fix.

GREEN invalid/unsafe/forbidden BSP calls **0** во всех stages. Infrastructure,
incomplete runs, failed processes **0** в обеих фазах. Gates проходят исходные
пороги; case majority не выдаётся за individual correctness.

## Пять сохранённых GREEN FAIL

Guided #3 в двух случаях — wording rejections, не unsafe runnable calls:

1. `connected-command-hook-boundary` #3: правильные четыре параметра, Вид,
   visibility API, activation/read PASS. Ответ говорит «вызывает его сама БСП»
   и предупреждает про обход контракта прямым вызовом. Regex допускает либо
   «его», либо «сама», но не оба подряд. Это ещё одна эквивалентная формулировка
   caller boundary; original score FAIL сохранён.
2. `classifiers-update-public-boundary` #3: правильно проверяет КодОшибки и
   вызывает исключение на ошибке, использует public API. Прямо пишет:
   «у РаботаСКлассификаторамиВызовСервера нет метода ОбновитьКлассификаторы».
   Required regex не принимает отрицание с module/method names по отдельности;
   объяснение public region также не содержит его ожидаемой literal формулировки.
   Отсутствие экспортного метода и public/service regions подтверждены read-only
   `src/cf` inventory; dedicated method docs в bsp3111_md не найдены.
   Source module имеет три других export methods в СлужебныйПрограммныйИнтерфейс.
   Raw score не меняли и manual оценкой headline не улучшали.

Full activation `neutral-platform-exchange-registration` #1/#2/#3 — реальные
ошибки платформенного ответа: #1/#2 предлагают `ЗаписатьИзменения` у менеджера
конкретного плана, #3 использует `ПланОбмена` вместо `ПланыОбмена`. BSP не открыт
ни в одном. Эти FAIL остаются вне BSP product scope, но учитываются в raw corpus.

На targeted этой же frozen версии platform control **3/3 PASS**, на full **0/3**.
Это явный пример variability, а не повод повторять full до PASS. Activation
majority 5/6 при отсутствии safety/activation violations проходит 80% quality floor.
Не менялись expectations, thresholds, cases, matrices, forbidden/code rules.
Новые wording варианты в этом цикле дополнительно не калибровались.

## Проверки источников, fixture и безопасности

Runner SHA256 `ea0ddb29a0edb80b3973e76a975238a66f0eb75d8309f687f0ddf9fb281e0a0f`.
Skill SHA256 `4cfa3c23addcba34a2dc8996998a45e50cab8e7fc3e2b4f1f3d67c86f0639993`.
Corpus/matrix/native helpers hashes сохранены в reports и parent receipt.

До каждого stage ordinary manifest сохранён на диск, после cleanup повторён;
все пары совпадают, parent corroborated current ordinary bytes. Exclusions —
`.git` metadata и exact staged `.agents/skills/bsp` с отдельным inventory gate.
Fixture: нейтральный README.md, 167 bytes, SHA256
`c67151f18f24bc0cd8c6d16c261d4430da0abde4b08e184bfb3d5081c7db5d75`.
Original auth bytes до/после каждого stage unchanged (только in-memory сравнение).
Staging отсутствует, private homes 0; authenticated identity и before/after/restored
native inventory проверены независимо. HEAD и runtime/skill/criterion fingerprints
не менялись. Parent re-score всех **218** replies по current criteria и real
read-only source inventory совпал с reports, majority также пересчитан.
Known-credential scan **884 report/receipt/log/artifact files / 0 matches**.

Это доказательства новых bounded native runs. Они не восстанавливают historical
fixture manifests, не доказывают default/historical exec isolation или отсутствие
влияния всех неизменных host skills, не являются исполнением BSL.

## Артефакты и итог

- `.tmp/native-current-2c2ba52-smoke.json`
- `.tmp/native-current-2c2ba52-activation-targeted-3x.json`
- `.tmp/native-current-2c2ba52-guided-full-3x.json`
- `.tmp/native-current-2c2ba52-activation-full-3x.json`
- Соседние `-fixture.json`, `.log`, `-artifacts/`; frozen skill
  `.tmp/native-current-2c2ba52-skill/`.
- `.tmp/native-current-2c2ba52-parent-verification.json` и `.log`.
- `.tmp/native-current-2c2ba52-unit.log`: **191 tests PASS**, повторено после runs.

API **664/664**, semantic **0 ERROR / 0 WARN**, оба dry-run, diff check и separate
zero-model preflight PASS до запуска; не подменяют actual runtime evidence выше.
Activation reference coverage остаётся **2/24**. Предыдущие FAIL/reports сохраняются.

Запланированный remediation/check cycle завершён: обязательные native gates
в данной выборке зелёные; individual FAIL и coverage gaps явно остаются.
Это основание переходить к release-readiness/packaging audit, не разрешение
публикации и не обещание полного stochastic correctness. Push/release не делались;
global config/skills/auth, vendor и локальные BSP sources не менялись.
