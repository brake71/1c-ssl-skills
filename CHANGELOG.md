# Changelog

## 2026-10-04 — каноническая поставка и стабильная маршрутизация (v0.13)

### Этап 1 — надёжное чтение UTF-8 в behavioral eval

- Подтверждён инфраструктурный источник нестабильности: Windows PowerShell
  выводил `Get-Content -Encoding UTF8` в CP866, а Codex декодировал stdout как
  UTF-8. Модель получала повреждённые reference-файлы даже при успешном чтении.
- Runner задаёт одинаковые для RED/GREEN Windows-инструкции чтения через
  UTF-8-совместимые `rg`/Python, отключает профиль PowerShell и фиксирует UTF-8
  для Python. Глобальные настройки Codex и скилы не изменяются.
- Повреждённый вывод успешной команды сохраняется в `tool_output_decode_errors`
  и классифицируется как инфраструктурный `tool_output_encoding`, даже если
  финальный ответ прошёл scorer. Такие запуски можно повторить через `--resume`.
  Отдельный символ замены непосредственно у штатного маркера Codex
  `... N bytes omitted ...` исключается: это разрыв UTF-8 при обрезке большого
  вывода, а не порча читаемого файла. Повреждение вне этой границы по-прежнему
  считается инфраструктурной ошибкой.
- Исправлен false negative scorer: комментарий внутри правильной реализации
  hook о запрете прямого вызова больше не скрывает её BSL-блок; явно неверные
  примеры по-прежнему исключаются. Обе границы защищены unit-регрессиями.
- Отчёт переведён на schema v4 и содержит SHA256 runner: resume отклоняет
  результаты со старой семантикой или изменённым кодом runner.
- Независимое ревью выявило и помогло устранить ложное свидетельство чтения:
  `rg --files`, счётчики, поиск пути как шаблона и соседний `echo` больше не
  засчитываются. Требуется непустой вывод команды чтения; поддержаны обычные
  inline-чтения Python. Это эвристика команды, не доказательство использования
  всего reference моделью.
- Python cache исключён из GREEN staging и fingerprint скила: локальный
  `__pycache__` больше не меняет состав проверяемой поставки и SHA256.
- Проверки: 68 unit-тестов, API coverage 100% (662 claims, 24 references),
  semantic validation без ошибок/предупреждений, eval dry-run, `git diff --check`
  и локальная установка/повторное обновление обоими установщиками прошли.
  Содержание скила и пороги проверок не изменены.
- Свежий smoke `message-bound-to-field` на `gpt-6-luna medium`: RED 0/1,
  GREEN 1/1, чтение reference 1/1, без ошибок API, процесса и кодировки.
  Полный gate этим smoke не подтверждается.
- Полный RED/GREEN 27 × 3 выполнен на `gpt-6-luna medium`. Исходный отчёт
  ошибочно классифицировал 15 обрезанных выводов как ошибки кодировки.
  Offline replay тех же ответов/JSONL после точечного исправления scorer и
  классификатора: GREEN 22/27, activation 25/26, reference-read 24/26,
  invalid/unsafe/forbidden/process/infrastructure ошибок 0; RED 14/27.
  **Gate всё ещё FAIL** из-за пропуска reference в сценариях резервного
  копирования и замены ссылок. Это пересчёт сохранённых трасс, не новый запуск
  модели на финальном runner; исходный отчёт сохранён отдельно.
- Повторный smoke на предшествующей ревизии runner также не прошёл: GREEN 0/1 из-за
  отсутствия активации/чтения reference, без повреждения кодировки и API-ошибок.
  Каталог `skills/list` подтвердил обнаружение включённого project-scoped `bsp`;
  стабильность его неявного выбора моделью остаётся открытой задачей.
- Потребительские прогоны в приватных `TemporaryDirectory` оказались
  несопоставимы: Windows restricted token не мог прочитать staged-файлы, а
  PowerShell работал вне проекта. Их FAIL не используется как quality verdict.
  Калибровка обычного каталога с наследуемыми ACL подтвердила правильный cwd
  и UTF-8-чтение. Проверка в проекте без исходников разработчика продолжается.
- Этап инфраструктуры частичный: behavioral gate не пройден. Windows-инструкции
  runner не входят в поставку скила; даже PASS такого прогона отдельно не
  докажет неассистированное поведение обычного потребителя.

### Этап 2 — переносимые references и исполняемый BSL

