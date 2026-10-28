# P5: `gpt-6-sol` full native 3× после уточнения прогресса и восстановления лимита

**Статус:** локально проверенная матрица на текущем **рабочем дереве**, не проверка упакованного релизного payload и не публикация. Предыдущие raw FAIL и предыдущие fingerprints сохранены. Внутри одной матрицы модель/effort, consumer, runner, corpus и payload фиксированы; результаты `gpt-6-luna` и `gpt-6-sol` не смешиваются.

## Новая граница

- Предыдущий [модельный диагностический цикл](p4-platform-only-model-diagnosis.md) с тем же prompt показал RED/GREEN platform-only 3/3, но progress 0/3 в полной activation. Из трёх прогресс-ответов два не содержали BSL-директиву `&НаКлиенте` в клиентском fence (реальный пробел); третий содержал клиентский обработчик, но показывал **фрагмент внутри уже выполняемой серверной функции** без объявления `Функция ... Экспорт`. Пользовательская задача прямо просит фрагмент, поэтому требование полной оболочки было доказанным false negative для третьего ответа; старый verdict не переписывался.
- `tests/fixtures/responses/p4-progress-server-fragment.md` сохраняет raw-эквивалент; paired-тест в `tests/test_activation_expansion.py` сначала дал RED, затем GREEN. Оценщик принимает серверный фрагмент **только** с прилегающей меткой «внутри/в теле [выполняемой (в фоне)] серверной функции», с исполняемым вызовом в отдельном fence без `&НаКлиенте` и `ДлительныеОперацииКлиент.*`; второй fence всё равно обязан содержать `&НаКлиенте`, включённый флаг и ожидание. Негативные контроли не допускают клиентский прогресс, ложный флаг, отсутствие метки/клиентской директивы. Это ограниченное распознавание фрагмента, не анализ произвольного BSL.
- В `skills/bsp/references/longs-and-jobs.md` рядом с уже имевшимся примером добавлено прикладное правило: в клиентском фрагменте показывать `&НаКлиенте`, поскольку пояснение вне кода не задаёт контекст. Источниковые API-сигнатуры и пороги не менялись.
- Точечный sol/native прогон до последней правки reference (`.tmp/p4-progress-fragment-sol-native-1x.json`) сохранил GREEN FAIL: оба контекстных требования не выполнены; отсутствие клиентской директивы не смягчено. На новых точных байтах (`.tmp/p5-progress-context-sol-native-1x.json`) RED 0/1, GREEN **1/1** с обоими fences, activation/read и fixture/isolation PASS; это один результат, не доказательство причинности.

## Замороженные входы и итог

`native-runtime-v1` schema 7; `gpt-6-sol`, medium; `--runs 3 --jobs 6 --timeout 480`, `--bsl-src src/cf`, `--skill skills/bsp` (не архив). Consumer `C:/Users/dchekmenev/Projects/bsp-native-p0-fixture-consumer`. Skill fingerprint `a531b00ada743f832e159868c669c6d68ff120f2d0c4f0269141fca68e51d6`; runner SHA-256 `4098fc0d3508910f12b84b842979a5497e36eeb9c401bc2515cf1e8bc8b04ad8`. Guided и activation corpus/matrix — раздельные, их SHA-256 и требуемые reference-пути хранятся в JSON-отчётах.

| Корпус | RED majority | GREEN majority / individual | GREEN activation | GREEN exact-read | Negatives | Quality / fixture / isolation |
|---|---:|---:|---:|---:|---:|---|
| Guided, 27 кейсов | 9/27 | **27/27 · 80/81** | 78/78 | 78/78 | 0/3 false activation | **PASS / PASS / PASS** |
| Activation, 11 кейсов | 4/11 | **11/11 · 32/33** | 23/24 (8/8 majority) | 21/21 | 0/9 false activation | **PASS / PASS / PASS** |

