# Changelog

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
