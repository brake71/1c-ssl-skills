# Полная native проверка 23826f1

2026-10-09. Свежие независимые RED/GREEN runs, не resume/replay targeted
прогонов. Ревизия `23826f1234c4f7ee45f1af578da9e4517c42a49e` заморожена;
код, shipped skill, пороги и корпуса не менялись. Без commit/push/release.

## Профиль и результаты

`native-runtime-v1`, `gpt-6-luna`, effort `medium`, runs 3, jobs 6,
timeout 480. Guided и activation выполнялись последовательно, каждый со
своим report/private home; прежний нейтральный consumer.

| Corpus | RED majority / individual | GREEN majority / individual |
|---|---|---|
| Guided 27 × 3 | 2/27 / 9/81 | **27/27 / 79/81** |
| Activation 6 × 3 | 3/6 / 9/18 | **5/6 / 16/18** |

Оба quality/isolation gates PASS в обоих reports. Infrastructure failures 0.
GREEN проверяемые invalid/unsafe/forbidden BSP calls 0. Guided positive
activation/reference-read **78/78** (26/26 cases majority); activation positive
activation **9/9**, reference-read **6/6**, false activation negatives **0/9**.
Это результаты данной выборки, не универсальная гарантия корректности.
Первичная сводка агента ошибочно указала activation majority 6/6; parent
сверил actual JSON/individual scores: **5/6**.

- `.tmp/native-current-23826f1-guided-full-3x.json`
- `.tmp/native-current-23826f1-activation-full-3x.json`
- Соседние `-artifacts/`, `.log` и `-fixture.json`.
- Независимый receipt: `.tmp/native-current-23826f1-parent-verification.json`.
- Frozen skill: `.tmp/native-current-23826f1-skill/`.

Runner SHA256 `ea0ddb29a0edb80b3973e76a975238a66f0eb75d8309f687f0ddf9fb281e0a0f`;
skill SHA256 `b4db1c7a3362d4453883a9809bf784072f54a5ea4cb2a99649a935ca9a6e2e63`.
Corpus/matrix/native helper fingerprints сохранены в reports и parent receipt.

## Четыре сохранённых GREEN FAIL

### Два false negatives проверки формулировок в guided

1. `update-safe-write-module-name` #1. Ответ прямо говорит
   «ОбновлениеИнформационнойБазыСервер — ошибочное имя модуля» и использует
   правильный `ОбновлениеИнформационнойБазы.ЗаписатьДанные(...)`.
   Required regex принимает «невер», но не «ошибочное». Другие требования
   выполнены; source подтверждает публичный метод и отсутствие Server-suffix
   модуля. Отказ обусловлен словарём regex, не рекомендацией неверного API.
2. `connected-command-hook-boundary` #2. Ответ содержит четыре параметра
   exported hook и Вид; явно говорит «его вызывает инфраструктура БСП» и
   предупреждает, что прямой вызов обходит цикл и кэширование. Regex допускает
   «вызывает БСП», но не промежуточное «инфраструктура». Это эквивалентное
   объяснение caller boundary, не пропуск правила.

Контракты проверены по документации 3.1.11 `1794_записатьданные.md` и
`2080_приопределениикомандподключенныхкобъекту.md`, затем по экспортным
сигнатурам/регионам и исходному телу в `src/cf`. Это проверка этих утверждений,
не исполнение BSL или полная верификация всех ответов.

Scorer/corpus **не исправлены в этом прогоне**; исходные scores остаются FAIL,
headline остаётся 79/81, не 81/81. Следующая узкая калибровка требует paired
regressions и отдельного replay/behavioral evidence, без переписывания reports.

### Две настоящие платформенные ошибки

`neutral-platform-exchange-registration` #1/#3 рекомендуют `ЗаписатьИзменения`
вместо нужного механизма регистрации; #3 дополнительно пропускает менеджер
`ПланыОбмена`. В обоих BSP не активировался. Ошибки не исправлены, FAIL
сохранены. Это граница standalone platform product, не повод принудительно
включать BSP или подмешивать платформенный ответ в metadata.

## Fixture, безопасность и независимые проверки

До каждого runner на диск сохранён prospective ordinary fixture manifest,
после cleanup — повторный. Явные исключения: `.git` metadata и только exact
`.agents/skills/bsp` stage (проверяется отдельным inventory gate). Все manifests
до/после совпали: один нейтральный README.md, 167 bytes,
SHA256 `c67151f18f24bc0cd8c6d16c261d4430da0abde4b08e184bfb3d5081c7db5d75`.

Source auth bytes сравнены в памяти до/после каждого corpus: неизменны.
Staged BSP удалён, remaining private homes 0. Parent повторно вычислил
runner/skill/helpers/corpus/matrix fingerprints и isolation reasons: PASS.
Known-credential scan **798** новых report/receipt/artifact/log files: 0 совпадений.

Этот полный baseline имеет собственные prospective fixture receipts; они
не восстанавливают отсутствовавшие manifests исторических запусков.
Native inventory gate по-прежнему не является автоматическим semantic
neutrality checker обычных файлов; при resume нужна отдельная сверка fixture.

Статические проверки текущей ревизии: **177 unit tests PASS**, API **664/664**
в 24 references, semantic **0 ERROR / 0 WARN**, оба corpus dry-run и
`git diff --check` PASS. Лог: `.tmp/native-current-23826f1-unit.log`.
Исторические FAIL не изменены и не пересэмплированы. Activation reference
coverage остаётся 2/24; полнота guided corpus не превращает её в 24/24.
