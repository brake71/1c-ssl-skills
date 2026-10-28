# P2: полный native 3× после правок scorer — activation gate FAIL

**Статус:** новая frozen граница после двух [paired-исправлений](p2-wording-and-context-followup.md); запуск завершён, но **не принят**. Это не релиз. Исходный результат не перезаписывался, quality attempts не повторялись. Полный P1 3× относится к другой границе и остаётся [историческим](p1-full-native-3x-followup.md).

## Входы и завершённые gates

`native-runtime-v1`, schema 7, `gpt-6-luna` / medium, `--runs 3 --jobs 6 --timeout 480`, `--bsl-src src/cf`, внешний consumer `C:/Users/dchekmenev/Projects/bsp-native-p0-fixture-consumer`. Тот же извлечённый v0.16 `--skill` fingerprint `9e023a29d78053c2db4b9503f4b234455344e5bf9ce81363f6b1a26faf3a496d`. Runner SHA-256 `922a72d5b3b9de1f84c6f9a71b26b32a293307e2f000e1f8fb3dec56c745253e`; guided corpus/matrix `428f28ed502cd09fb6381db31551494446fcc5a4e068ebe06296232c62f2ae5b` / `cd0f5a6908fd0f0c0dd1c64890768633f63d2b7f2a3110cf92de53ac9192d6bb`; activation `4312961411ec83005940a248c0222b7042f0f599111bdbd38a94107e5af183f2` / `65d8ac951df5e4efa27f8099c2c05059f3805603d8b69c9cb2ef929da0110cc9`. Текущие байты runner/corpora/matrices совпали с отчётами. Источник БСП не в consumer, а только в индексе evaluator.

| Корпус | RED majority | GREEN majority / individual | GREEN activation | GREEN strict exact-read | GREEN false activation | Quality / fixture / isolation |
|---|---:|---:|---:|---:|---:|---|
| Guided, 27 | 1/27 | **27/27 · 81/81** | 78/78 | 78/78 | 0/3 | **PASS / PASS / PASS** |
| Activation, 11 | 3/11 | **10/11 · 28/33** | 22/24 positive runs, 7/8 majority | 18/21 positive runs, 6/7 majority | 0/9 | **FAIL / PASS / PASS** |

Activation gate причина: `reference_read_rate must be 100%, got 85.7%`. Оба отчёта complete=true, 3 runs на каждый выбранный case в RED и GREEN; infrastructure/incomplete/policy-blocked 0. GREEN invalid/unsafe/forbidden BSP calls 0. Шесть prospective ordinary-fixture checkpoints в обоих отчётах совпадают с baseline, native isolation PASS, staged skill после cleanup отсутствует. Эти данные не доказывают корректность BSL компиляцией или исполнением.

## Пять individual GREEN FAIL (четыре кейса)

- `neutral-public-api-boundary` #1–2: **не активировали BSP**, `fundamentals.md` не прочитан. В ответах есть верное общее предупреждение о служебном интерфейсе/серверном контексте, но нет явного рекомендованного региона `ПрограммныйИнтерфейс`. Это два содержательно неполных ответа и пропущенный scope-before-open. #3 прошёл с точным чтением. **Именно этот кейс** не достиг majority/read gate.
- `neutral-print-registration` #3: activation/read PASS, но вместо менеджера `Документы.Счет` в `Настройки.ОбъектыПечати` добавлен `Метаданные.Документы.Счет`. В `bsp3111_md/003_глава_3_настройка_и_использование_подсистем_при_разработке_к.md` (локальный фрагмент регистрации) и в `src/cf/CommonModules/УправлениеПечатьюПереопределяемый/Ext/Module.bsl` добавляются менеджеры (`Документы.*`); reference `print-reports.md` прямо определяет элементы массива как менеджеры. Это не повод принимать метаданные по расширенному regex. #1–2 прошли.
- `neutral-rls-field-message` #1: ответ на уровне scorer quality PASS и skill активирован, но **оба declared references не доказаны**. Raw успешные `rg` вызываются с относительными `references/base-common.md` и `references/users-access.md` (не с точными `.../.agents/skills/bsp/references/...`), поэтому strict per-file read=false. Не считать output или один `SKILL.md` достаточным подтверждением. #2–3 прочитали оба файла и прошли.
- `neutral-platform-exchange-registration` #2: BSP не активирован (граница пройдена), но предложен `ПланыОбмена.ИмяВашегоПлана.ЗаписатьИзменения(...)` вместо требуемого `...ЗарегистрироватьИзменения(...)`. Это платформенная ошибка ответа, не ложная BSP-активация и не повод менять критерий. #1 и #3 прошли.

Новые GREEN `neutral-background-progress` и `other-version-api-boundary` — по 3/3; printing 2/3, platform-only 2/3. Замена двух прежних false negative не доказывает улучшение генерации ответов: новая выборка случайна, сам payload прежний. Факт **gate FAIL** блокирует утверждение о готовности новой матрицы независимо от guided PASS.

## Дальше

Не возобновлять и не повторять quality slots этого отчёта. Рассмотреть узкую правку router description/scope для нейтрального вопроса об экспортной функции в служебном интерфейсе с paired negative controls для platform-only; удостовериться, что путь к `fundamentals.md` прочитан, а не угадан. Отдельно проверить предсказуемость absolute reference fallback для RLS при сохранении strict read rule. Print/platform — исправлять инструкцию или сценарий только при источниковом evidence, не расширять scorer ради PASS. После любой новой правки — новая frozen граница и полная matrix 3×; tag/push/release только по отдельному разрешению. Следующая [scope-проверка](p3-neutral-api-scope-activation-followup.md) закрыла пропуск public/API, но обнаружила новый forbidden gate FAIL: не считать исходный FAIL исчезнувшим задним числом.

Локальные неизменённые артефакты: `.tmp/p2-guided-full-3x.json` и `-artifacts/`; `.tmp/p2-activation-full-3x.json` и `-artifacts/`. Вывод процесса activation завершился с exit 1 из-за качества, не из-за инфраструктуры.