Прогресс GREEN **3/3**, platform-only **3/3** без BSP activation; public/service boundary **3/3**. GREEN invalid/unsafe/forbidden calls 0, infrastructure/incomplete 0. Ответы не исполнялись/не компилировались в 1С. Обобщать по этой малой стохастической выборке или выводить причинный эффект изменения reference нельзя.

### Guided `--resume` без quality retry

Первый запуск `.tmp/p5-guided-sol-full-3x.json` был **complete=false и gate FAIL**: RED 2 случая `tool_output_encoding`, GREEN 63 `process_error` после внешнего usage limit. Оригинальный частичный FAIL не объявлялся PASS. После сообщения о восстановлении лимитов `--resume` с прежними параметрами заново запросил **ровно 65 инфраструктурных** слотов. Изначально завершённые RED 79 (29 PASS, 50 quality FAIL) и GREEN 18 не были заново отправлены модели; такие слоты runner сохраняет штатно. Финальный отчёт complete=true и gates PASS. Исходный JSON до resume отдельно не копировался и побайтное сравнение всех этих 97 записей задним числом невозможно; транскрипт запуска и итоговый `resumed_at` фиксируют факт восстановления. Quality FAIL в финальном результате не переигрывались.

### Два individual GREEN FAIL в итоговой паре корпусов

1. Guided `save-attached-file-public-boundary` #2: activation/read PASS, ответ использует `РаботаСФайлами.ДвоичныеДанныеФайла(ПрисоединенныйФайл, Ложь)`, проверяет `Если Данные = Неопределено Тогда Возврат Ложь`, записывает в серверный путь и отвергает служебный метод. Required code regex принимает имена `ДвоичныеДанные` и `ДанныеФайла`, но не `Данные` при той же безопасной проверке. Это **кандидат на false negative scorer**, не пересчитанный raw PASS. Нужны paired positive/negative controls, подтверждение связки присваивания/проверки и отдельная проверочная граница; не расширять regex только по слову `Данные` без связи с вызовом.
2. Activation `other-version-api-boundary` #1: ответ отказывает в подтверждении сигнатуры 3.2.1 на основе 3.1.11 (quality PASS), но **не активирует BSP**; сценарий требует activation для распознавания границы версий (reference не требуется). #2–3 активировали скил. Статус #1 остаётся FAIL, а 8/8 majority не означает 24/24 individual.

## Независимая проверка сохранённых raw

Для обеих матриц повторно, без model calls, проверены hashes текущих runner/skill/corpora/matrices, шесть ordinary-fixture checkpoints, отсутствие staged skill, полнота 3 запусков на кейс, JSONL syntax, native sidecars и совпадение сохранённых ответов. Replay `score_response` и exact skill/reference-read evidence по JSONL дал **0 расхождений** с 162 guided и 66 activation записями. Найдены 648/648 guided и 264/264 activation ожидаемых файлов артефактов. Самостоятельная проверка не заменяет платформенную компиляцию и не проверяет неизвестные секреты.

**Static:** 232 unit tests PASS; API 664/664, 24/24 references; semantic ERROR/WARN 0/0; оба dry-run PASS. `vendor/agents-best-practices` не изменялся.

## Дальше

Эта матрица пройдена **только для текущих байтов рабочего дерева** и `gpt-6-sol`. Следующая техническая работа — paired проверка возможного false negative в guided `save-attached-file-public-boundary`; при правке scorer понадобится новая frozen граница и новый full 3×, текущие raw verdicts не пересчитывать. Для релизной готовности отдельно проверить **точный упакованный payload**, оба установщика и native матрицы извлечённого архива; подготовка локального кандидата не означает разрешение на tag/push/release. Не переносить результаты на `gpt-6-luna`.

Артефакты: `.tmp/p5-activation-sol-full-3x.json` и `-artifacts/`; `.tmp/p5-guided-sol-full-3x.json` и `-artifacts/`. Парные исторические `.tmp/p4-*-sol-*.json` сохранены отдельно.
