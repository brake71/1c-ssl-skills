# Следующий цикл после a728b0b: smoke wording и discovery scope

Исходное состояние `6b8584e`: runtime/skill соответствует проверенному a728b0b;
full guided 81/81, но smoke и activation quality FAIL. Релиз не публикуется.

## Диагноз из сохранённых traces, не новое выполнение

В `neutral-upgrade-safe-write` GREEN #3 нет reader commands, нет activation/read,
есть запрещённая запись объекта. В `neutral-form-caption` #3 успешно открыт
только installed SKILL.md, затем дан правильный платформенный ответ. В обоих
случаях native before/after каталог содержит enabled repo BSP с одним и тем же
metadata hash, что и успешные #1/#2. Исчезновение skill/дрейф каталога не объясняет misses.

Рабочие гипотезы discovery: слабый implicit migration pointer без BSP имени,
разрешительное «не требует чтения» для platform-only scope, недостаточно явный
pre-open precedence. Это гипотезы model-selection variance, не доказанные
детерминированные причины. Проверка AST/наличия строки в description не является
behavioral доказательством.

## Ограниченные изменения

- Smoke required pattern сохраняет прежние alternatives и добавляет только
  связь «Путь ... ключом/КлючДанных ... эти варианты не совмещают» в одной
  bounded sentence. Отдельное упоминание «не совмещают», отсутствие нужной
  пары сущностей, разрешение совмещать, double negation или другой sentence
  не удовлетворяют новой ветви.
- Verbatim fixture из native smoke a728b0b; пять paired tests. Контракт подтверждён
  по `bsp3111_md/242_сообщитьпользователю.md`, затем по public exported signature
  в read-only `src/cf`. Fixtures совпадают с оригинальной response.
- Description 780→747 decoded characters. Решение scope перед открытием,
  explicit BSP API review прежде platform exclusion; implicit migration/update
  handler с библиотечной записью даже без BSP имени/версии требует skill/scenario.
  Existing form-element properties, pure BSL и явно platform exchange ведут
  к платформенному ответу без открытия. Russian cues сохранены JSON-escaped;
  router остаётся ASCII. API ответы/методы и corpus IDs в metadata не добавлялись.
- В body только уточнён migration/update routing после version check. Absolute
  installed root, reference recovery, table и version/source boundary сохранены.

Число требований, cases/tasks, matrices, forbidden/code requirements, thresholds
не менялись. Activation reference coverage остаётся 2/24. Старые FAIL сохранены.

## RED/GREEN и replay до behavioral launch

Первый focused test run: ровно **2 FAIL** (captured smoke и discovery contract),
остальные controls PASS. После изменения **9 focused tests PASS**.
Полный suite **191 tests PASS**, API **664/664**, semantic **0 ERROR / 0 WARN**,
оба dry-run и diff check PASS. Zero-model native catalog preflight PASS —
это другой bounded профиль, не behavioral/runtime proof.

Offline replay всех **200** a728b0b replies: ровно один GREEN verdict change,
только smoke 0→1/1. Guided остаётся 81/81; activation 14/18, все реальные misses
и saved activation/reference evidence неизменны. Оригинальные reports не изменены.
Replay не доказывает влияние новой description на model selection.

Артефакты: `.tmp/routing-smoke-cycle-{red,green,unit}.log`,
`-offline-replay.json`, `-native-preflight.json` и `.log`, оба `-*-dry-run.log`.
Shipped skill candidate SHA256:
`4cfa3c23addcba34a2dc8996998a45e50cab8e7fc3e2b4f1f3d67c86f0639993`.

## Заранее заданная behavioral последовательность

После criterion/skill commit одна замороженная версия, `native-runtime-v1`,
`gpt-6-luna`, medium, jobs 6, timeout 480:

1. Smoke `message-bound-to-field`, 1×.
2. Targeted activation: library migration write, existing-element caption,
   standalone platform exchange, каждый 3×.
3. Full guided 27 cases, каждый 3×.
4. Full activation 6 cases, каждый 3×.

Все runners последовательно в прежнем external neutral consumer. Prospective
ordinary manifests до/после, source auth bytes comparison в памяти, frozen skill,
HEAD/fingerprints, authenticated inventory/restored RED, cleanup обязательны.
Infrastructure/isolation/fixture drift останавливает цикл без retry;
quality FAIL сохраняется и сам по себе не отменяет запланированные следующие stages.
Ни prompt, ни skill не меняются между stages. После — independent re-scoring,
credential scan и разбор всех FAIL. Пока новых behavioral результатов нет.
Не повторяем тот же вариант ради PASS; без push/release/global изменений/vendor edits.

Результаты frozen commit 2c2ba52: [полная native проверка discovery scope](2c2ba52-native-discovery-verification.md).
Все четыре quality/isolation gates PASS; guided 79/81, activation 15/18,
individual FAIL сохранены. Это новый behavioral evidence, отдельно от replay выше.
