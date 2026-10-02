# notifications - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 |
| Deployable(s) | clarity-api / clarity-worker / clarity-stream |
| Work package | phased |
| Owner | @clarity |
| Status | in-progress |
| Postgres schema | `notifications` |

## 1. Purpose
Template-only dispatch, preferences, quiet hours, delivery status.

## 2. Public interface (`public.py` facade)
| Method | Input | Output | Errors | Notes |
|---|---|---|---|---|
| `send_notification` | template_id, params, channel?, language?, msisdn?, case_id? | `NotificationRecord` | ValueError | Templates only |
| `get_status` | notification_id | record or None | - | - |
| `list_templates` | - | template ids | - | - |

## 3. HTTP endpoints
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/notifications/send` | Template-only send |
| GET | `/v1/notifications/status/{id}` | Delivery status |
| PUT | `/v1/notifications/preferences` | Language / channel / enabled |

## 4. Events
None yet (`notification.sent/delivered/failed` planned).

## 5. Data owned
In-memory notification records and preferences (prototype).

## 6. Permissions declared
None yet.

## 7. Config keys declared
| Key | Default | Description |
|---|---|---|
| `notifications.quiet_hours.start` | `21:00` | Quiet hours start |
| `notifications.quiet_hours.end` | `07:00` | Quiet hours end |
