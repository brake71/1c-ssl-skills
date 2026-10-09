# Калибровка двух false negatives после полного native 23826f1

## Изменение критериев

В `evals/cases.json` изменены только две `required_patterns`:

- `update-safe-write-module-name`: принимается «ошибочное имя/название
  [общего] модуля», не любое упоминание ошибки.
- `connected-command-hook-boundary`: принимается «вызывает инфраструктура
  БСП/BSP», не инфраструктура вообще без BSP caller.

Число обязательных требований, code patterns, forbidden patterns, пороги,
case IDs/tasks, routing, references, activation corpus и матрицы не менялись.
Поскольку сценарии не добавлялись и не переносились, matrix изменений не требует.
Shipped skill SHA256 остаётся
`b4db1c7a3362d4453883a9809bf784072f54a5ea4cb2a99649a935ca9a6e2e63`.

Две дословные сохранённые responses: `tests/fixtures/responses/native-full-23826f1.json`.
Семь paired regression tests: `tests/test_full_native_response_scoring.py`.
До изменения критериев обе положительные fixtures FAIL, отрицательные controls
PASS; после — все семь tests PASS. Controls сохраняют отказы при ошибке записи
вместо неверного имени модуля, упоминании неверного имени метода/другого модуля,
неверном recommended call, не-BSP caller, direct hook call, неверном skeleton,
пропущенных activation/reference read.

## Offline replay — не новые model turns

Оригинальные reports 23826f1 не изменены. Все **198** старых scores
воспроизведены с прежними критериями и реальным read-only `src/cf` inventory.
Новые критерии меняют **ровно два verdicts**, оба GREEN guided false negatives:

| Corpus | RED individual | GREEN до → после | Majority GREEN |
|---|---:|---:|---:|
| Guided | 9/81 → 9/81 | 79/81 → **81/81** | 27/27 → 27/27 |
| Activation | 9/18 → 9/18 | 16/18 → **16/18** | 5/6 → 5/6 |

Дополнительно в шести RED scores заменён только текст regex в `missing_patterns`;
число hits, доли и verdicts там неизменны. Реальные платформенные FAIL сохранены.
Replay: `.tmp/scoring-23826f1-offline-replay.json`; исходные hashes сохранены
в этом receipt. Replay не является свежей behavioral проверкой.

## Проверки перед commit

**184 unit tests PASS**, API **664/664**, semantic **0 ERROR / 0 WARN**,
оба corpus dry-run, `git diff --check` PASS. Логи:
`.tmp/scoring-23826f1-red.log`, `-green.log`, `-unit.log`,
`-guided-dry-run.log`, `-activation-dry-run.log`.

Свежие smoke и полные native RED/GREEN корпуса запускаются после commit;
их результаты здесь пока не заявлены. Без quality retries/resume, без
переписывания старых reports, без push/release или изменения vendor.
