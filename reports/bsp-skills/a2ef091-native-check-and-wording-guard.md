# Native a2ef091 и дополнительный false-PASS control

## Сохранённая частичная behavioral проверка a2ef091

Ревизия была заморожена на время выполнения. `native-runtime-v1`,
`gpt-6-luna`, medium, timeout 480, jobs 6. Завершены smoke 1× и guided 3×.
Activation не запущен: parent остановил последовательность после текущего
этапа из-за независимо обнаруженного дефекта нового regex, не из-за quality FAIL.

| Этап | RED majority / individual | GREEN majority / individual |
|---|---|---|
| Smoke | 0/1 / 0/1 | 1/1 / 1/1 |
| Guided | 3/27 / 11/81 | **27/27 / 78/81** |

Оба gates PASS, infra 0. Guided positive activation/reference-read **77/78**,
а не 77/81: три version-boundary runs не требуют BSP activation/reference.
Case majority activation/read 26/26; false activation 0/3 negative runs.
Проверяемые GREEN invalid/unsafe/forbidden BSP calls 0.

Три сохранённых GREEN FAIL, не калибруются в рамках этой задачи:

- `print-object-registration` #3: нет activation/reference read; неверные hook,
  передача строки вместо manager и каркас настройки печати.
- `update-safe-write-module-name` #3: правильный runnable call, но совет коллеги
  ошибочно назван верным, имя с Server-suffix не отклонено.
- `classifiers-update-public-boundary` #2: проверяет КодОшибки, но тело error branch
  содержит только комментарий, без требуемой обработки ошибки.

Файлы: `.tmp/native-current-a2ef091-smoke.json`,
`.tmp/native-current-a2ef091-guided-full-3x.json`, соседние logs/artifacts/fixture receipts.
Parent независимо сверил fingerprints, реальные scores с read-only `src/cf`
inventory, majority и native inventory. До/после ordinary fixture совпала,
source auth bytes неизменны, staging/private homes очищены. Known-credential
scan **662 files / 0 matches**. Receipt:
`.tmp/native-current-a2ef091-parent-verification.json`.

## Почему требуется отдельный commit критериев

До изменения frozen corpus read-only counterexample показал, что новая ветвь
`ошибочн...` принимает «безошибочное имя модуля» за отказ от ошибочного имени.
Теперь только новая ветвь связана с точным отвергаемым именем
`ОбновлениеИнформационнойБазыСервер` и утвердительным label после dash/colon/«это».
Отдельное «не», составные слова и warning о другом модуле эту ветвь не удовлетворяют.
Прежние альтернативы не менялись; BSP caller correction сохранён.

Eight regression tests: те же captured positives и controls плюс compound words,
отрицание и чужой module warning. На критериях a2ef091 новые controls дают
**5 failures**, на исправленных критериях все tests PASS. Общий suite:
**185 tests PASS**, API **664/664**, semantic **0 ERROR / 0 WARN**, оба dry-run
и diff check PASS. Логи `.tmp/scoring-a2ef091-guard-red.log`, `-unit.log`.

## Offline replay, отдельно от behavioral результатов

- Первоначальные 198 replies 23826f1: по-прежнему ровно два GREEN verdict changes;
  guided 79→81/81, activation 16/18 unchanged, RED unchanged. Шесть RED диагностик
  только переименовывают missing regex. Все исходные reports неизменны.
  `.tmp/scoring-a2ef091-guard-offline-replay.json`.
- Все 164 replies завершённых a2ef091 smoke/guided: **0 verdict changes**, включая
  три настоящих GREEN FAIL. `.tmp/scoring-a2ef091-guard-partial-replay.json`.

Это не новые model turns. Следующий full native run выполняется на отдельной
исправленной ревизии, потому что изменился criterion fingerprint вследствие
false-PASS control. Не повторяем a2ef091 ради PASS, не меняем skill, tasks,
матрицы, пороги или forbidden/code requirements; старые FAIL сохранены.
Пока результаты следующего smoke/full guided/full activation здесь не заявлены.
Без push/release, глобальных skill/auth изменений и изменений vendor.

Продолжение: [свежая полная native проверка a728b0b](a728b0b-native-full-verification.md).
Guided 81/81 PASS; smoke и activation quality gates FAIL. Эти результаты
сохранены отдельно и не заменяют partial a2ef091 evidence или offline replay.
