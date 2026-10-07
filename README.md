# 1С:БСП Skill

Скил для AI-агента, который помогает применять 1С:БСП 3.1.11 в прикладной
разработке: выбирать реальные общие модули и методы, учитывать контекст
исполнения, отличать стабильный API от служебного и не выдумывать интерфейсы.

## Установка и обновление

Одна и та же команда подходит и для первой установки, и для обновления. По
умолчанию скил устанавливается для Claude Code в `~/.claude/skills/bsp`.

### Linux и macOS

```bash
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash
```

Для других агентов:

```bash
# Codex: ~/.agents/skills/bsp
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --agent codex

# OpenCode: ~/.config/opencode/skills/bsp
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --agent opencode

# Произвольный каталог skills
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --target /path/to/skills
```

Чтобы установить конкретный тег или коммит, передайте `--ref`:

```bash
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --ref v0.14
```

Если не хочется выполнять загруженный код через pipe, сначала сохраните и
просмотрите установщик:

```bash
curl -fsSLO https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh
less install.sh
bash install.sh --agent codex
```

### Windows PowerShell

Для Claude Code:

```powershell
irm https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.ps1 | iex
```

Для Codex, OpenCode или произвольного каталога параметры удобнее передать
сохранённому скрипту:

```powershell
irm https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.ps1 -OutFile install.ps1
.\install.ps1 -Agent Codex
.\install.ps1 -Agent OpenCode
.\install.ps1 -Target C:\path\to\skills
.\install.ps1 -Agent Codex -Ref v0.14
Remove-Item .\install.ps1
```

В pipe-варианте параметры задаются переменными окружения:

```powershell
$env:SKILLS_AGENT = 'Codex'
irm https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.ps1 | iex
Remove-Item Env:SKILLS_AGENT
```

Установщики загружают указанный git ref, проверяют наличие `SKILL.md` и
атомарно заменяют только каталог `bsp`. Остальные пользовательские скилы не
затрагиваются.

### Из релиза или клона

GitHub Release содержит архивы `bsp-skill-vX.Y.zip` и
`bsp-skill-vX.Y.tar.gz`. Внутри — `skills/bsp/`, `install.sh` и `install.ps1`.
Каталог `skills/bsp` можно вручную скопировать в каталог скилов агента;
установщики поддерживают локальный источник без обращения к сети:

```bash
bash install.sh --source . --agent codex
```

```powershell
.\install.ps1 -SourceDirectory . -Agent Codex
```

Из клона:

```bash
git clone https://github.com/brake71/1c-ssl-skills.git
cp -r 1c-ssl-skills/skills/bsp ~/.claude/skills/
```

## Состав

Репозиторий поставляет один umbrella-скил `skills/bsp/`:

- `SKILL.md` — ASCII-only маршрутизатор по задачам: первое чтение безопасно
  даже при legacy code page Windows;
- `references/` — 24 тематических справочника со сценариями, сигнатурами,
  примерами и антипаттернами;
- `scripts/bsp_api.py` — проверка методов, регионов и диапазонов строк по XML-выгрузке
  конфигурации БСП.

Reference-файлы не являются отдельными скилами. Агент сначала загружает
`bsp/SKILL.md`, затем выбирает один подходящий reference. Скил рассчитан на
БСП 3.1.11; для другой версии сигнатуры и стабильность API нужно перепроверять
по исходникам соответствующей поставки.

Маршрутизатор написан по-английски, references и точные BSL-имена — по-русски;
ответ остаётся на языке пользователя. На Windows инструкции скила предлагают
native `rg` или Python с UTF-8 stdout: `Get-Content -Encoding UTF8` задаёт только
кодировку входа, но не гарантирует UTF-8 в выводе инструменту агента. Глобальные
настройки оболочки установщики не меняют.

## Проверка API по исходникам

Скрипт принимает обязательный путь к корню выгрузки конфигурации с каталогом
`CommonModules/`:

```bash
python -X utf8 skills/bsp/scripts/bsp_api.py method СообщитьПользователю --src src/cf
python -X utf8 skills/bsp/scripts/bsp_api.py module ОбщегоНазначения --src src/cf
python -X utf8 skills/bsp/scripts/bsp_api.py modules --src src/cf
```

Выгрузка `src/cf/` не распространяется с репозиторием. Без неё
reference-файлы остаются пригодны для использования, но факты нельзя
дополнительно подтвердить скриптом.

