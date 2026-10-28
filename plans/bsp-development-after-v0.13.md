# Развитие единого скила `bsp` после локального кандидата v0.16

**Статус:** действующий план после локально проверенного v0.16 на frozen
`5f9aefe`. Тег/push/релиз v0.16 не создавались. Имя файла сохранено для ссылок.
Публикация и проверка скачанных assets — отдельный этап с отдельным разрешением.

## Историческая отправная точка v0.15

- Поставляется **один** `skills/bsp/`: короткий маршрутизатор, 24 тематических
  `references/`, скрипт `scripts/bsp_api.py`. Сторонние `.agents/skills/`
  нужны разработчикам Pi, не входят в релиз и не являются источником API БСП.
- Поставляемые пути `skills/bsp`, `install.sh`, `install.ps1` на теге v0.15
  не отличаются от проверенного кандидата `7b1abc7`. ZIP/tar.gz кандидата
  собраны дважды побайтно одинаково; проверены оба упакованных установщика,
  обновления и безопасные отказы без сети и без глобальных назначений.
- По [отчёту кандидата](../reports/bsp-skills/7b1abc7-release-candidate-readiness.md):
  191 unit tests PASS, API coverage 664/664, 24/24 references,
  semantic ERROR/WARN 0/0. Совпадение сигнатуры и региона не доказывает
  поведение метода и не является компиляцией или исполнением BSL.
- Свежие native-прогоны распакованного ZIP: smoke 1/1; guided **27/27 majority,
  78/81 individual**; activation **6/6 majority, 18/18 individual**.
  Quality/overall и isolation gates PASS, проверяемых invalid/unsafe/forbidden
  BSP calls и infrastructure failures нет. Это результаты отдельных корпусов;
  их нельзя складывать в один показатель качества.
- Guided strict reference-read — **76/78** положительных запусков, activation
  positive/read — **9/9 и 6/6**, false activation — **0/3 и 0/9** соответственно
  в guided/activation negatives. Три guided FAIL сохранены. Эти результаты
  одной выборки не доказывают отсутствие будущих stochastic ошибок.
- Самостоятельная активация покрывает **2/24 references** (`base-common.md`,
  `update.md`), а не все 24: API coverage и behavioral coverage — разные вещи.
  Корпус и матрица: `evals/activation-cases.json` и
  `evals/activation-reference-matrix.json`.

История исправлений и исходные FAIL остаются в отчётах:
[scope-before-open](../reports/bsp-skills/2c2ba52-native-discovery-verification.md),
[reference recovery](../reports/bsp-skills/p3-reference-recovery-after-p2.md),
[native runtime](../reports/bsp-skills/p0-native-runtime-loop-after-v0.14.md).
Новые PASS не меняют исторические результаты и не доказывают причинного
улучшения относительно другого профиля, модели или evaluator.

## Текущее состояние v0.16

[Полная проверка кандидата](../reports/bsp-skills/v0.16-release-candidate-readiness.md):
217 tests PASS, API 664/664, semantic 0/0; точные архивы и оба упакованных
установщика PASS. Свежий guided **27/27 majority, 81/81 individual**,
activation **10/10, 28/30**, все итоговые quality/isolation gates PASS.
Guided activation/read **78/78**, activation positive/allrefs-read **21/21
и 18/18**, false activation **0/3 и 0/9**. Один capacity failure восстановлен
в отдельной копии, 59 завершённых результатов и оба quality FAIL сохранены.
Это не публикация и не причинный эксперимент по одному изменению.

Первая P1-партия выполнена: **5/24 references**, 10 сценариев, сквозной
allrefs-read, согласованная матрица. P3 evidence-пилот выполнен для этих
рискованных правил, не для всех API. Источники и исходные FAIL доступны
в [evidence-пилоте](../reports/bsp-skills/v0.16-activation-source-check.md)
и связанных отчётах кандидата.

