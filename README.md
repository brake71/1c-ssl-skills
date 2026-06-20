# 1С:БСП Skills

Коллекция скилов для AI-агента, работающего с конфигурациями 1С:Предприятие 8
на базе БСП 3.1.11. Каждый скил покрывает одну подсистему: даёт агенту карту
«общий модуль → метод», реальные сигнатуры и явные границы между
стабильным и служебным API.

## Зачем

БСП — это ~70 подсистем верхнего уровня и ~1600 общих модулей. Без
навигации агент выдумывает несуществующие модули (типичная галлюцинация —
`ОбщегоНазначенияСлужебный`), путает стабильный API со служебным и нарушает
конвенции суффиксов (`Клиент`/`Сервер`/`КлиентСервер`/`ВызовСервера`/
`ПовтИсп`/...). Скилы закрывают это: дают агенту проверенные маршруты,
фактические имена модулей и формальные запреты.

## Использование

Скилы написаны в формате [AgentSkills](https://agentskills.io) — файл
`SKILL.md` с frontmatter, в котором агенту сказано, когда подгружать скил
и какие скилы смежные. Поддерживаются:

- Claude Code — путь по умолчанию `~/.claude/skills/`
- OpenCode — скопировать `.claude/skills/` в проект или в
  `~/.config/opencode/skills/`
- любой другой harness, читающий `SKILL.md`

Архитектура — **4 кластерных umbrella-скила** с decision-tree роутингом.
`SKILL.md` кластера содержит дерево решений и направляет к нужному
leaf-скилу из `references/`. Начинать с загрузки кластерного скила, он
сам определит нужный leaf.

## Быстрый старт

### Вариант 1 — из релиза

На странице [Releases](https://github.com/brake71/1c-ssl-skills/releases)
доступен архив `bsp-skills-vX.Y.zip` только с каталогом `.claude/skills/`. Скачать, распаковать
и скопировать в свой проект:

```bash
unzip bsp-skills-v0.2.zip -d bsp-skills
cp -r bsp-skills/.claude/skills/bsp-* .claude/skills/
```

### Вариант 2 — клон репозитория

```bash
git clone https://github.com/brake71/1c-ssl-skills.git
# BSP-скилы лежат в .claude/skills/bsp-*/ внутри клона.
# Подключить к своему проекту — скопировать нужные кластеры:
cp -r 1c-ssl-skills/.claude/skills/bsp-core      .claude/skills/
cp -r 1c-ssl-skills/.claude/skills/bsp-data      .claude/skills/
cp -r 1c-ssl-skills/.claude/skills/bsp-ui-forms  .claude/skills/
cp -r 1c-ssl-skills/.claude/skills/bsp-ops       .claude/skills/
```

Взять все BSP-скилы разом (4 кластера):

```bash
cp -r 1c-ssl-skills/.claude/skills/bsp-* .claude/skills/
```

### Проверка

Задать агенту вопрос по любой подсистеме из таблицы ниже — в ответе
должны появиться реальные имена модулей и методов БСП 3.1.11, а не
выдуманные.

## Скилы

BSP-скилы — 4 кластерных umbrella + leaf-скилы в `references/` каждого
кластера. Кластерный `SKILL.md` содержит decision-tree роутинг к leaf-ам.


| Кластер (umbrella) | Назначение                                                                                                                                                                              | Leaf-скилы                                                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `bsp-core`                | Навигация, утилиты, фоновые задания, префиксы, обновление                                                                                         | `bsp-fundamentals`, `bsp-base-common`, `bsp-longs-and-jobs`, `bsp-prefixes`, `bsp-update`                                           |
| `bsp-data`                | Обмен данными, ЭП/МЧД, контактная информация, классификаторы, валюты/банки, внешние компоненты                     | `bsp-data-exchange`, `bsp-esign-mcd`, `bsp-contact-info`, `bsp-classifiers`, `bsp-currencies-banks`, `bsp-external-components`      |
| `bsp-ui-forms`            | Подключаемые команды, печать, свойства форм, мультиязычность, файлы/версии, дубли                                             | `bsp-commands-external`, `bsp-print-reports`, `bsp-forms-validation`, `bsp-multilang`, `bsp-files-and-versions`, `bsp-report-dedup` |
| `bsp-ops`                 | Пользователи/доступ, почта/SMS, бизнес-процессы, администрирование, резервное копирование, мониторинг, ПДн | `bsp-users-access`, `bsp-comms`, `bsp-bp-tasks`, `bsp-admin-tools`, `bsp-backup`, `bsp-perf-monitoring`, `bsp-protection-pd`        |

## Лицензия

[MIT](LICENSE). Copyright (c) 2026 Чекменев Дмитрий Алексеевич.
