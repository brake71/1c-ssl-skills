# P1: полная native-матрица после добавления прогресса

**Статус:** локальный проверочный цикл на незакоммиченной границе после v0.16; не новая версия скила и не публикация. Предыдущие отчёты не пересчитывались. Использован неизменённый распакованный payload v0.16 (`.tmp/v0.16 message local tests/unpacked zip/skills/bsp`, fingerprint `9e023a29d78053c2db4b9503f4b234455344e5bf9ce81363f6b1a26faf3a496d`), а runner и activation-корпус расширены относительно кандидата.

## Входы и результаты

- `native-runtime-v1`, schema 7, `gpt-6-luna` / medium, `--runs 3 --jobs 6 --timeout 480`, индекс `--bsl-src src/cf`. Один внешний consumer: `C:/Users/dchekmenev/Projects/bsp-native-p0-fixture-consumer`; source BSP в consumer отсутствуют. Отдельные RED/GREEN 3× на двух корпусах, не объединённая метрика.
- Runner SHA-256: `3f785c9964e9eabed0502c1a296d3acdcf4ff1734638524f277167fe3a1c5552`. Guided corpus/matrix: `428f28ed502cd09fb6381db31551494446fcc5a4e068ebe06296232c62f2ae5b` / `cd0f5a6908fd0f0c0dd1c64890768633f63d2b7f2a3110cf92de53ac9192d6bb`; activation corpus/matrix: `2cacabf0bb550eed9380479c5a1bbdc25c9a5adc0afac5aa39b8dd0d84d0418f` / `65d8ac951df5e4efa27f8099c2c05059f3805603d8b69c9cb2ef929da0110cc9`. Хеши текущих runner/corpora/matrices сверены с сохранёнными отчётами.

| Корпус | RED majority | GREEN majority / individual | GREEN activation | GREEN exact-read | GREEN negatives | Gates |
|---|---:|---:|---:|---:|---:|---|
| Guided, 27 кейсов | 3/27 | **27/27 · 78/81** | 78/78 | 77/78 | 0/3 false activation | quality/fixture/isolation PASS |
| Activation, 11 кейсов | 4/11 | **11/11 · 31/33** | 24/24 | 20/21 | 0/9 false activation | quality/fixture/isolation PASS |

В guided `plain-bsl-no-bsp` — negative. В activation три negative, version-boundary требует активации, но не требует reference: поэтому знаменатели activation/read отличаются. В каждой фазе полные матрицы без infrastructure/incomplete/policy-blocked; GREEN invalid/unsafe/forbidden calls — 0. Все шесть prospective ordinary-fixture checkpoints совпали с baseline (`task.txt`); изолированные native-инвентари и cleanup PASS, staged skill после запуска отсутствует. Это проверки ответов и трасс, не компиляция BSL. RED и GREEN различаются наличием staged `bsp`, но результат не доказывает причинность каждого отдельного правила.

## Независимая проверка raw и пять GREEN FAIL

Отдельный read-only аудит сверил 162 guided и 66 activation исходов, наличие sidecar/response/stderr и количество JSONL events. При сверке его первоначальный подсчёт по одному `quality_passed` пропустил guided `nonexistent-service-module` #1; проверка по `status` и повторный разбор исправили счёт: **3** guided run-level FAIL, из них **2** с `quality_passed=false` и **1** с `reference_ok=false`. Ни один FAIL не был повторён до случайного PASS.

1. Guided `prefix-hook-not-call` #2: reference прочитан; ответ предлагает непроверенный по источнику хук `ПриЗаполненииПрефиксообразующихРеквизитов` вместо ожидаемого имени. `missing_code_patterns` не пуст; это содержательная ошибка ответа, не повод ослаблять критерий.
2. Guided `nonexistent-service-module` #1: содержательный score PASS, но `reference_read=false`. Raw `rg` перечислил **несуществующий** sibling path и правильный `bsp/references/longs-and-jobs.md` в одной команде; output содержит строки правильного файла, но **exit_code=1** из-за ошибочного пути. По действующему strict read rule смешанный exit 1 не засчитывается: 77/78, а не 78/78. Это известный путь восстановления чтения, не ошибка содержания reference.
3. Guided `contact-info-representation-public-boundary` #2: ответ содержит публичный вызов, reference прочитан, 4/4 required hits и нет invalid/unsafe; однако `executable_bsl_blocks` исключает единственный корректный fence, и `quality_passed=false`. Непосредственный suffix «Промежуточно получать внутренние данные не нужно: этот метод возвращает готовую строку» определяется как негативный контекст. Это кандидат на узкое исправление evaluator с paired positive/negative controls; raw FAIL сохранён.
4. Activation `neutral-background-progress` #1: прочитан `SKILL.md`, но вместо точного `longs-and-jobs.md` попытка обращения к ошибочному пути; в клиентском фрагменте отсутствует `ВыводитьПрогрессВыполнения = Истина`. Поэтому read и quality FAIL; #2–3 прочитали точный reference и прошли. Требование не снижать: одни `ПараметрыОжидания(...)` прогресс не включают.
5. Activation `other-version-api-boundary` #2: ответ явно ограничивает подтверждение сигнатуры 3.2.1 документацией 3.1.11 и предлагает проверить источники версии 3.2.1. Required wording regex не принимает «сигнатуру из 3.1.11 нельзя считать подтверждением сигнатуры для 3.2.1»; это кандидат на paired scorer-регрессию, а не основание задним числом исправлять raw verdict. Для кейса точный reference не обязателен.

Пункты 1–3 — три guided FAIL, пункты 4–5 — два activation FAIL. Печать 3/3 (точный `print-reports.md` прочитан); платформенный обмен 3/3 без ложной активации, вызов `ПланыОбмена` подтверждён scorer. Majority gates PASS не означают 100% отдельных запусков.

## Следующая итерация

Разделить содержательные ошибки (хук, отсутствующий флаг прогресса), mixed-reader exit 1 и два вероятных wording/context false negatives. Для каждого будущего изменения scorer сначала сохранить положительный и негативные paired tests, затем отдельный targeted RED/GREEN; не менять frozen отчёты. Если готовится новый релиз после изменения критериев или payload, потребуется новый полный native 3× на новой точной границе, проверка архивов/установщиков и отдельное разрешение на tag/push/publication.

Артефакты: `.tmp/p1-guided-full-3x.json`, `.tmp/p1-guided-full-3x-artifacts/`, `.tmp/p1-activation-full-3x.json`, `.tmp/p1-activation-full-3x-artifacts/`. Не поставляются в скиле.
