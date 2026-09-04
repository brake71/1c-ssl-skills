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
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --ref v0.10
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
.\install.ps1 -Agent Codex -Ref v0.10
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
`bsp-skill-vX.Y.tar.gz`. Внутри находится `skills/bsp`, который можно вручную
скопировать в каталог скилов агента.

Из клона:

```bash
git clone https://github.com/brake71/1c-ssl-skills.git
cp -r 1c-ssl-skills/skills/bsp ~/.claude/skills/
```

## Состав

Репозиторий поставляет один umbrella-скил `skills/bsp/`:

- `SKILL.md` — маршрутизация по задачам;
- `references/` — 24 тематических справочника со сценариями, сигнатурами,
  примерами и антипаттернами;
- `scripts/bsp_api.py` — проверка методов, регионов и диапазонов строк по XML-выгрузке
  конфигурации БСП.

Reference-файлы не являются отдельными скилами. Агент сначала загружает
`bsp/SKILL.md`, затем выбирает один подходящий reference. Скил рассчитан на
БСП 3.1.11; для другой версии сигнатуры и стабильность API нужно перепроверять
по исходникам соответствующей поставки.

## Проверка API по исходникам

Скрипт принимает обязательный путь к корню выгрузки конфигурации с каталогом
`CommonModules/`:

```bash
python skills/bsp/scripts/bsp_api.py method СообщитьПользователю --src src/cf
python skills/bsp/scripts/bsp_api.py module ОбщегоНазначения --src src/cf
python skills/bsp/scripts/bsp_api.py modules --src src/cf
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

### Поведенческий RED/GREEN-тест

Статические проверки подтверждают содержимое справочников, но не активацию
скила и качество ответа агента. Для этого используются корпус
`evals/cases.json`, машинно проверяемая матрица
`evals/reference-matrix.json` (`reference → eval case IDs`) и запуск Codex через
команду `cdx`. Пустой список в матрице явно фиксирует пробел поведенческого
покрытия; dry-run проверяет точное соответствие матрицы корпусу и всем 24
reference-файлам.

```bash
# Быстрый прогон одного сценария: без скила и со скилом.
python ci/run_skill_evals.py --case message-bound-to-field --runs 1

# Полный релизный прогон; три повтора уменьшают влияние дрейфа модели.
python ci/run_skill_evals.py --runs 3 --jobs 6

# Возобновляемый прогон с фиксированным путём отчёта.
python ci/run_skill_evals.py --runs 3 --jobs 6 --output .tmp/release-eval.json
python ci/run_skill_evals.py --runs 3 --jobs 6 --output .tmp/release-eval.json --resume
```

При `--resume` runner проверяет модель, корпус, число повторов, фазы и пороги,
сохраняет уже завершённые качественные результаты и повторяет только
отсутствующие, незавершённые или инфраструктурно упавшие запуски. Отчёт
атомарно обновляется после каждого `case × phase × run`. Инфраструктурные
причины (`quota/rate limit`, authentication, network, timeout, недоступная
модель и sandbox policy) отделены от ошибок качества ответа.

`--jobs` задаёт предельное число одновременных запусков `cdx`; значение `6`
сокращает длительность полного прогона, не меняя число повторов и пороги.
Модель тестов зафиксирована как `gpt-5.6-luna`; при сравнении с другой моделью
её точный идентификатор можно передать через `--model`.

RED и GREEN выполняются в одном каталоге `src/`. В GREEN runner временно
устанавливает только `bsp` в `src/.agents/skills/bsp`, а затем удаляет staging.
Глобальные каталоги скилов не изменяются. Сырые JSONL-события, ответы и отчёт
сохраняются в `.tmp/bsp-evals/`.

Runner изолирует запуск флагами `--ignore-user-config`, `--ignore-rules` и
`--sandbox read-only`. На Windows он дополнительно задаёт
`windows.sandbox="unelevated"`: без явного backend после отключения
пользовательского config Codex блокирует даже команды чтения. Такие отказы
помечаются в отчёте как `tool_policy_blocked` и считаются инфраструктурными
ошибками, даже если процесс `cdx` вернул код 0.

Основные метрики: доля прошедших сценариев, неявная активация по наблюдаемому
чтению staged `SKILL.md`/reference в JSONL-трейсе, точность методов, вызовы
служебного API и модулей `*Переопределяемый`, запрещённые антипаттерны и расход
токенов. Ненулевой код означает, что GREEN не достиг заданных порогов.

## Лицензия

[MIT](LICENSE). Copyright (c) 2026 Чекменев Дмитрий Алексеевич.
