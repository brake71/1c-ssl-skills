# P2: два доказанных false negative после полной P1-матрицы

**Статус:** локальная новая граница runner/activation corpus, без изменения payload `skills/bsp` и без публикации. Исторические `.tmp/p1-{guided,activation}-full-3x.json` и их raw verdicts неизменны; их full 3× gates относятся к предыдущим fingerprints. [Разбор исходных пяти FAIL](p1-full-native-3x-followup.md).

## Исправления через paired regressions

1. `other-version-api-boundary` GREEN #2: сохранён ответ из raw в `tests/fixtures/responses/p1-version-boundary.md`. Формулировка «сигнатуру из 3.1.11 нельзя считать подтверждением сигнатуры для 3.2.1» явно отказывает в переносе. Узкая дополнительная ветка `required_patterns` в `evals/activation-cases.json` принимает только отказ именно для сигнатуры 3.2.1 по данным 3.1.11; тесты отвергают утверждение «можно считать подтверждением», отрицание вместо отказа и подмену целевой версии. Не снимаются запрет на runnable transplanted API и требования активации/версии.
2. `contact-info-representation-public-boundary` GREEN #2: сохранён ответ в `tests/fixtures/responses/p1-contact-info-public.md`. Приписка «Промежуточно получать внутренние данные не нужно: этот метод возвращает готовую строку» не маркирует предшествующий публичный BSL вызов как ошибочный. `ci/run_skill_evals.py` исключает лишь узкую формулировку об отсутствии необходимости *получать внутренние данные* из проверки запрета; тесты сохраняют отрицательные контроли для реального запрета вызова этого метода, неверного `ТолькоПервая` и служебного вызова. Нельзя считать это универсальным разбором русских предупреждений.

Оба теста сначала дали RED на прежнем runner/corpus, затем GREEN на точечных правках. Повторное **локальное** оценивание старых response strings без model calls даёт PASS только двум указанным случаям; ошибочный хук, mixed-reader exit 1 и прогресс без флага по-прежнему FAIL. Это контрфактическая проверка scorer, **не** переписывание прежнего native результата.

## Проверки новой границы

- 230 unit tests PASS; API coverage **664/664**, 24/24 references; semantic ERROR/WARN **0/0**; guided и activation dry-run PASS.
- Новый native targeted RED/GREEN 1× с прежним распакованным payload v0.16, `gpt-6-luna` / medium, внешним `C:/Users/dchekmenev/Projects/bsp-native-p0-fixture-consumer`, `--bsl-src src/cf`: version boundary RED 0/1, GREEN **1/1** (`.tmp/p2-version-wording-native-1x.json`); contact-info RED 0/1, GREEN **1/1** (`.tmp/p2-contact-wording-native-1x.json`). Fixture, isolation и quality gates PASS, staged skill удалён. Это независимые новые ответы, не повтор до принятия прежних ответов.
- Версионный сценарий не требует reference-read; contact-info exact-read 1/1. Отдельные raw-артефакты лежат рядом с JSON-отчётами. Оба результата имеют новые fingerprints. На момент этого targeted-отчёта полный 3× ещё не проводили; [следующий полный прогон](p2-full-native-gate-failure.md) дал activation gate FAIL.

Следующее на момент targeted-цикла: полный guided/activation 3× и raw audit; до релиза отдельно проверить точные archives/installers и запросить разрешение на tag/push/publication. Новый full-цикл уже проведён, но activation gate FAIL — см. отчёт выше. Если задача — уменьшить реальные FAIL прогресса/хука или mixed-reader, работать с reference/router/постановкой отдельно; расширение scorer ради их принятия недопустимо.