- Исправлены контекст `ВызовСервера` (серверный модуль с разрешённым вызовом
  с клиента), срок кэширования `ПовтИсп` и трактовка глобального контекста.
  XML-выгрузка теперь явно необязательна; пути разрешаются относительно
  установленного `SKILL.md`, а не рабочего каталога разработчика.
- Добавлен самодостаточный каркас команды в модуле-переопределителе:
  структура источников, вложенный поиск, реальные колонки команды,
  экспортный хук и штатное условие видимости. Прикладные имена помечены
  как заменяемые; демо-модуль БСП не требуется.
- Scorer различает BSL, комментарии и строковые литералы. Комментарий или
  строка с текстом вызова больше не подтверждают исполняемый API; URL и
  строковые аргументы сохраняются. Предупреждение о другом методе и заголовок
  следующего отрицательного примера не скрывают проверяемый код.
- Критичные сценарии требуют безопасных аргументов записи и экспортного
  четырёхпараметрического хука с правильными колонками. Естественные
  эквивалентные формулировки принимаются без снижения требований или порогов.
- Проверки: 78 unit-тестов, coverage 662/662 по 24 references, semantic
  validation 0 ERROR / 0 WARN, eval dry-run и `git diff --check` прошли.
  Независимые ревью помогли закрыть comment-only PASS и скрытие неверного
  вызова предупреждением о неквалифицированном имени другого метода.
- Целевой consumer RED/GREEN трёх сценариев × 3: GREEN **3/3 по majority**,
  активация и чтение reference 3/3, запрещённые/неверные/служебные вызовы 0.
  Один запуск повторён через проверенный resume после порчи вывода в
  PowerShell pipeline; итоговых infrastructure errors 0. В fundamentals
  один из трёх ответов не активировал скил и ошибся в именах: **8/9 отдельных
  GREEN-ответов**, а не устойчивые 9/9.
- Этот targeted PASS — ограниченный технически ассистированный прогон,
  не неассистированный Windows-тест.
- Последующий полный consumer 27 × 3 на `dca64bf` дал **gate FAIL**:
  GREEN 20/24 полностью оценённых сценария, ещё 3 исключены из сводки из-за
  `tool_output_encoding` после `rg | Select-String`; RED 13/27. Неверных,
  служебных и запрещённых вызовов в GREEN 0. Majority не прошло у update,
  delete-marked, SMS и fundamentals; всего 19 quality-failed GREEN-запусков.
  Часть отказов связана со scorer, а не с ошибками BSL; разбор и повтор на
  окончательном runner ещё нужны. Исходный отчёт сохранён без пересчёта.
  **v0.13 ещё не готов к релизу.**

### Этап 3 — закрытие причин consumer failures (candidate)

- Scorer исключает BSL по метке неверного примера или запрету конкретного
  вызова, а не по любому отрицательному замечанию рядом. Удалены опасные
  исключения для положительных рекомендаций и реализаций hooks: они могли
  скрывать противоречивый запрет вызова в теле процедуры.
- Python read-evidence поддерживает обычные переменные `Path`, текст и вывод
  диапазона строк. Вывод пути/счётчика, пустые чтения, условные выражения,
  переназначенные фабрики и перенаправленный stdout не засчитываются.
- Windows guidance явно исключает pipeline native readers через PowerShell
  cmdlets. Пороги и число повторов не снижены; эквивалентные формулировки
  границы hook и неправильного имени модуля покрыты регрессиями.
- References: исправлено неверное утверждение об автоматическом создании
  тела клиентского обработчика разблокировки; разделены проверка самой МЧД
  в реестре и проверка подписи объекта; уточнены исходное имя модуля обновления,
  инициатор/место исполнения серверного вызова и полные имена в памятке.
- 84 unit-теста PASS, API 662/662, semantic 0 ERROR / 0 WARN, dry-run PASS.
  Независимые ревью фактов и scorer выполнены, найденные блокеры устранены.
- Свежий targeted consumer 6 × 3: GREEN majority 5/6, individual 16/18,
  activation/reference 6/6, invalid/unsafe/forbidden/infra 0. Несмотря на
  PASS стандартного 80%-gate, fundamentals остаётся предметом доработки.
  Последующий fundamentals × 3 на следующем skill fingerprint: 1/3 native;
  один дополнительный правильный ответ отвергнут буквальным шаблоном
  («имя неверно»). Этот false negative исправлен регрессией, а пропуск полного
  имени серверного модуля по-прежнему отклоняется. Это не новый native PASS.
- Локальные ZIP/tar.gz candidate содержат ровно 29 файлов, проверены побайтово;
  установка и повторное обновление из распакованного candidate обоими
  установщиками прошли без сети и изменения глобальных скилов.