## Приоритеты и ближайшая итерация

| Приоритет | Статус после локального v0.16 | Следующий результат |
|---|---|---|
| P0 — воспроизводимость | Штатный manifest/resume-контроль в рабочем дереве; guided и activation native 3×: fixture/isolation PASS | Сохранить prospective контроль на следующей границе |
| P1 — покрытие поведения | 11 кейсов, 6/24 references; на текущей границе `gpt-6-sol` progress 3/3, activation 11/11 majority | Не переносить результат на другие модели и все 24 темы |
| P2 — отказы качества | Текущие sol activation 32/33, guided 80/81; оба gates PASS; два individual FAIL сохранены | Разобрать guard attached-file с paired controls, не переписывать FAIL |
| P3 — авторинг | Evidence-пилот выполнен; клиентский контекст прогресса уточнён | Проверять источники следующих выбранных правил |
| P4 — устойчивость и релиз | Один native sol 3× на рабочем дереве прошёл, но точный архив/установщики не проверены | Frozen packaging и прогоны извлечённого payload; публикация только по разрешению |

**Текущая итерация — удержать проверенную sol-границу, разобрать оставшийся guided false negative до релизной упаковки.**

1. Штатные ordinary manifests уже встроены в native runner/resume (schema 7):
   исключаются `.git` и точный staged BSP, а изменение fixture блокирует
   продолжение. Unit-регрессии покрывают успешный resume и изменения до/после
   фаз и cleanup. Первый пробный native 1× под системным `Temp` дал fixture/
   isolation PASS, но GREEN quality FAIL: raw-команды чтения consumer завершились
   `os error 5` и скил не был прочитан. Результат сохранён, не переоценён.
   Отдельный новый targeted native 1× в доступном Git-корне дал GREEN quality,
   fixture и isolation PASS. Отчёты schema 6 без baseline нельзя возобновлять.
2. Два activation FAIL разобраны по raw evidence. Точная print-формулировка
   теперь принимается узким дополнительным критерием с отрицательными
   контролями; новый targeted native RED/GREEN 1× PASS. Отдельный платформенный
   ответ с `РегистрацияИзменений` остаётся FAIL: нужен `ПланыОбмена`, отсутствие
   BSP activation не исправляет неверный механизм. Исторические FAIL сохранены;
   на новой полной матрице печать и платформенный обмен прошли 3/3 каждый.
3. Первая новая P1-тема `longs-and-jobs.md` уже добавлена после проверки
   документации 3.1.11 и исходников: два контекста прогресса, paired controls,
   indexed targeted native 1× PASS; корпус/матрица теперь 11 кейсов, 6/24.
   См. [evidence и границы](../reports/bsp-skills/p1-progress-activation-followup.md).
   Следующую тему (`classifiers.md`, `data-exchange.md` или `esign-mcd.md`)
   брать только после оценки отдельного риска, а не для роста числа файлов.
4. Prompts не раскрывают skill paths; корпус и матрица обновляются вместе.
   Сохранять прежние negatives/version boundary, проверять каждый declared
   reference сквозной задачи. Не размножать кейсы ради числа файлов.
5. На новой frozen границе static/dry-run и полные guided/activation native 3×
   на точном извлечённом payload прошли по итоговым gates; prospective manifests
   и raw audit проверены. Guided individual **78/81**, exact-read **77/78**;
   activation individual **31/33**, exact-read **20/21**. Причины пяти FAIL
   и raw evidence: [новый отчёт](../reports/bsp-skills/p1-full-native-3x-followup.md).
   С тех пор scorer и version criterion изменены: два false negative закрыты
   paired tests и targeted native 1×. Новый полный guided 3× дал 81/81, а
   activation 3× — 28/33 и **gate FAIL** по strict read 6/7: нейтральный
   public/service кейс не активировал скил 2/3. Пять новых individual FAIL
   сохранены без retry. [Новый raw-отчёт](../reports/bsp-skills/p2-full-native-gate-failure.md).
   Старый полный 3× остаётся самостоятельным историческим baseline.
