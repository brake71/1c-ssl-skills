# P4: platform-only блокер — replay и отдельный профиль модели

**Статус:** read-only диагностика уже сохранённых `gpt-6-luna` outcomes, регрессия на два неверных ответа и **новый отдельный** native-профиль `gpt-6-sol`/medium. Скил, eval-корпус и пороги не менялись; старые FAIL не возобновлялись. Ни один профиль пока не подтверждён как готовый к релизу.

## Что было красным без новых model calls

`neutral-platform-exchange-registration` просит платформенный механизм **без активации BSP**. В трёх завершённых `gpt-6-luna` full cohorts на совпадающем prompt/case criterion:

| Сохранённый cohort | RED individual | GREEN individual | BSP activation в GREEN |
|---|---:|---:|---:|
| `.tmp/p1-activation-full-3x.json` | 2/3 | 3/3 | 0/3 |
| `.tmp/p2-activation-full-3x.json` | 1/3 | 2/3 | 0/3 |
| `.tmp/p3-activation-full-3x.json` | 1/3 | 2/3 | 0/3 |

Итого **RED 4/9**, **GREEN 7/9** в трёх раздельных выборках; не использовать как один эксперимент с причинной оценкой скила — runner/corpus/payload менялись, хотя platform-only критерий не менялся. Нет evidence, что BSP был прочитан или активирован в любом из этих platform-only GREEN запусков. Ошибки возникали и в RED: `ЗаписатьИзменения(...)` вместо требуемого метода; в GREEN наблюдались `ПланыОбмена.ИмяВашегоПлана.ЗаписатьИзменения(...)` и `ОбменДанными.ЗарегистрироватьИзменения(...)`.

Проверяемый tight loop: `python -m unittest discover -s tests -p 'test_activation_expansion.py' -v` — `test_platform_exchange_failure_is_not_a_false_activation_issue` теперь защищает оба наблюдавшихся неверных кода (проверяемая ошибка: wrong method/forbidden BSP call), принимает прежний положительный `ПланыОбмена[ИмяПлана].ЗарегистрироватьИзменения(...)` и отвергает ложную BSP-активацию. Тест PASS; это регрессия scorer на сохранённые механизмы, **не исправление поведения модели**. Источник правильного платформенного механизма дополнительно подтверждён многочисленными вызовами `ПланыОбмена.ЗарегистрироватьИзменения(Узел, Объект)` в read-only `src/cf/CommonModules/ОбменДаннымиXDTOСервер/Ext/Module.bsl` и `src/cf/CommonModules/ОбновлениеИнформационнойБазы/Ext/Module.bsl`. Локальная Knowledge Vault (`X:/knowledge-vault/kb/concepts/1c-integrations-rmq-docflow-odata.md`) также перечисляет платформенный вариант; это вторичный контекст, не API-справочник поставки. Незначимые имена узлов/ссылок в ответах не являются причиной двух наблюдавшихся отказов.

## Независимая проба `gpt-6-sol` на том же frozen payload

Отдельный модельный профиль, `native-runtime-v1`, medium, `--skill skills/bsp`, `--bsl-src src/cf`, тот же внешний consumer, три RED и три GREEN запуска платформенного кейса: `.tmp/p4-platform-model-sol-3x.json`. Skill SHA-256 `21e36a2f80535d3e8f6f4d937a8949953bf9ab104377cad900ec24d8086ba06d`; runner `922a72d5b3b9de1f84c6f9a71b26b32a293307e2f000e1f8fb3dec56c745253e`. **RED 3/3, GREEN 3/3** correct; false BSP activation **0/3**, fixture/isolation/quality PASS. Единственная выборка не даёт гарантии и не стирает лунные FAIL.

Полный отдельный activation 3× на `gpt-6-sol` (`.tmp/p4-activation-model-sol-full-3x.json`) при **тех же** skill/runner/corpus/matrix fingerprints и consumer: RED **5/11 majority**, GREEN **10/11 majority, 29/33 individual**, positive activation **8/8 majority, 23/24 individual** (version boundary один раз не активирован), exact-read **7/7 majority, 21/21 individual**, negatives **0/9 false activation**. GREEN forbidden/invalid/unsafe 0, fixture/isolation/overall gates PASS; infrastructure/incomplete 0. **Но** `neutral-background-progress` провалился **0/3**: #1–2 показывают прогресс и включённый флаг, но клиентские fences не помечены `&НаКлиенте`; #3 помечает клиентский fence, но серверный фрагмент без оболочки `Функция ... Экспорт`, что не удовлетворяет текущему критерию. #3 — возможное расхождение критерия с запросом «фрагмент внутри выполняемой функции», **не** автоматический PASS. Отдельно version boundary #1 дал отказ от уверенной сигнатуры без BSP activation и поэтому FAIL как активируемая граница. GREEN gate PASS отражает агрегатные пороги, но **не** majority каждой темы; 0/3 в новой P1-теме неприемлемо объявлять проверенным покрытием.

## Решение и граница

Простая замена модели устраняет наблюдавшийся platform-only FAIL в этой малой выборке, но создаёт непроверенную/неустойчивую рекомендацию по прогрессу и отдельный activation FAIL. Не принимать модель `gpt-6-sol` вместо `gpt-6-luna` по одному платформенному сценарию или по агрегатному gate. Не менять `should_trigger=false`, не расширять скил на platform-only, не снижать `forbidden_hits=0`, не переписывать исторические raw verdicts и не гонять исходные quality slots до успеха.

Следующее решение до нового дорогого полного прогона: отдельно разобраться, действительно ли пользовательский запрос на **минимальный фрагмент** должен требовать полного объявления `Функция ... Экспорт`, с paired positive/negative controls; отличать это от реально отсутствующего `&НаКлиенте`. Если менять критерий — новая frozen граница, targeted, затем полная activation и guided на выбранном профиле. Для `gpt-6-luna` platform-only неправильный ответ остаётся наблюдаемой стохастической ошибкой базовой модели: без изменения non-skill инструкции/модели скил не может заставить неактивировавшегося агента выбрать верный платформенный вызов.

[Следующая frozen sol-матрица](p5-sol-full-matrix-after-limit-recovery.md) на других байтах scorer/skill после paired-разбора прогресса прошла оба native gates; исходные 0/3 этой границы не пересчитаны.

Публикация, tag/push/release не выполнялись. Dirty пользовательский submodule не менялся.