- Свежая полная consumer матрица 27 × 3 на окончательных fingerprint запущена.
  До её завершения и отдельной проверки transport без reader guidance
  **готовность релиза не подтверждена**. Теги, push и публикация не выполнялись.

### Этап 4 — consumer gate и безопасный bootstrap на Windows

- Полная свежая RED/GREEN матрица 27 × 3 на `3bdd931` завершена: **gate PASS**,
  GREEN majority 26/27, individual 73/81; API-quality 75/81. Majority activation
  и reference-read 26/26; invalid/unsafe/forbidden/process/infra 0. RED majority
  14/27. Это технически ассистированный Windows-прогон, не unassisted PASS.
- Отдельная установка архива без reader guidance выявила повреждение stdout
  во всех 9 BSP-запусках. Plain-BSL ответы были корректны; helper ошибочно
  требовал от них reference. Исходный диагностический JSON не переписан.
- Маршрутизатор переведён в ASCII-only English, чтобы первое чтение было
  безопасным при любой совместимой с ASCII code page. Все 24 русских references,
  точные имена API и требования workflow сохранены; отвечать нужно на языке
  пользователя. UTF-8-reading инструкции теперь входят в установленный скил,
  включая чтение файлов проекта. Глобальные настройки не меняются.
- Свежий guidance-free installed-archive diagnostic с ASCII bootstrap:
  **encoding/infra 0/12**, individual 11/12, majority 4/4; BSP activation 9/9,
  reference evidence 8/9. Оставшийся правильный fundamentals-ответ был отклонён
  из-за отсутствия успешной команды чтения: комбинированная shell-команда
  завершилась с кодом 1. Это отдельный ограниченный diagnostic, не полный gate.
- Исправлена отрицательная классификация по фрагменту `невер`: возвращаемый
  код `НеверныйЛогинИлиПароль` больше не превращает правильный BSL в неверный
  пример. Реальные отрицательные примеры по-прежнему исключаются.
- Classifiers-ответы дополнительно показали настоящую неполноту: вместо
  обработки ошибки в ветке был только комментарий. Reference теперь содержит
  исполняемую реакцию на ошибку и отделяет нормальный `ОбновлениеНеТребуется`.
  Проверка обработки результата реализована как ограниченный анализ BSL без
  выполнения кода: один самодостаточный fence, реальный source-call, aliases,
  ветвления и сообщения/журнал/исключения. Исключение при нормальном статусе,
  заглушки и смешивание разных fences отвергаются. Независимое финальное ревью
  не воспроизвело блокирующих ошибок.
- Уточнён факт о предложенном classifiers-вызове: метод
  `РаботаСКлассификаторамиВызовСервера.ОбновитьКлассификаторы` не существует;
  отрицательное утверждение подтверждено выгрузкой БСП 3.1.11.
- Проверки текущего этапа: **90 unit PASS**, API **663/663** по 24 references,
  semantic **0 ERROR / 0 WARN**, dry-run и `git diff --check` PASS.
  Быстрый consumer smoke: GREEN 1/1. Следующий targeted classifiers 3× дал
  native 1/3 (gate FAIL), хотя настоящая обработка ошибки была корректна 3/3:
  один ответ пропустил исходное полное имя, другой был отклонён из-за порядка
  слов в предупреждении. Естественные эквиваленты защищены RED→GREEN-тестом;
  исходный targeted JSON не пересчитан и не объявляется PASS.
- ASCII/bootstrap и покрытие всех reference-маршрутов защищены unit-тестами.
  После этих изменений fingerprint требуется новый полный behavioral прогон;
  PASS на `3bdd931` не переносится автоматически на текущий candidate.
- Финальные ZIP/tar.gz содержат по 29 файлов и побайтно совпадают с текущей
  поставкой. Install + update обоими упакованными установщиками в локальные
  пути с пробелами прошли; по 27 файлов скила совпали с распаковкой.
- Guidance-free diagnostic на финальном архиве: **majority 4/4**, individual
  **10/12**, quality **11/12**, BSP activation/reference **9/9**, infra **0/12**.
  Classifiers и message прошли 3/3; fundamentals — 2/3 (пропущены два полных
  имени модулей), plain-BSL — 2/3 (одна лишняя активация при правильном ответе).
  Это ограниченный diagnostic с сохранёнными host plugins, не полный gate.
  Fingerprint скила, runner и корпуса подтверждены.
