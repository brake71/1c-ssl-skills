---
name: bsp-ops
description: "Users/access, email/SMS, business processes, admin tools, backup, monitoring, personal data in 1C BSP"
metadata:
  scope: bsp
  version: "3.1.11+"
  layer: umbrella
  leaf_skills:
    - bsp-users-access
    - bsp-comms
    - bsp-bp-tasks
    - bsp-admin-tools
    - bsp-backup
    - bsp-perf-monitoring
    - bsp-protection-pd
---

# BSP Operations

Routing skill for operational BSP subsystems. Read the decision tree,
determine the correct leaf skill, then load `references/<leaf>.md` for
full API details.

## When to use

Task involves BSP operational subsystems: users, access, communications,
business processes, admin tools, backup, monitoring, or personal data.

Determine the leaf skill by trigger words (first match wins):

1. **bsp-users-access** — user, Пользователи, access,
   УправлениеДоступом, role, RLS, administrator,
   ВнешниеПользователи, ТекущийПользователь,
   доступ, права, роль
2. **bsp-comms** — email, Почта, SMS, ОтправкаSMS,
   ШаблоныСообщений, chat, Обсуждения, 1C:Dialogue,
   РаботаСПочтовымиСообщениями, Взаимодействия,
   send email, send SMS, message template
3. **bsp-bp-tasks** — business process, БизнесПроцессы,
   task, Задача, redirect task, overdue,
   БизнесПроцессыИЗадачи, execute task, leading task
4. **bsp-admin-tools** — connection lock, ЗавершениеРаботыПользователей,
   delete marked, УдалениеПомеченныхОбъектов,
   scheduled deletion, active connections,
   administration parameters, put session to termination
5. **bsp-backup** — backup, РезервноеКопированиеИБ,
   auto backup, backup schedule, next backup date,
   backup settings, backup form
6. **bsp-perf-monitoring** — performance, ОценкаПроизводительности,
   key operation, monitoring center, ЦентрМониторинга,
   benchmark, замер, timing, business statistics
7. **bsp-protection-pd** — personal data, ЗащитаПерсональныхДанных,
   152-FZ, consent, data subject, ПДн,
   разрушение персональных данных, subject consent

## Leaf skills

| Leaf | File | Brief |
|------|------|-------|
| bsp-users-access | references/bsp-users-access.md | Users, access control, RLS, roles |
| bsp-comms | references/bsp-comms.md | Email, SMS, chat, message templates |
| bsp-bp-tasks | references/bsp-bp-tasks.md | Business processes, tasks, overdue |
| bsp-admin-tools | references/bsp-admin-tools.md | Connection locks, deletion, admin |
| bsp-backup | references/bsp-backup.md | Infobase backup, schedules |
| bsp-perf-monitoring | references/bsp-perf-monitoring.md | Performance benchmarks, monitoring |
| bsp-protection-pd | references/bsp-protection-pd.md | Personal data protection, consent |

## Cross-cluster routing

Ops subsystems overlap with other clusters in several places:

| Trigger | Go to |
|---------|-------|
| print a user list / access report, attach file to a task, form property on a user form | `bsp-ui-forms` |
| exchange user/access data between nodes, sign an access-grant with ЭП | `bsp-data` |
| safe storage of email/SMS credentials, common message-to-user, serialization of access settings | `bsp-core` → `bsp-base-common` |
| run heavy backup / deletion / monitoring in background (`ДлительныеОперации`) | `bsp-core` → `bsp-longs-and-jobs` |
| schedule a backup or deletion job (`РегламентныеЗадания`) | `bsp-core` → `bsp-longs-and-jobs` (for the API), but the *handler* registration stays in `bsp-backup` / `bsp-admin-tools` |

**Ambiguous keywords** (first match wins, but consider both clusters):

- `Задача` (task) in a business-process context → stay here (`bsp-bp-tasks`).
  `Задача` in a `РегламентныеЗадания` context → `bsp-core` →
  `bsp-longs-and-jobs`. The two are different: `Задача` is a business-task
  object, `РегламентноеЗадание` is a scheduled job.
- `РезервноеКопирование` backup *schedule* is here (`bsp-backup`), but the
  actual background execution goes through `ДлительныеОперации` /
  `РегламентныеЗадания` (core). If the task is «configure when backups run»,
  stay; if it is «the backup job itself is stuck», check core + ops.
- `УдалениеПомеченныхОбъектов` (here, ops) vs `ПоискИУдалениеДублей`
  (ui-forms cluster): both delete objects, but dedup is a UI-driven merge,
  while `УдалениеПомеченных` is a scheduled cleanup. Match by intent.

If no trigger matches, fall back to `bsp-fundamentals` and locate the
subsystem by the module map.

## Search tools

Use `scripts/bsp_ops_search.py` to look up methods and modules
in the target repository's configuration export:

```bash
python scripts/bsp_ops_search.py method ТекущийПользователь --src <path/to/cf>
python scripts/bsp_ops_search.py module Пользователи --src <path/to/cf>
python scripts/bsp_ops_search.py modules-by-subsystem Пользователи --src <path/to/cf>
python scripts/bsp_ops_search.py detect --src <path/to/cf>
```

`--src <path>` is **required**: path to the configuration export root
(directory containing `CommonModules/`). No auto-detection — the agent
must pass the path explicitly. If the path is invalid or has no
`CommonModules/` subdir, the script exits with a non-zero code.
