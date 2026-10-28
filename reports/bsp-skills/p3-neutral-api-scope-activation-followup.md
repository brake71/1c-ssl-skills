# P3: нейтральный экспортный API — уточнение маршрута и новая матрица

**Статус:** локальный эксперимент после [P2 gate FAIL](p2-full-native-gate-failure.md). Изменён `skills/bsp/SKILL.md` (только описание триггера), прежний кандидат v0.16 и все старые raw-отчёты не изменены. **Новый полный activation GREEN gate тоже FAIL**, поэтому нет готового кандидата/публикации. Повторения quality до случайного PASS не было.

## Мотивировка и правка

В прежнем full 3× `neutral-public-api-boundary` дважды отвечал без открытия скила и обязательного `fundamentals.md`: нейтральная формулировка «конфигурация со стандартными подсистемами, экспортная функция, ВызовСервера, СлужебныйПрограммныйИнтерфейс» не называла БСП явно. Переданный скилу контекст — description до открытия файла; поэтому добавлен **один** узкий trigger для такого вопроса о стабильности и контексте клиента/сервера. Platform-only exclusion не удалён. Description остался ASCII (русские слова в JSON/YAML escape), 776 символов (<780), router сохранил 24 маршрута; новых references или API-утверждений нет. `tests/test_skill_bootstrap.py` контролирует scope-указатель и исключение platform-only.

При первой длинной редакции тест на лимит description честно дал FAIL; текст сокращён **до финальных байтов** до итоговых проверок. Результат targeted 1× на первой длинной редакции хранится отдельно и не считается evidence финальных байтов.

## Итоговые проверки и native evidence

- 231 unit tests PASS, API coverage **664/664**, semantic ERROR/WARN **0/0**, оба dry-run PASS. Финальный fingerprint skill: `21e36a2f80535d3e8f6f4d937a8949953bf9ab104377cad900ec24d8086ba06d`; runner/corpus SHA-256 сохранены в отчёте полного запуска.
- Финальный targeted 1× с `--skill skills/bsp`, native `gpt-6-luna` / medium, `--bsl-src src/cf`, тем же внешним consumer: `neutral-public-api-boundary` RED 0/1, GREEN **1/1** с activation и exact `fundamentals.md` read; `neutral-platform-exchange-registration` RED 0/1, GREEN **1/1** без BSP activation. Fixture/isolation/quality PASS. Локальные отчёты: `.tmp/p3-public-api-scope-final-1x.json`, `.tmp/p3-platform-negative-final-1x.json`.
- Новый полный activation native 3× (`--jobs 6 --timeout 480`, `.tmp/p3-activation-full-3x.json`, artifacts рядом): RED **3/11** majority; GREEN **11/11** majority, **31/33** individual; positive activation **24/24**, strict exact-reference read **21/21**, false activation negatives **0/9**; GREEN invalid/unsafe 0, **forbidden 1**. Fixture и isolation PASS, все 6 checkpoints совпали с baseline, staged skill удалён. **Quality gate FAIL: `forbidden_hits must be 0, got 1`**; runner завершился exit 1. Completion 66/66 outcomes, infrastructure/incomplete 0. Это новый corpus sample и изменённый payload, не причинное доказательство улучшения от одной фразы.

### Два индивидуальных FAIL нового activation

1. `neutral-rls-field-message` #1: skill активирован, оба declared references `users-access.md` и `base-common.md` по строгому правилу прочитаны; ответа с вызовом `УправлениеДоступом.ЧтениеРазрешено(...)` **нет** — вместо этого модель заявила, что подтверждённого библиотечного вызова не нашла. В `skills/bsp/references/users-access.md` метод и сценарий есть. Raw первый широкий `rg` по двум references вернул 659 строк, включая имя метода; последующий узкий поиск по иным возможным именам завершился `exit 1`, после чего ответ ошибочно заявил об отсутствии подтверждённого метода. Это ошибка поиска/понимания при наличии факта чтения, не разрешение снимать критерий. Остальные два запуска прошли.
2. `neutral-platform-exchange-registration` #2: skill не активирован, как и требуется для чисто платформенной задачи, но в коде предложен **`ОбменДанными.ЗарегистрироватьИзменения(...)`**, запрещённый BSP-вызов вместо `ПланыОбмена[ИмяПлана].ЗарегистрироватьИзменения(...)`. Это неправильный ответ и точная причина глобального forbidden gate FAIL. Platform-only задача должна оставаться без BSP activation; расширение триггера ради этого ответа нарушило бы границу. #1 и #3 прошли. Его нельзя исправлять ослаблением `forbidden_patterns` или повтором quality до случайного PASS.

Предыдущий full P2 3× с другим skill fingerprint дал activation gate FAIL из-за пропуска `fundamentals.md` в 2/3. На новой матрице этот кейс **3/3 activation/read/quality PASS**, но полный gate всё равно FAIL из-за другого сценария. Guided full 3× для нового payload **не запускался**: gate activation уже заблокирован, а полный guided предыдущего payload (81/81) не переносится на изменённые байты.

## Следующий шаг

Не объявлять ready/release. Разобрать RLS retrieval на raw command/output: exact read — необходимое, но не достаточное доказательство, что нужный фрагмент использован. Для платформенного вызова зафиксировать ограничение модели/корпуса: не лечить проблему активацией BSP для запроса о платформе; возможное решение (например, уточнение формулировки задачи или смена профиля) требует отдельного baseline и негативных контролей, а не корректировки scorer под FAIL. При выбранной новой границе сравнения снова выполнить static → targeted → полный activation и только при PASS полный guided и packaging. Tag/push/release требуют отдельного разрешения.