- Полный финальный consumer RED/GREEN **27 × 3 завершён без resume: gate PASS**.
  GREEN **25/27 majority**, **72/81 individual**, quality **77/81**; majority
  activation/reference **26/26**. Invalid/unsafe/forbidden/process/policy/infra
  **0**. RED **13/27 majority**, **36/81 individual**, invalid 4, unsafe 7,
  forbidden 2, infra 0. Все четыре fingerprint совпали с проверенными bytes.
  Classifiers GREEN 3/3, включая настоящую обработку ошибки.
- Оставшийся behavioral debt: fundamentals 1/3 (по одному полному имени модуля
  пропущено в двух ответах), plain-BSL 1/3 (две лишние активации). Единичные
  провалы чтения reference — long-operation, currency-rates, business-statistics;
  внешний компонент — без требуемого предупреждения. PDn run2 содержит
  правильный вызов и предупреждение, но scorer исключил BSL-блок: это отдельный
  долг эвристики отрицательных примеров, не доказанная ошибка reference.
  Сырые результаты не пересчитаны. PASS означает выполнение существующих
  порогов, не 81/81 повторяемость и не полный unassisted Windows gate.
- Кандидат проверен по текущим gate; релиз, теги и push не выполнялись.
  Архив соответствует проверенным bytes рабочего checkout. При сверке с Git
  обнаружено только EOL-различие: четыре строки `agents/openai.yaml` — CRLF
  в checkout и LF в Git blob. Канонический LF-архив имеет другой fingerprint;
  результаты нельзя автоматически переносить на него. Перед публикацией
  нужно согласовать и проверить точные bytes выпуска.

### Этап 5 — каноническая поставка и финальная проверка v0.13

- Добавлен `ci/build_release.py`: ZIP/tar.gz собираются из Git blobs, а не
  checkout; порядок, даты и режимы файлов фиксированы, cache/untracked
  исключены. Manifest хранит исходное дерево, per-file/архивные хеши и
  fingerprint. Две сборки кандидата дали побайтно одинаковые архивы.
- Release workflow использует тот же сборщик. CI smoke проверяет install +
  update обоими **упакованными** установщиками в пути с пробелами.
  `.gitattributes` фиксирует LF поставки; fingerprint скила сортирует
  относительные POSIX-имена одинаково на Windows/Linux. Старые платформенные
  fingerprint не объявляются проверкой новой ревизии.
- Уточнён scope описания скила: обычный BSL без библиотечной интеграции не
  требует BSP. Памятка `ОбщегоНазначения*` содержит полный набор обсуждаемых
  клиентских/серверных/служебных вариантов и критерий завершения ответа.
- Исправлен PDn false negative scorer: «этот метод» после явно названного
  другого метода не скрывает рекомендуемый BSL fence. Регрессия RED→GREEN
  и replay исходного ответа прошли; защитные тесты отрицательных примеров
  сохранены. Scorer остаётся ограниченной эвристикой, не компилятором BSL.
- Первый канонический targeted gate был FAIL: fundamentals 1/3. Исходные
  ответы сохранены; уточнены реальные служебные замены и серверное место
  исполнения `ВызовСервера`, затем собран **новый** кандидат.
- Финальные проверки: **98 unit PASS**, API **663/663**, 24 references,
  semantic **0 ERROR / 0 WARN**, dry-run, py_compile, actionlint и diff-check
  PASS. Локальные install/update подтвердили побайтное совпадение 27 файлов
  скила с архивом; глобальные скилы не менялись.
- Новый consumer smoke PASS; targeted 3 × 3 — **3/3 majority**, 8/9 individual.
  Полный RED/GREEN 27 × 3 — **gate PASS**, GREEN **27/27 majority**, **78/81
  individual**, quality 79/81, majority activation/reference **26/26**.
  Invalid/unsafe/forbidden/process/policy/infra/incomplete **0**. RED —
  11/27 majority, 34/81 individual; invalid 4, unsafe 11, forbidden 6.
- Отдельный guidance-free installed-archive diagnostic: **4/4 majority**,
  **11/12 individual**, BSP activation/reference **9/9**, plain BSL без
  активации **3/3**, ошибок кодировки/инфраструктуры **0**. Это ограниченный
  diagnostic с сохранёнными host plugins, не полный unassisted Windows gate.
- Сырые результаты не пересчитаны и quality failures не заменены повторами.
  Остался долг scorer по backup/files и эквивалентным формулировкам; один
  полный currency-запуск не активировал скил/не прочёл reference.
  PASS означает выполнение gate, не 81/81 гарантированную повторяемость.