6. На следующей границе дополнено описание `SKILL.md`: нейтральный
   exported/common-module service review явно ведёт в `fundamentals.md`,
   platform-only остаётся вне активации. Static и парные targeted 1× PASS;
   новый полный activation 3× — **11/11 majority, 31/33 individual**, positive
   activation/read **24/24 и 21/21**, false activation **0/9**, но **GREEN gate
   FAIL**: платформа без активации BSP предложила запрещённый
   `ОбменДанными.ЗарегистрироватьИзменения(...)` в одном запуске. Второй FAIL —
   RLS-отказ при успешном чтении двух reference. Guided full 3× на новых
   байтах **не проводился**. Исходные FAIL и [отчёт](../reports/bsp-skills/p3-neutral-api-scope-activation-followup.md)
   сохранены; повторять quality slots ради PASS нельзя.
7. Платформенную ошибку проверили отдельно на `gpt-6-sol`: platform-only
   RED/GREEN по 3/3, без BSP activation, но первый sol full activation имел
   progress 0/3. После paired scorer-регрессии для серверного фрагмента и
   уточнения клиентского контекста в `longs-and-jobs.md` новая **frozen sol**
   матрица на рабочем дереве: activation **11/11 majority, 32/33 individual**,
   progress/platform по **3/3**; guided после штатного `--resume` только 65
   infrastructure слотов **27/27, 80/81 individual**. Оба quality/fixture/
   isolation gates PASS, raw replay 228/228. Два individual FAIL сохранены:
   version-boundary без активации и attached-file guard с иным именем
   переменной. [Новый отчёт](../reports/bsp-skills/p5-sol-full-matrix-after-limit-recovery.md).
   Это не публикация и не проверка точного ZIP/tar.gz.

```mermaid
flowchart TD
    A[Sol activation и guided 3×] --> B[Оба gates PASS]
    B --> C[Два individual FAIL сохранены]
    C --> D[Paired разбор attached-file]
    D --> E[Новая frozen граница при правке]
    E --> F[Архив и упакованные установщики]
    F --> G[Публикация только по разрешению]
```

## P0 — чистая и воспроизводимая база сравнений

**Выполнено для `native-runtime-v1`:** per-run inventory до/после turn в одном
app-server процессе, PID/thread/turn binding, post-cleanup RED snapshot,
отдельный isolation gate, schema v6 и fingerprints helpers/account identity.
Zero-model preflight — отдельная проверка, не замена реального runtime evidence.
Credentials используются только в защищённом disposable home; исходный
`auth.json` не меняется.

В последних discovery и candidate циклах ordinary consumer manifests
сохранены до/после каждого этапа и независимо проверены. Поэтому повторять
задачу «получить первый baseline с manifest» больше не требуется.
**В текущем рабочем дереве реализовано:** штатный native runner сохраняет
SHA-256 manifest обычных файлов до вызовов модели, сверяет его до/после фаз,
после cleanup и до `resume`. Изолированный gate включает fixture; schema 7
блокирует старые отчёты без встроенного baseline. `.git` и только точный
`<consumer>/.agents/skills/bsp` исключены, связанные обычные пути запрещены.
Positive/negative unit-тесты, targeted native 1× и новые полные guided и
activation 3× на внешнем Git-корне прошли по итоговым gates: fixture/isolation
PASS, staged skill удалён.
Отчёт: `.tmp/p0-native-fixture-project-smoke.json` (локальный, не поставляется).
Первый пробный отчёт `.tmp/p0-native-fixture-smoke.json` сохранён с GREEN FAIL:
consumer в системном `Temp` не читался native-командами (`os error 5`);
fixture/isolation всё же PASS. Полные 3× теперь выполнены для текущих runner/corpus/payload, но не для
будущих правок и не заменяют проверку архивов/установщиков перед релизом.
Исторические manifests отсутствуют и задним числом не восстанавливаются.
[Границы прежнего resume](../reports/bsp-skills/v0.14-0749271-review-followup.md).

