# P0 после v0.14 — native preflight, не закрытие изоляции

Дата: 2026-10-08. **Статус P0: открыт.** Добавлен детерминированный аудит
`ci/probe_eval_isolation.py`; опубликованный скил, behavioral runner и пороги
не менялись. Это первый инструментальный шаг, не новый behavioral baseline.

## Что проверяется

- Отдельный потребительский Git-корень вне репозитория разработчика, без
  локальных BSP sources. Отчёт хранится вне consumer-корня и не перезаписывается.
- Каждый native app-server запускается с одним временным `CODEX_HOME`; туда не
  копируются config, инструкции, credentials и пользовательские скилы. Parent
  environment фильтруется allowlist системных переменных/путей: API keys,
  provider overrides, proxy credentials и integration tokens не передаются.
  После аудита home удаляется. Model turns не отправляются.
- Общие явные Windows/UTF-8 `-c` из `build_cdx_command` переиспользуются, но
  профиль **другой**: `native-preflight-clean-home-v1`, approval `never`,
  read-only, web search disabled; features plugins/remote_plugin/apps/hooks/
  memories/skill_mcp_dependency_install/shell_snapshot отключены.
- В каждом процессе через native RPC считываются effective config/layers,
  `skills/list` с `forceReload`, локальная plugin inventory и профиль
  ephemeral thread с `instructionSources`. Missing inventory, discovery/load
  errors, активные project config layers, MCP servers и загруженные файлы
  инструкций дают отказ. У native thread не запускается ни один turn.
- GREEN добавляет только `<consumer>/.agents/skills/bsp`. Проверяются точный
  путь, name/scope/enabled/pluginId и fingerprint байтов. Каталог прочих скилов,
  их metadata/content fingerprints, effective config, permissions и выбранные
  характеристики окружения должны совпадать. После cleanup повторно проверяется
  исходный RED-каталог. Существующий target и linked staging parents запрещены.
- В отчёт не попадают raw config, dependency URLs или credentials; сохраняются
  fingerprints и ограниченные метаданные. Raw stderr/native error text не
  сохраняется. При отсутствии native inventory preflight не заменяется
  самоотчётом модели или эвристическим поиском файлов.

## Реальные пробы

Codex CLI **0.160.0**, Windows, launcher `cdx.CMD`. Model setting
`gpt-6-luna`, effort medium фиксируют профиль, но **вызовов модели 0**.
Native schema изучена из установленного CLI, не из предполагаемых API.

Положительный consumer-корень:
`C:/Users/dchekmenev/Projects/bsp-isolation-probe` (отдельный Git-root).

```bash
python ci/probe_eval_isolation.py --dir C:/Users/dchekmenev/Projects/bsp-isolation-probe --model gpt-6-luna --reasoning-effort medium --output .tmp/p0-native-final-r2.json
```

**Native catalog gate PASS.** RED: пять system-скилов (`imagegen`,
`openai-docs`, `review-agent`, `skill-creator`, `skill-installer`) и user-скил
`retro`. GREEN: тот же каталог плюс один enabled repo-scoped `bsp`. После
cleanup каталог вновь равен RED; target отсутствует. Effective config,
plugin inventory и thread profile совпали между тремя snapshots.

Fingerprint скила:
`7a494f31bda067e95fefc6374cd0fdef5b64535075b3d949837ee58e8e073ac9` — те же
байты, что опубликованы в v0.14. Проверенная ревизия probe SHA256:
`1f6f086888babac1f46e5fee1b6305ee075b9ef0c34e9b0654f40254e186d470`.

Отрицательный контроль: отдельный consumer-корень
`C:/Users/dchekmenev/Projects/bsp-isolation-negative-20261008`, в котором есть
синтетический `.agents/skills/unrelated/SKILL.md`. Native probe завершилась
кодом **2**, причина `RED already discovers BSP or other project skills`.
Staged `bsp` не создавался, sentinel постороннего скила остался неизменным.
Отчёт: `.tmp/p0-native-negative-final-r2.json`.

Независимое ревью выявило передачу credentials через parent environment;
после исправления allowlist добавлены unit-регрессии и реальная положительная
проба с синтетическим `OPENAI_API_KEY`. Ключ отсутствует в environment native
процесса и в отчёте. Также проверены отказы для linked report paths и Windows
reparse points, включая Python без `Path.is_junction`.

Проверки: **137 unit-тестов PASS** (28 новых), API coverage 664/664 по 24
references, semantic 0 ERROR / 0 WARN, оба eval dry-run, py_compile и
`git diff --check` PASS. Native положительная проба выполнена повторно;
старые и новые отчёты не объединяются в behavioral gate.

## Чего результат не доказывает

1. Это snapshot отдельного app-server с disposable home, а не effective
   catalog реальных `exec`-процессов основного runner. Даже совпадение явных
   `-c` не доказывает равенство transport, config loading и runtime discovery.
   В JSON явно записано `exec_runtime_isolation_proven=false`.
2. Отключённые plugins и пустая локальная plugin inventory относятся только
   к диагностическому профилю. Это не утверждение, что у хоста глобально нет
   plugins, и не доказательство полного remote plugin catalog прежних прогонов.
3. Чистый `CODEX_HOME` не делает каталог пустым: пользовательский `retro`
   обнаруживается из `~/.agents/skills`. Проверяется равенство его байтов и
   metadata между фазами, а не отсутствие влияния на поведение модели.
4. Не проверялись prompt neutrality, доступность чтения файлов restricted
   token, качество ответа, активация скила или причинный эффект установки.
   Thread creation без turn не заменяет потребительский behavioral smoke.
5. Runtime drift между snapshot и модельным turn пока вообще не измеряется:
   turn отсутствует. Исторические v0.13/v0.14 отчёты не получают нового proof.

## Следующая итерация P0

Выбрать поддерживаемый способ получать catalog/config inventory **в том же
процессе, который выполняет behavioral turn**. Если для этого нужен
app-server transport, оформить отдельный профиль и baseline, не объявлять его
эквивалентным прежнему `exec`. Связать snapshots с конкретным run, отчётом и
resume fingerprint; затем выполнить RED/GREEN smoke `message-bound-to-field`
и новый baseline. Credentials и глобальные скилы не изменять; до этого
**P0 не закрывать**.