## Разработка и проверки

```bash
python -m unittest discover -s tests -v
python ci/validate_key_methods.py --coverage-only
python ci/validate_key_methods.py --src src/cf
python ci/run_skill_evals.py --dry-run
```

CI также проверяет компиляцию скриптов, обязательность `--src`, покрытие
references и локальные smoke-тесты обоих установщиков. Полная семантическая
проверка требует локальную выгрузку БСП и поэтому выполняется перед релизом
локально.

### Релизный кандидат без публикации

Сборщик читает содержимое Git-дерева, а не рабочий checkout: окончания строк
Windows, незакоммиченные изменения и Python cache не меняют архивы. Для новой
ревизии сначала сохраните изменения в локальном коммите или явно передайте
подготовленное Git-дерево через `--ref`. Тег и сеть для сборки не нужны:

```bash
python ci/build_release.py --ref HEAD --version v0.14 --output-dir .tmp/v0.14-candidate
```

Выходной каталог должен быть новым. В нём — ZIP, tar.gz, распакованный
`extracted/` и `manifest.json` с исходным деревом, хешами файлов/архивов и
fingerprint скила. Архивы содержат только `skills/bsp`, `install.sh` и
`install.ps1`; workflow выпуска использует тот же сборщик. `.gitattributes`
фиксирует LF для поставки, а fingerprint сортирует относительные POSIX-имена
одинаково на Windows и Linux.

Перед публикацией проверьте установку и повторное обновление из `extracted/`
обоими упакованными установщиками в локальный путь с пробелами. Затем выполните
smoke и полный RED/GREEN-прогон с `--skill` на **распакованном** скиле и `--dir`
на отдельном потребительском Git-проекте без исходников БСП. Сверьте fingerprint
отчёта с manifest. PASS другого checkout или старого архива не заменяет эту
проверку. Сборка и проверки не создают тег и не публикуют релиз.

Результаты опубликованного v0.14: [проверка скачанных архивов и релиза](reports/bsp-skills/v0.14-published-verification.md), [качество кандидата и ограничения](reports/bsp-skills/v0.14-release-candidate-readiness.md). История v0.13 — [проверка готовности](reports/bsp-skills/v0.13-release-readiness.md).

### Поведенческий RED/GREEN-тест

Статические проверки подтверждают содержимое справочников, но не активацию
скила и качество ответа агента. Для этого используются корпус
`evals/cases.json`, машинно проверяемая матрица
`evals/reference-matrix.json` (`reference → eval case IDs`) и запуск Codex через
команду `cdx`. Пустой список в матрице явно фиксирует пробел поведенческого
покрытия; dry-run проверяет точное соответствие матрицы корпусу и всем 24
reference-файлам. Это преимущественно guided-корпус. Отдельные задания для
самостоятельной активации и отрицательных границ лежат в
`evals/activation-cases.json` с собственной
`evals/activation-reference-matrix.json`; их результаты нельзя складывать с
основным gate в одну метрику.

В сценарии классификаторов `error_handling_rule` проверяет действительную
обработку `КодОшибки` после указанного `source_call` в одном BSL-фрагменте.
Пустой код и `ОбновлениеНеТребуется` не должны приводить к исключению.
Ограниченный анализ поддерживает присваивания, aliases и ветвления
`Если`/`ИначеЕсли`/`Иначе`; он не исполняет BSL и не заменяет компилятор.
Комментарии, строки-заглушки и отдельный фрагмент с обработчиком не служат
свидетельством обработки. Неподдерживаемые условия и управляющие конструкции
не объявляются проверенными. Результат виден в `error_handling_rule_passed`
и учитывается в числе выполненных требований.

```bash
# Быстрый прогон одного сценария: без скила и со скилом.
python ci/run_skill_evals.py --case message-bound-to-field --runs 1

# Полный прогон: явно фиксируем модель и reasoning effort.
python ci/run_skill_evals.py --runs 3 --jobs 6 --model gpt-6-luna --reasoning-effort medium

# Возобновляемый прогон с теми же параметрами и фиксированным путём отчёта.
python ci/run_skill_evals.py --runs 3 --jobs 6 --model gpt-6-luna --reasoning-effort medium --output .tmp/release-eval.json
python ci/run_skill_evals.py --runs 3 --jobs 6 --model gpt-6-luna --reasoning-effort medium --output .tmp/release-eval.json --resume
```