Для каждого нового сравнения:

1. Использовать `--dir` с отдельным потребительским Git-корнем вне этого
   репозитория: без локальных BSP sources/docs, заранее установленного `bsp`
   и иных проектных скилов, влияющих на задачу. Обычные fixture-файлы нейтральны:
   не рассказывают о RED/GREEN, staging и расположении скила. Проверить их
   содержание и фактические чтения в обеих трассах, записать host plugins.
2. Зафиксировать одинаковые модель, effort, задачи и consumer для RED/GREEN;
   единственное запланированное отличие — staged `bsp` в GREEN. Сохранить
   fingerprints скила, runner, корпуса и матрицы, actual skill catalog и
   ordinary fixture manifest до запуска/после cleanup. Штатный native runner
   сверяет baseline до `resume`; исторические schema 6 не имеют встроенного
   baseline и не подтверждают fixture resume.
3. Использовать проверенный распакованный v0.16 или точно зафиксированную кандидатную
   ревизию; указать источник `--skill`. Native результаты не переносить на
   стандартный/исторический `exec`. Инфраструктурные ошибки сохранять как FAIL.

**Готово, когда:** runner блокирует изменение ordinary fixture при запуске
и resume; положительный и отрицательный контроль имеют unit-регрессии;
свежий native отчёт подтверждает изоляцию и cleanup. Проверка не требует
изменения `SKILL.md` и не снимает исторических ограничений.

## P1 — границы активации и покрытие поведения

**После v0.16:** локальная матрица расширена с 5/24 до **6/24** references
и с 10 до 11 кейсов; для `longs-and-jobs.md` есть indexed targeted 1×,
первый полный 3× (2/3) и второй полный 3× (3/3). Второй полный activation
не прошёл read gate; третий на уточнённом scope прошёл coverage/read, но
провалил forbidden gate другого платформенного кейса. Отдельная текущая
sol-граница дала progress 3/3 и полный activation gate PASS. Первая партия v0.16 завершена; scope-before-open, explicit BSP
API review, library migration и allrefs-read не считать будущими правками.
Историческая выборка activation **28/30** сохранила два FAIL и не отменяет
platform-only ошибок или будущих ложных активаций.

- Сохранять три существующие отрицательные задачи обычного BSL/платформы:
  правильный ответ и отсутствие BSP activation проверяются раздельно.
  Добавлять новые границы при наблюдаемом пробеле, не дублировать прежние.
- Граница другой версии уже есть. Требование — не выдавать API 3.1.11 за
  подтверждённый API другой версии. Активация для распознавания границы
  допустима; это не обязательно `should_trigger=false`. Данные `bsp321_md/`
  использовать только при явной задаче сравнения и проверке версии.
- Первую партию не повторять как новую работу. Выбирать дополнительные
  рискованные темы по наблюдаемым ошибкам: прикладной контекст, public/service
  API, hook versus вызов, обработка ошибок; не только наличие имени метода.
- Guided corpus/matrix: `evals/cases.json` / `evals/reference-matrix.json`.
  Guidance-free corpus/matrix: `evals/activation-cases.json` /
  `evals/activation-reference-matrix.json`. Изменять каждую пару синхронно;
  результаты разных профилей хранить отдельно.

**Готово для партии, когда:** prompts не раскрывают расположение скила;
критерии отличают правильный ответ от выбранных ошибок; матрица согласована;
точечные результаты и повторы сохранены, действующие gates проходят.
В отчёте отдельно видны positive activation, exact-reference read и false
activation. Полный прогон перед релизом включает новые и прежние сценарии.

## P2 — разбор ошибок качества без ослабления gate