- Точные bytes, fingerprint, отчёты и ограничения зафиксированы в
  `reports/bsp-skills/v0.13-release-readiness.md`. По отдельному разрешению
  опубликован `v0.13` на коммите `c5585f3`: release workflow PASS, скачанные
  ZIP/tar.gz и все 29 файлов побайтно совпали с проверенным кандидатом.

## 2026-09-28 — строгая проверка API и eval (v0.12)

- Статический валидатор требует 100% eligible API claims во всех 24 references;
  проверено 662 утверждения без semantic errors или warnings.
- Eval runner различает требования к прозе и исполняемому BSL, поддерживает
  code-block assertions, проверяет чтение назначенного reference для scoped
  GREEN-кейсов и сохраняет обратную несовместимость отчётов через schema v3.
- Усилены сценарии реализации hooks и регистрации объекта печати, добавлены
  детерминированные тесты scorer и API-валидатора.
- Проверки перед выпуском: 55 unit-тестов, API coverage/semantic validation,
  eval dry-run и `git diff --check` прошли.
- **Известное ограничение:** полный RED/GREEN-прогон 27 кейсов × 3 на
  `gpt-6-luna medium` не прошёл: последний полный отчёт на предыдущей версии
  scorer показал GREEN 18/27, reference-read 23/26 и 5 invalid API-вызовов.
  После последующего ужесточения проверки отдельных BSL-блоков целевой кейс
  печати прошёл 0/3. Полная матрица на точной версии scorer, входящей в v0.12,
  не запускалась; поведенческий GREEN gate не заявляется как пройденный.

## 2026-09-15 — полное поведенческое покрытие references (v0.11)

- Поведенческое покрытие расширено с 9 до всех 24 reference-файлов: корпус
  содержит 27 сценариев, включая 15 новых проверок публичных границ API,
  служебных модулей и хуков переопределения.
- Маршрутизатор теперь требует прочитать выбранный основной reference и сверить
  с ним правила и пример ответа, а не отвечать только по таблице навигации.
- Для загрузки курсов валют добавлен отдельный сценарий со стабильным
  `РаботаСКурсамиВалютКлиентЛокализация.ПоказатьЗагрузкуКурсовВалют(...)`;
  прямое открытие внутренней формы и служебная клиентская обёртка исключены.
- Исправлен сценарий замены ссылок: публичный
  `ОбщегоНазначения.ЗаменитьСсылки(...)` сам проверяет прикладные правила при
  `УчитыватьПрикладныеПравила = Истина`; прямой вызов служебной проверки больше
  не рекомендуется.
- Полный RED/GREEN-прогон 27 сценариев × 3 завершён: GREEN 27/27, активация
  26/26, без invalid/unsafe/forbidden/process/policy errors. RED прошёл 18/27,
  допустил 1 несуществующий, 16 служебных и 4 запрещённых вызова; расход токенов
  GREEN ниже примерно на 57%.

## 2026-09-04 — возобновляемые evals и проверяемое покрытие (v0.10)

- Поведенческий runner поддерживает `--resume` для отчёта, заданного через
  `--output`: успешные и качественно проваленные запуски не повторяются, а
  отсутствующие, незавершённые и инфраструктурно упавшие запускаются снова.
- Прогресс атомарно сохраняется после каждого `case × phase × run`.
- Причины инфраструктурных отказов разделены на quota/rate limit,
  authentication, network, timeout, model unavailable, sandbox policy и
  прочие ошибки процесса; они не смешиваются с ошибками качества ответа.
- `bsp_api.py` выводит диапазон строк тела экспортного метода для команд
  `method` и `module`; валидатор и eval runner адаптированы к расширенному
  формату парсера.
- Добавлена машинно проверяемая матрица `evals/reference-matrix.json`, которая
  связывает все 24 reference-файла с eval cases и явно показывает пробелы
  поведенческого покрытия. Сейчас сценариями покрыты 9 из 24 references.
- Полный релизный RED/GREEN-прогон прошёл: GREEN 12/12, активация 11/11, без
  invalid/unsafe/forbidden/process/policy errors. RED прошёл 8/12, допустил 1
  несуществующий и 9 служебных вызовов; расход токенов GREEN ниже примерно на
  58%.

## 2026-08-30 — воспроизводимые evals на Luna и Windows sandbox (v0.9)

- Модель поведенческих тестов зафиксирована как `gpt-5.6-luna`; другой точный
  идентификатор по-прежнему можно передать через `--model`.
- Windows-запуск с `--ignore-user-config` теперь явно включает restricted-token
  backend через `windows.sandbox="unelevated"`. Это устраняет блокировку команд
  чтения staged-скила в режиме `--sandbox read-only`.
