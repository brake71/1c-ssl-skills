# P3: восстановление доступа к reference после P2

## Диагноз по сохранённой trace

Источник: `.tmp/native-guided-after-p2-r1-3x-artifacts/connected-command-hook-boundary.green.2.jsonl`
и исходный `.tmp/native-guided-after-p2-r1-3x.json`; оба остаются неизменными.

Модель успешно прочла проектный `.agents/skills/bsp/SKILL.md`, но построила
путь к `commands-external.md` от системного `skills/.system/imagegen/../bsp`.
Чтение завершилось ошибкой пути; последующий listing не является чтением.
Повторного чтения правильного абсолютного reference не было. Справка входила
в staged skill; требование выгрузки не было следствием отсутствия поставки.

В этом individual run `reference_evidence=[]`, `reference_read=false`.
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

Свежие behavioral результаты пока не получены. Старые majority PASS и
individual FAIL не изменяются и не заменяются unit-тестами. P1-покрытие и два
платформенных quality failure остаются отдельными задачами.