**На первой границе после v0.16:** полные guided/activation 3× прошли majority
и gates, но пять individual FAIL сохранены. Guided: ошибка имени хука,
смешанный `rg` exit 1 и исключённый верный BSL fence при предупреждении о
другом вызове. Activation: прогресс без включённого флага/точного чтения и
непринятая формулировка ограничения версии. [Raw audit и следующий
разбор](../reports/bsp-skills/p1-full-native-3x-followup.md). Первым шагом
для двух дефектов scorer уже добавлены paired controls, исправлены узкие
критерии и прошли новые targeted native 1×. [Отчёт
P2](../reports/bsp-skills/p2-wording-and-context-followup.md). Реальные ошибки
ответа не превращать в PASS правкой критериев. На изменённой границе
guided полный 3× **81/81**, activation **28/33**, strict read 6/7 и
**GREEN gate FAIL**. Причины пяти FAIL, включая пропуск активации
public/service в 2/3: [raw-отчёт](../reports/bsp-skills/p2-full-native-gate-failure.md).
Узкая правка scope теперь дала public/service 3/3 и strict read 7/7 на новой
activation матрице, но forbidden BSP call в platform-only задаче сохранил
**GREEN gate FAIL**; RLS 1/3 отказался от документированного метода после
чтения reference. [Отчёт того payload](../reports/bsp-skills/p3-neutral-api-scope-activation-followup.md).

**Текущая sol-граница:** после двух ограниченных поправок прогресса и
восстановления только 65 инфраструктурных guided-слотов оба full 3× gates
PASS. Activation 32/33 (version-boundary без активации), guided 80/81:
`save-attached-file-public-boundary` с безопасным guard переменной `Данные`
не принят regex, допускающим только другие имена. [Raw evidence и границы](../reports/bsp-skills/p5-sol-full-matrix-after-limit-recovery.md).
Проверить эту гипотезу paired controls; не превращать исходный FAIL в PASS
без новой frozen проверки.

**Исторические случаи** из v0.16 activation: `neutral-print-registration`
#3 — непринятый caller wording при корректных code patterns; теперь есть
точная fixture, узкая альтернативная формулировка и paired negative tests;
новый targeted native 1× PASS, прежний raw FAIL не переписан. Platform-only
`neutral-platform-exchange-registration` #2 — нет требуемого `ПланыОбмена`;
paired test подтверждает дефект ответа, не scorer. Guided той выборки 81/81,
но прежние FAIL не объявляются причинно исправленными.

**Исторические случаи** из candidate guided v0.15, исходные verdicts сохранены:

- `nonexistent-service-module` #2 и `classifiers-update-public-boundary` #3:
  правильный target встречается в выводе вместе с неверными sibling paths,
  aggregate reader exit 1; независимого успешного retry нет. Это mixed-reader
  evidence FAIL, а не доказательство, что reference вообще не читался.
- `update-safe-write-module-name` #2: публичный вызов правильный, activation/read
  PASS; required wording regex не принял формулировку ошибки в имени модуля.
  Manual diagnosis не меняет исходный raw FAIL.

1. Для каждого нового отказа различать ошибку ответа, ошибку чтения и false
   negative scorer. Сначала проверить raw trace; если локальные артефакты
   отсутствуют, воспроизвести случай. Не объявлять прежние причины устранёнными
   только из-за нового случайного PASS.
2. Для доказанного дефекта scorer добавить paired regressions: правильный
   ответ принимается, похожий неверный отвергается. Mixed-reader случай
   сначала проверить на негативных контролях; успешный listing не заменяет
   чтения, критерий не ослаблять ради принятия ответа.
3. Править узкий слой: reference/маршрут при ошибке агента, scorer при false
   negative, ожидание кейса при дефекте постановки. Неправильные вызовы,
   служебные методы и прямые вызовы hook блокировать детерминированно.
   Для смыслового расхождения, не выражаемого надёжным шаблоном, использовать
   выборочное независимое ревью по источнику, не один общий балл LLM-judge.
