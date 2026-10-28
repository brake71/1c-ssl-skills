# Планы по скилу БСП

**Действующий план развития:** [после локального кандидата v0.16](bsp-development-after-v0.13.md).
Первая activation-партия выполнена: **5/24 references**, 10 сценариев;
guided 81/81, activation 28/30 individual, все итоговые gates PASS.
После локального v0.16 в рабочем дереве встроен fixture/resume контроль P0.
P1 начата: `longs-and-jobs.md` проверен по источникам, добавлен в матрицу
(11 кейсов, 6/24 references). На новой границе полные guided/activation native
3× прошли итоговые gates: **27/27 · 78/81** и **11/11 · 31/33**; fixture/isolation
PASS. Пять individual FAIL той границы сохранены: прогресс прошёл 2/3,
один mixed-reader, ошибочный хук и два false negative evaluator. Последние
закрыты paired-тестами и двумя targeted native 1×. На изменённой границе
полный guided 3× **27/27 · 81/81 PASS**, но activation **10/11 · 28/33,
GREEN gate FAIL**: public/service кейс не активировался 2/3, strict read 6/7.
После узкой правки `SKILL.md` следующий activation 3×: **11/11 · 31/33**,
activation/read 24/24 и 21/21, но **forbidden gate FAIL** из-за платформенного
ответа с вызовом BSP; новый guided 3× не проводился. Отдельный `gpt-6-sol`
сохранил platform-only 3/3 RED и 3/3 GREEN; полный activation gate PASS,
но новая тема прогресса **0/3**. Профили не объединяются.
После paired-разбора прогресса и уточнения reference новый **sol** native
цикл на текущих байтах рабочего дерева завершён: activation **11/11 · 32/33**,
guided после resume только инфраструктурных слотов **27/27 · 80/81**, все
quality/fixture/isolation gates PASS. Два individual FAIL сохранены; релизный
на момент P5 архив ещё не был проверен, публикации не было.
[Первая targeted-проверка](../reports/bsp-skills/p1-progress-activation-followup.md) ·
[первая полная матрица](../reports/bsp-skills/p1-full-native-3x-followup.md) ·
[paired исправления](../reports/bsp-skills/p2-wording-and-context-followup.md) ·
[первый gate FAIL](../reports/bsp-skills/p2-full-native-gate-failure.md) ·
[scope-проверка и второй gate FAIL](../reports/bsp-skills/p3-neutral-api-scope-activation-followup.md) ·
[диагностика platform-only и другого профиля](../reports/bsp-skills/p4-platform-only-model-diagnosis.md) ·
[текущая sol-матрица и resume](../reports/bsp-skills/p5-sol-full-matrix-after-limit-recovery.md).

Основание текущего состояния: [локальная проверка v0.16](../reports/bsp-skills/v0.16-release-candidate-readiness.md).
На момент локального отчёта тег/push/публикация v0.16 не выполнялись. [Кандидат v0.15](../reports/bsp-skills/7b1abc7-release-candidate-readiness.md)
остаётся историческим evidence; эти локальные отчёты не доказывают
публикацию GitHub Release или скачанных release assets.
[Проверка опубликованного v0.14](../reports/bsp-skills/v0.14-published-verification.md)
остаётся историческим evidence, не проверкой v0.15.

Остальные файлы фиксируют ход уже завершённых этапов или рабочие материалы
для отдельных аудитов; старые пути `.claude/skills/bsp*`, несколько отдельных
`bsp-*` скилов и команды прежних runner не описывают нынешнюю поставку.
Нынешняя структура — **один** `skills/bsp/` с `references/` и `scripts/`.

| Документ | Назначение сейчас |
|---|---|
| [Улучшения v0.12 → v0.13](2026-08-30-bsp-skill-improvements.md) | История экспериментов и старых долгов; секции `Next` неактуальны |
| [План объединения 4 → 1](piped-humming-sutherland.md) | Архитектурная история, объединение выполнено |
| [Первоначальный roadmap](2026-06-06-bsp-skills-roadmap.md) и [чек-лист](2026-06-06-bsp-skills-checklist.md) | История создания отдельных скилов до объединения |
| [Spec авторинга references](bsp-authoring-spec.md) | Шаблон сценария и принципы источников; перед применением сверять пути и команды с `CLAUDE.md` |
| [Аудит references](bsp-references-audit-plan.md) | Исторический чек-лист аудита; статусы и пути не служат доказательством проверки текущего релиза |

Третьесторонние скилы в `.agents/skills/` доступны агентам Pi в этом проекте,
но не входят в `skills/bsp/` и не являются планом переноса их инструкций
в опубликованный скил.
