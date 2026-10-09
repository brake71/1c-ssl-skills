# Свежая полная native проверка a728b0b

Замороженная runtime/criterion ревизия:
`a728b0b0ba3683bba73e0ed7242afad11bdbe0f6`. Это новая behavioral выборка,
не offline replay и не повтор a2ef091 ради PASS. Причина новой ревизии —
доказанный compound-word/unrelated-warning false PASS; guard был проверен
paired regressions до запуска. Shipped skill, prompts/tasks, матрицы,
пороги и forbidden/code requirements не менялись.

Профиль `native-runtime-v1`, `gpt-6-luna`, effort medium, jobs 6, timeout 480.
Последовательно: smoke 1×, guided 3×, activation 3×. Все **200 model runs**
завершены; quality FAIL не пересэмплировались. Gate FAIL в smoke не блокировал
следующие корпусы, поскольку infrastructure/fixture/isolation failures отсутствовали.

## Реальные результаты JSON, независимо проверенные parent

| Этап | RED majority / individual | GREEN majority / individual | Quality | Isolation |
|---|---|---|---|---|
| Smoke | 0/1 / 0/1 | **0/1 / 0/1** | FAIL | PASS |
| Guided | 2/27 / 7/81 | **27/27 / 81/81** | PASS | PASS |
| Activation | 3/6 / 10/18 | **5/6 / 14/18** | FAIL | PASS |

GREEN guided positive activation/read **78/78**, case majority **26/26**;
negative false activation **0/3**. Activation positive activation **8/9**,
reference-read **5/6**; case majority соответственно **3/3** и **2/2**.
Negative false activation **1/9**, только `neutral-form-caption` #3.
Standalone platform exchange activation **0/3**, включая #1: первичная
сводка агента ошибочно назвала его activated. Runs 3/3 не заменяются case majority.

Infrastructure, incomplete runs и failed processes **0** во всех фазах.
GREEN guided invalid/unsafe/forbidden **0**; activation invalid/unsafe **0**,
forbidden hits **1**. Поэтому activation quality gate FAIL, несмотря на
case pass rate 5/6 (выше 80% floor). Smoke gate FAIL из-за 0/1 pass rate.

## Пять сохранённых GREEN FAIL

1. Smoke `message-bound-to-field` #1: activation/read PASS, API/code PASS;
   единственный missing pattern — `(?:одновременно|конфликт)`. Ответ объясняет,
   что ключ и путь задают «конкурирующий способ адресации» и «эти варианты не
   совмещают». Это ещё один wording false negative, не отсутствие объяснения.
   Сверены task, `bsp3111_md/242_сообщитьпользователю.md`, затем public exported
   signature `ОбщегоНазначения` в read-only `src/cf`. Новую ветвь в критерий
   **не добавляли**, raw score/gate остаются FAIL; следующий отдельный фикс
   требует paired negatives, а не простого расширения словаря без context.
2. Activation `neutral-upgrade-safe-write` #3: skill/reference не прочитаны.
   Предлагает выдуманную структуру параметров и forbidden runnable
   `ДокументОбъект.Записать(ПараметрыЗаписи)` вместо безопасного BSP wrapper.
   Реальный activation/quality failure; это причина forbidden_hits=1 и gate FAIL.
3. Activation `neutral-platform-exchange-registration` #2: неверный
   `ПланыОбмена.ЗаписатьИзменения` вместо регистрации изменений.
4. Тот же case #3: неверный `ОбменДанными.ЗаписатьИзменения`; пропущен
   требуемый manager. В обоих BSP не активировался. Платформенные ошибки
   сохраняются отдельно от BSP product scope, не исправляются injection/forced activation.
5. Activation `neutral-form-caption` #3: прочитан installed BSP SKILL.md,
   reference не читался. Платформенный runnable ответ правильный, но задача
   вне BSP scope: реальная false activation по принятому read-evidence контракту.

Два первоначальных wording fixes verified регрессиями и offline replay;
исправленный guided corpus в этой свежей выборке полностью PASS. Это не
устраняет stochastic routing/quality misses и не доказывает всех implicit задач.
Итог всей behavioral проверки **не зелёный**, release-ready утверждение не делается.

## Fingerprints, fixture и безопасность

Runner SHA256 `ea0ddb29a0edb80b3973e76a975238a66f0eb75d8309f687f0ddf9fb281e0a0f`.
Skill SHA256 `b4db1c7a3362d4453883a9809bf784072f54a5ea4cb2a99649a935ca9a6e2e63`.
Guided corpus SHA256 `75c6e4c572a6108845415ba0e7dd0510f635525a9fc9ffef71263779c33bd170`.
Matrices и native helpers hashes сохранены в reports/parent receipt.

До каждого runner prospective ordinary-file manifest сохранён на диск,
после cleanup повторён. Все пары совпали; явные исключения `.git` metadata
и только exact staged `.agents/skills/bsp` (отдельный inventory gate).
Обычный fixture — один нейтральный README.md, 167 bytes, SHA256
`c67151f18f24bc0cd8c6d16c261d4430da0abde4b08e184bfb3d5081c7db5d75`.
Parent повторно сверил текущие ordinary bytes с after manifest.
Source auth bytes до/после каждого этапа неизменны (сравнение только в памяти).
Staging отсутствует, private homes 0. Native inventory и authenticated identity
проверены независимо; runtime/criterion fingerprints совпали с замороженной ревизией.

Parent заново вычислил все 200 actual scores по текущим criteria и реальному
read-only BSP source inventory; они совпадают с reports. Majority также пересчитан.
Known-credential scan **809 report/receipt/artifact/log files / 0 matches**.
Это bounded native/fixture доказательства данных запусков, не восстановление
historical manifests, не доказательство исторического/default exec isolation,
не автоматический neutrality gate ordinary файлов и не исполнение BSL.

## Артефакты и статика

- `.tmp/native-current-a728b0b-smoke.json`
- `.tmp/native-current-a728b0b-guided-full-3x.json`
- `.tmp/native-current-a728b0b-activation-full-3x.json`
- Соседние `-artifacts/`, `.log`, `-fixture.json`; frozen skill
  `.tmp/native-current-a728b0b-skill/`.
- `.tmp/native-current-a728b0b-parent-verification.json` и `.log`.
- `.tmp/native-current-a728b0b-unit.log`: **185 tests PASS**, повторено после runs.

API **664/664**, semantic **0 ERROR / 0 WARN**, оба dry-run и diff check PASS
перед criterion commit; runtime/skill/criteria после запуска не менялись.
Activation reference coverage всё ещё **2/24**. Исторические и a2ef091 FAIL
сохранены; quality retries/resume не делались. Без push/release, без global
skill/auth изменений, без изменений user-owned vendor или локальных BSP sources.