4. Сохранять пороги `--min-claims`, `--min-files`, `--min-coverage` и GREEN gates.
   Platform-only ошибки остаются в raw corpus, но не требуют активации BSP.

**Готово, когда:** исправленная причина имеет регрессию и свежий поведенческий
результат; похожие реальные ошибки остаются FAIL, исторические отчёты неизменны.

## P3 — проверяемость поведенческих правил при авторинге

1. Использовать выполненный evidence-пилот первой партии; добавлять только
   новые выбранные рискованные правила, например МЧД. Цепочка:
   утверждение → документация БСП 3.1.11 → сигнатура, регион и контекст
   по `src/cf/` → сценарий/reference → результат проверки.
2. При расхождении документации и исходника фиксировать влияние на
   рекомендацию. Начинать с документации, затем подтверждать по исходнику;
   совпадение имени метода не доказывает поведение. Если пилот не обнаружит
   проблем, не строить реестр всех API ради реестра.
3. Evidence хранить в материалах разработчика: установленный `bsp` работает
   без локальной документации/выгрузки.

**Готово, когда:** выбранные нюансы независимо проверяются по двум источникам,
противоречия описаны, router не увеличен и не зависит от локальных файлов.

## P4 — цена, устойчивость и подготовка будущего релиза

- Использовать уже собираемые токены и повторы. При росте стоимости на том
  же качестве добавить разрез по кейсу/reference и предупреждение о бюджете.
  Стоимость не служит основанием для принятия неправильного ответа.
- Поддерживать smoke нескольких разных границ, но не заменять им полные
  RED/GREEN 3×. Проверку другой модели хранить отдельно.
- Следующую поставку проверять как архив: точные payload bytes, оба
  установщика и совпадение fingerprint с native 3× на замороженном скиле.
  При тех же входных байтах и критериях прогон из извлечённого архива не
  повторять; при изменении любого из них понадобится новая frozen проверка.
  GitHub publication/assets verification отдельно от локального packaging.
- Сохранять единый скил и существующий простой harness. Hosted-агенты,
  self-modification, BDI, latent briefing, постоянная память и универсальный
  BSL parser требуют отдельной наблюдаемой потребности, не входят в эту итерацию.

## Порядок работы и контроль

Итерация: одна проблема → зафиксированный baseline → минимальная правка с
негативной регрессией → точечный RED/GREEN → проверка контрольных сценариев.
Изменение scorer или корпуса фиксирует новую границу сравнимости, а не
автоматически означает улучшение самого скила.

После изменения скила, валидатора или корпуса выполнить:

```bash
python -m unittest discover -s tests -v
python ci/validate_key_methods.py --coverage-only
python ci/validate_key_methods.py --src src/cf
python ci/run_skill_evals.py --dry-run
python ci/run_skill_evals.py --cases evals/activation-cases.json --reference-matrix evals/activation-reference-matrix.json --dry-run
```

Если `src/cf/` отсутствует, явно сообщить, что семантическая проверка не
выполнена. В native behavioral-командах явно фиксировать `--transport native`,
`--model`, `--reasoning-effort`, внешний `--dir`, источник `--skill` и отдельный
`--output` для каждого этапа. Authentication — только через защищённую
disposable native-обвязку; credentials не сохранять в отчёт.

Сначала smoke `--case message-bound-to-field --runs 1` или точечный новый кейс;
для activation указывать её `--cases` и `--reference-matrix`. Перед релизом —
полные guided и activation `--runs 3 --jobs 6` в том же внешнем consumer,
с prospective manifests и проверкой cleanup. Результаты разных моделей и
профилей не усреднять; реальные quality FAIL не повторять до случайного PASS.
Push/tag/release требуют отдельного разрешения, не являются побочным эффектом плана.