- Отказы `blocked by policy` записываются как `tool_policy_blocked`, считаются
  инфраструктурными ошибками даже при коде процесса 0 и видны в консольной
  сводке.
- Добавлены регрессионные тесты сборки команды `cdx` для Windows/POSIX,
  фиксированной модели и классификации policy blocks.
- Полный релизный RED/GREEN-прогон на Luna прошёл: GREEN 12/12, активация 11/11,
  по нулям invalid/unsafe/forbidden/process/policy errors. RED прошёл 10/12 и
  допустил 5 служебных вызовов; скил устранил их все и сократил наблюдаемый
  расход токенов GREEN примерно на 47%.
- Добавлен план дальнейшего расширения поведенческого покрытия и надёжности
  eval-инфраструктуры: `plans/2026-08-30-bsp-skill-improvements.md`.

## 2026-08-06 — поведенческие evals и актуальная поддержка Codex (v0.8)

- Добавлен воспроизводимый RED/GREEN runner `ci/run_skill_evals.py`, который
  запускает Codex через `cdx exec`, временно размещает скил в project-scoped
  `src/.agents/skills/bsp` и сохраняет JSONL, ответы и итоговый JSON-отчёт.
- Добавлен корпус из 12 положительных, граничных и отрицательных сценариев в
  `evals/cases.json`; проверяются активация, ожидаемые паттерны, антипаттерны,
  существование экспортных методов и прямые вызовы служебных API/хуков.
- Добавлены unit-тесты eval runner и проверка корпуса в CI.
- Независимые eval-запуски выполняются параллельно с ограничением `--jobs`,
  а промежуточный отчёт сохраняется после завершения каждого сценария.
- Scorer отличает явно отрицательные fenced-примеры от рекомендуемого BSL-кода
  по соседнему контексту и связанным альтернативам; реальные формулировки
  защищены регрессионными тестами.
- Релизный workflow теперь публикует архивы только после успешной валидации;
  изменения `evals/**` также запускают CI.
- Улучшены `description` и рабочий процесс скила: выбор одного основного
  reference, точечная загрузка сценария, обязательная граница stable/service/
  deprecated/`*Переопределяемый`, проверка через `bsp_api.py` при наличии
  выгрузки.
- Добавлен `agents/openai.yaml`. Путь установки Codex обновлён с устаревшего
  `~/.codex/skills` на актуальный `~/.agents/skills`.
- Frontmatter скила оставляет только `name` и `description`; во все длинные
  reference-файлы добавлены компактные оглавления.

## 2026-07-29 — установка и независимая структура skills (v0.7)

- Публичный скил перенесён из `.claude/skills/bsp` в независимый от harness
  каталог `skills/bsp`; внешний development-submodule перенесён в `vendor/`.
- Добавлены идемпотентные установщики `install.sh` и `install.ps1` для
  установки и обновления в Claude Code, Codex, OpenCode или произвольный
  каталог.
- CI и release workflow обновлены под новую структуру, smoke-тесты установщиков
  и выпуск ZIP/tar.gz архивов.

## 2026-07-21 — инфраструктура единого BSP-скила (v0.6)

- README и CLAUDE.md синхронизированы с единым `.claude/skills/bsp` после
  удаления старых кластеров `bsp-*`.
- `agents-best-practices` оформлен как корректный git submodule через
  `.gitmodules`.
- `ci/validate_key_methods.py` переведён с устаревших Markdown-таблиц на
  inline API-утверждения `Модуль.Метод(...)` и обязательные пороги покрытия.
- Добавлена проверка положительных и отрицательных API-утверждений, регионов и
  неэкспортных методов по `src/cf`.
- Добавлены синтетические BSL/Markdown-фикстуры и unit-тесты парсера,
  валидатора, длинных сигнатур, регионов и ошибок покрытия.
- CI запускает unit-тесты, coverage-only проверку и проверяет mapping
  submodule.
- Парсер `bsp_api.py` больше не ограничивает многострочную сигнатуру 30
  строками.
- Исправлены проверяемые утверждения в `data-exchange.md` и опечатка в имени
  хука `ПриЗаполненииПоставляемыхПрофилейГруппДоступа`.

## 2026-07-04 — BSP skills audit & print skill (v0.5)

### fix: полный аудит 24 reference-файлов скила bsp (БСП 3.1.11)

Перепроверка всех reference-файлов в `.claude/skills/bsp/references/`
по исходникам `src/cf/` и документации `bsp3111_md/`. Исправлено 37
критических расхождений и ~60 минорных уточнений:

