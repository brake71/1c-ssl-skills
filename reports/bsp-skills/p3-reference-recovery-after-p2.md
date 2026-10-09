# P3: восстановление доступа к reference после P2

## Диагноз по сохранённой trace

Источник: `.tmp/native-guided-after-p2-r1-3x-artifacts/connected-command-hook-boundary.green.2.jsonl`
и исходный `.tmp/native-guided-after-p2-r1-3x.json`; оба остаются неизменными.

Модель успешно прочла проектный `.agents/skills/bsp/SKILL.md`, но построила
путь к `commands-external.md` от системного `skills/.system/imagegen/../bsp`.
Чтение завершилось ошибкой пути; последующий listing не является чтением.
Повторного чтения правильного абсолютного reference не было. Справка входила
в staged skill; требование выгрузки не было следствием отсутствия поставки.

В этом individual run `reference_evidence=[]`, `expected_reference_read=false`.
Исходные 26/26 означают majority по scoped cases, а не 78/78 individual reads.
Таким образом, здесь нет ложного засчитывания reference-read; прежняя
формулировка о положительном marker именно этого ответа была неверна.
Missing-code requirements правильно сохранили quality FAIL.

## Ограниченное исправление

- Router сначала привязывает installed root к уже прочитанному абсолютному
  `SKILL.md`; recovery выполняется из того же root, независимо от cwd.
- Добавлен конкретный Python UTF-8 fallback. Отдельный portable тест запускает
  его из системного каталога при наличии другого ложного BSP root и проверяет
  выбранный файл, Unicode/пробелы и ошибку действительно отсутствующего файла.
- Evaluator распознаёт literal `Path(...).parent / 'references' / 'file'`,
  только когда прочитанный текст достигает top-level print. Это не выполнение
  произвольного Python для извлечения evidence.

Отдельный синтетический контрпример подтвердил соседнюю ошибку evidence:
`rg` не прочёл ожидаемый reference, но следующий listing сделал общий exit 0;
его непустой output ошибочно считался чтением. Извлечение теперь исключает
цели, явно названные известным reader diagnostic. Сбой другой цели не скрывает
успешное чтение; независимое последующее чтение восстанавливает evidence.
Это ограниченная защита, не доказательство полного происхождения каждого
фрагмента stdout составной команды и не доказательство понимания сценария.

## Проверки перед свежим behavioral run

174 unit tests PASS; coverage 664/664 в 24 references; semantic 0 ERROR / 0 WARN;
guided/activation dry-run, py_compile и diff check PASS. Регрессии покрывают
реальный неправильный системный путь, masked exit, Windows/Python/PowerShell
ошибки и отсутствие подавления другого target. Original synthetic repro теперь
возвращает пустой evidence. Для fallback отдельно наблюдался RED на прежнем
AST extractor, затем GREEN после поддержки literal parent/join.

## Свежие native результаты на `5a4a338`

Модель `gpt-6-luna`, effort `medium`, timeout 480, jobs 6. Каждый runner
использовал отдельный report/private home; стадии выполнялись последовательно
в прежнем нейтральном consumer. Profile только `native-runtime-v1`.

| GREEN stage | Majority | Individual PASS | Чтение назначенного reference, individual |
|---|---:|---:|---:|
| message-bound-to-field smoke | 1/1 | 1/1 | 1/1 |
| connected-command-hook-boundary targeted | 1/1 | **2/3** | 3/3 |
| Guided 27 × 3 | 27/27 | **80/81** | 77/78 scoped runs |
| Activation 6 × 3 | 5/6 | **15/18** | 6/6 scoped runs |

Оба gate PASS во всех четырёх отчётах; GREEN проверяемые invalid/unsafe/forbidden
БСП и process/infra failures 0. Полный guided: positive activation 78/78;
reference-read majority 26/26. Activation: positive activation 9/9 (3/3 cases),
reference-read majority 2/2, **false activation 1/9** negative runs.

Сохранены пять отдельных GREEN FAIL, без quality retries/resume:

- Targeted hook #3: справка прочитана, но каркас имеет два параметра вместо
  четырёх, отсутствует `Команда.Вид = "СверкаОплаты"`. Это ошибка ответа после
  чтения, не проблема доступа. В полном guided тот же hook прошёл 3/3;
  это независимые результаты, не замена targeted FAIL.
- Guided exchange-register-changes #2: проверки ответа прошли, но обязательный
  `data-exchange.md` не прочитан. Модель ответила как на platform-only задачу,
  хотя пользователь спрашивал о публичном API БСП. Отказ сохранён; согласованность
  маршрута «API review versus platform-only» требует отдельной проверки.
- Activation neutral-platform-exchange-registration #2/#3: не выполнено
  требование `ЗарегистрироватьИзменения(...)`, без активации BSP. Это прежний
  класс платформенных ошибок, его исправление не заявляется.
- Activation neutral-form-caption #1: ответ корректен, но модель прочла router
  для чисто платформенной задачи; negative activation requirement не выполнен.

В шести свежих GREEN hook runs ошибочный root `imagegen/../bsp` не повторился;
назначенный reference прочитан 6/6. Это наблюдение выборки, не гарантия
безошибочного чтения/понимания всех будущих ответов. Первичная сводка агента
ошибочно назвала targeted hook 3/3 PASS; parent сверил individual score и
сохранил **2/3**, а также пропущенную в сводке ложную caption activation.

Отчёты и соседние `-artifacts/`/`.log`:

- `.tmp/native-reference-recovery-smoke.json`
- `.tmp/native-reference-recovery-hook-3x.json`
- `.tmp/native-reference-recovery-guided-3x.json`
- `.tmp/native-reference-recovery-activation-3x.json`

## Независимое завершение

Parent повторно вычислил runner/helpers/skill/corpus/matrix fingerprints и
isolation reasons по всем четырём отчётам: совпадение и PASS. Исходная auth
account identity совпадает с pre-run receipts; побайтовое сравнение auth до/после
не было снято, поэтому полная неизменность его содержимого не утверждается.
Проверка известных credentials по **832** новым report/artifact/log файлам:
совпадений 0. Staged BSP удалён, оставшихся private runtime homes 0.
Receipts: `.tmp/reference-recovery-parent-verification.json`.

Отдельный offline audit 198 сохранённых P2 runs не изменил ни activation,
ни reference-read evidence при новом extractor. Это replay, не model/isolation
run; исторические файлы и FAIL не переписаны. Receipt:
`.tmp/reference-recovery-historical-evidence-audit.json`.

174 unit tests и API 664/664 остаются PASS. Корпуса, матрицы и пороги не менялись;
P1 reference coverage остаётся 2/24. Следующие узкие задачи: hook skeleton
после успешного чтения, guided BSP API review/platform scope и false caption
activation. Платформенные ошибки рассматриваются отдельно. Push/release нет.
