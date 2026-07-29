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
# Codex: ~/.codex/skills/bsp
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --agent codex

# OpenCode: ~/.config/opencode/skills/bsp
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --agent opencode

# Произвольный каталог skills
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --target /path/to/skills
```

Чтобы установить конкретный тег или коммит, передайте `--ref`:

```bash
curl -fsSL https://raw.githubusercontent.com/brake71/1c-ssl-skills/main/install.sh | bash -s -- --ref v0.7
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
.\install.ps1 -Agent Codex -Ref v0.7
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
- `scripts/bsp_api.py` — проверка методов и регионов по XML-выгрузке
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
```

CI также проверяет компиляцию скриптов, обязательность `--src`, покрытие
references и локальные smoke-тесты обоих установщиков. Полная семантическая
проверка требует локальную выгрузку БСП и поэтому выполняется перед релизом
локально.

## Лицензия

[MIT](LICENSE). Copyright (c) 2026 Чекменев Дмитрий Алексеевич.