- **print-reports.md**: сигнатура `ДобавитьКомандыПечати` (1 параметр),
  сценарий `ПриОпределенииНастроекПечати`, автокомпоновка (Способ А)
- **fundamentals.md**: заменён выдуманный хук, уточнена категория ДлительныеОперации
- **base-common.md**: исправлены сигнатуры и возвращаемые структуры
- **longs-and-jobs.md**: исправлены сигнатуры и регионы
- **update.md**: исправлен регион метода
- **esign-mcd.md**: исправлён метод `РасшифровкаДанных`
- **classifiers.md**: исправлены сигнатуры и регионы
- **currencies-banks.md**: исправлен возврат `ПолучитьКурсВалюты` (Структура, не Неопределено)
- **external-components.md**: дополнен `ИспользуемыеКомпоненты`
- **users-access.md**: добавлены типы `ЗадачаСсылка`/`ПланОбменаСсылка` в `ОписаниеДанных`
- **comms.md**: исправлен возврат `СформироватьСообщение`, добавлены `Знач` и статус `НеОтправлено`
- **admin-tools.md**: исправлены поля `НовыеПараметрыБлокировкиСоединений`, пример с массивом
- **backup.md**: добавлен модуль `РезервноеКопированиеИБГлобальный`, исправлен интервал (15 мин)
- **perf-monitoring.md**: исправлено «не существует» на «служебный/не экспортируется»
- **commands-external.md**: исправлена сигнатура `ДобавитьКомандыСозданияНаОсновании` (2 параметра)
- **forms-validation.md**: исправлены регион, поля структуры, типы колонок, параметры хуков
- **prefixes.md**: исправлены неверные результаты в примерах
- **multilang.md**: исправлено описание `ИменаРеквизитовСУчетомКодаЯзыка` (Соответствие, не Массив)
- **report-dedup.md**: исправлен тип объекта (ОбщаяФорма, не Отчёт), добавлен `СтруктураПодчиненностиСлужебный`

### feat: план аудита

Добавлен `plans/bsp-references-audit-plan.md` — воспроизводимый план аудита
reference-файлов скила bsp.

## 2026-06-20 — search scripts & CI validator

### fix: parser multi-line Экспорт signatures (critical)

`parse_export_methods` in all 4 search scripts failed to find methods where
`Экспорт` is on a line after `Функция`/`Процедура` (common in BSP for long
parameter lists). Example: `УправлениеПечатью.СформироватьПечатныеФормы` was
reported as "not found" despite being a real export method.

Rewrote parser to two-pass approach:
1. First pass: build per-line region label map via `#Область` stack (handles
   nested sub-regions inside `ПрограммныйИнтерфейс`).
2. Second pass: scan `Функция`/`Процедура`, accumulate signature lines until
   `Экспорт` or `КонецФункции`/`КонецПроцедуры` or a new function declaration.

Before: `УправлениеПечатью` reported 35 stable methods. After: 36 stable +
correct unstable detection.

### fix: nested #Область inside ПрограммныйИнтерфейс

Methods in sub-regions (e.g. `ОповещениеПользователя` inside
`ПрограммныйИнтерфейс`) were missed because the parser reset `current_region`
to `None` on any unrecognised `#Область` name. Now sub-regions inherit parent
stability via explicit stack.

### fix: СлужебныеПроцедурыИФункции export methods invisible

Export methods in `#Область СлужебныеПроцедурыИФункции` were skipped entirely
(region label = `None`). Now labelled `"unstable"` so `only_stable=False`
finds them. Affects all 4 scripts.

### fix: UTF-8 stdout on Windows

All 4 scripts + validator force `sys.stdout.reconfigure(encoding="utf-8")`
via safe `getattr`. Cyrillic method names no longer produce mojibake in
Git Bash on Windows.

### fix: --src required, auto-detect removed

`auto_detect_src` (walk-up search for `CommonModules/`) removed from all 4
scripts. `--src <path>` is now `required=True`. Rationale: auto-detect was
fragile — worked from repo root by coincidence, failed from subdirectories,
silently picked wrong root. Agent must pass the path explicitly.

Exit codes: 2 = `--src` missing, 1 = invalid path / no `CommonModules/`.

### fix: wrong example in bsp-data/SKILL.md

`bsp_data_search.py method СформироватьПечатныеФормы` — this method belongs
to `bsp-ui-forms` (print), not `bsp-data`. Replaced with
`УзелПланаОбменаПоКоду` (data-exchange domain method).

### fix: non-export method in bsp-ui-forms/SKILL.md example