Fingerprint скила вычисляется по точным байтам и относительным POSIX-именам
в едином регистрозависимом порядке на всех ОС. Отчёты со старым платформенным
порядком сортировки не переносятся автоматически на новую поставку.

При `--resume` runner проверяет модель, корпус, скил, SHA256 самого runner,
число повторов, фазы и пороги; сохраняет уже завершённые качественные результаты
и повторяет только отсутствующие, незавершённые или инфраструктурно упавшие
запуски. Отчёт атомарно обновляется после каждого `case × phase × run`.
Текущая схема отчёта — v4: старые отчёты нельзя возобновлять с новой семантикой.
Инфраструктурные причины (`quota/rate limit`, authentication, network, timeout,
недоступная модель, sandbox policy и повреждённая кодировка tool output)
отделены от ошибок качества ответа.

`--jobs` задаёт предельное число одновременных запусков `cdx`; значение `6`
сокращает длительность полного прогона, не меняя число повторов и пороги.
Модель по умолчанию — `gpt-5.6-luna`. Для проверки v0.14 использовался
явный `--model gpt-6-luna --reasoning-effort medium`, как в командах выше.
Результаты разных моделей хранятся раздельно и не объединяются в один gate.

По умолчанию RED и GREEN выполняются в каталоге разработчика `src/`.
Для проверки потребительского проекта используйте `--dir PATH`: исходников
БСП и локальной документации разработчика в нём быть не должно. В GREEN
runner временно устанавливает только `bsp` в `PATH/.agents/skills/bsp`, затем
удаляет staging; существующий `bsp` не перезаписывается. Python cache не
копируется и не входит в fingerprint скила. Глобальные каталоги скилов не
изменяются. Сырые JSONL-события, ответы и отчёт
сохраняются в `.tmp/bsp-evals/`.

Runner изолирует запуск флагами `--ignore-user-config`, `--ignore-rules` и
`--sandbox read-only`. На Windows он дополнительно задаёт
`windows.sandbox="unelevated"`: без явного backend после отключения
пользовательского config Codex блокирует даже команды чтения. Такие отказы
помечаются в отчёте как `tool_policy_blocked` и считаются инфраструктурными
ошибками, даже если процесс `cdx` вернул код 0. Эти флаги не отключают
сторонние скилы и plugins хоста; их наличие может влиять на выбор модели.

Windows-запуск также отключает профиль PowerShell (`allow_login_shell=false`),
фиксирует UTF-8 для Python и передаёт одинаковые для RED/GREEN инструкции
читать UTF-8-файлы через `rg`/Python. `Get-Content -Encoding UTF8` задаёт
кодировку файла, но не stdout: OEM-вывод PowerShell может быть испорчен при
декодировании внутри Codex. Это касается и pipeline `rg | Select-String`:
PowerShell может заново закодировать результат native reader. Поэтому даже
при UTF-8-инструкции проверяется фактический вывод каждой команды.
Символы замены `U+FFFD` в выводе успешной команды
сохраняются как `tool_output_decode_errors`; запуск классифицируется как
`tool_output_encoding` и требует повторения, даже если ответ прошёл scorer.
Исключение — один символ замены непосредственно у штатного маркера обрезки
Codex `... N bytes omitted ...`: UTF-8 может разрываться на границе фрагмента.
Повреждение остальных частей вывода это исключение не скрывает.
Параметры Codex и developer-инструкция выше принадлежат runner и не входят
в поставку. Сам скил содержит ASCII-bootstrap и правила UTF-8-чтения references,
но не меняет конфигурацию Codex. Результаты ассистированного RED/GREEN-прогона
не подтверждают обычное неассистированное поведение на Windows.
Кроме того, приватный каталог `TemporaryDirectory` может быть недоступен
restricted token: до прогона нужно проверить реальное чтение файлов и cwd,
а не только успешное обнаружение скила в каталоге Codex.

Основные метрики: доля прошедших сценариев, неявная активация по наблюдаемому
команде чтения staged `SKILL.md`/reference с непустым выводом в JSONL-трейсе
(не перечислению файлов и не доказательству использования всего текста),
точность методов, вызовы
служебного API и модулей `*Переопределяемый`, запрещённые антипаттерны и расход
токенов. Ненулевой код означает, что GREEN не достиг заданных порогов.

## Лицензия

[MIT](LICENSE). Copyright (c) 2026 Чекменев Дмитрий Алексеевич.