`ДобавитьКомандыПечати` is not an export method (no `Экспорт`). Replaced
with `СоздатьКоллекциюКомандПечати` (stable export).

### fix: missing module prefixes

- `bsp_core_search.py`: added `ОбновлениеИнформационнойБазы` to
  `MODULE_PREFIXES` and `BSP_SUBSYSTEMS` (was missing — key methods in
  `bsp-update-key-methods.md` reference this module).
- `bsp_ops_search.py`: added `СоединенияИБ` to `MODULE_PREFIXES` and
  `BSP_SUBSYSTEMS` (owns `ЗавершениеРаботыПользователей` subsystem methods).

### feat: cross-cluster routing

Each umbrella SKILL.md (`bsp-core`, `bsp-data`, `bsp-ops`, `bsp-ui-forms`)
now has a `## Cross-cluster routing` section with:
- trigger → target-cluster table
- ambiguous-keyword disambiguation (e.g. `phone` in contact-info vs comms,
  `Задача` business-task vs `РегламентныеЗадания`, `Файл` versioning vs exchange)
- fallback to `bsp-fundamentals` when no trigger matches

### refactor: key-methods.md headings

5 `*-key-methods.md` files: heading changed from
«Key methods (полный справочник)» to «Key methods (дополнение)».
Added note: "not a full reference — run `python ... module <Name> --src`
for complete list".

### feat: CI validator

`ci/validate_key_methods.py` — validates all `references/*.md` method tables
against real BSP source code in `src/cf/`. For each `Module.Method` +
declared stability (✅ стабильный / ⚠️ служебный):
1. Finds module in `CommonModules/`.
2. Parses `.bsl` with the same parser as search scripts.
3. Reports mismatches: method not found, declared stable but in
   `СлужебныеПроцедурыИФункции`, etc.

First run found **40 errors** in existing skill content (methods declared
stable but actually in unstable regions). These are content bugs to fix
separately — the validator now catches them automatically.

Usage:
```bash
python ci/validate_key_methods.py --src src/cf
python ci/validate_key_methods.py --src src/cf --strict
```

### feat: GitHub Actions workflow

`.github/workflows/validate-skills.yml` — on push/PR to `.claude/skills/**`
or `ci/**`:
- `py_compile` all 4 search scripts + validator
- verify `--src` required (exit 2 when missing)
- verify UTF-8 reconfigure block loads

Full key-methods validation requires `src/cf/` (in `.gitignore`), so it
runs locally before commit (commented out in workflow).

### docs: README

Added "Инструменты разработчика" section: search scripts usage, CI validator,
GitHub Actions workflow description.

## 2026-06-08 — BSP skills consolidation

### feat: 4 cluster umbrella skills

Replace 25 standalone BSP skills with 4 cluster skills + decision-tree routing.

| Cluster | Content | Leaf skills |
|---------|---------|-------------|
| `bsp-core` | Navigation, utilities, background jobs, prefixes, update | 5 |
| `bsp-data` | Exchange, e-signature, contact info, classifiers, currencies, external components | 6 |
| `bsp-ui-forms` | Connected commands, printing, form properties, multilang, files/versions, dedup | 6 |
| `bsp-ops` | Users/access, comms, business processes, admin tools, backup, monitoring, personal data | 7 |

Each cluster:
- SKILL.md (~70-80 lines) — frontmatter + decision tree + leaf index
- references/ — full leaf skill content (24 files, no frontmatter, no hardcoded paths)
- scripts/ — Python search script for 1C config export

### feat: Python search scripts (4)

Per-cluster script with `detect`, `method`, `module`, `modules-by-subsystem` commands.
Auto-detect --src by walking upward for CommonModules/.
Parse BSL files by #Область ПрограммныйИнтерфейс for stable API listing.

### fix: content restoration

bsp-bp-tasks.md and bsp-admin-tools.md lost Patterns/Anti-patterns/BSL examples during migration. Restored from originals.

### fix: key-methods.md links

bsp-commands-external and bsp-files-and-versions reference files had broken `references/key-methods.md` links. Updated to `bsp-*-key-methods.md`.

### fix: argparse --src in search scripts

Windows Python + subparsers + `--src` before subcommand = parse fail. Switched to `parents` pattern. All 4 scripts fixed.

### chore: .gitignore

Add `__pycache__/` and `*.pyc`.

### refactor: remove old standalone skills

Delete 25 old bsp-* directories. 8954 lines removed.

### docs: AGENTS.md

Update .claude/skills section. 25 entries → 4 clusters + 3 non-BSP skills.
