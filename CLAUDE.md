# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this app is

A Django 5.2 web app (single app: `tracker`) that tracks a faulty field part's journey — engineer → (optional regional warehouse) → main warehouse → service desk → electronics → final disposition (back to stock / OEM / scrapped). Every login has exactly one role, and the role determines which home page they see and what actions are available. See `documents/1_APPLICATION_OVERVIEW.md` for the full plain-language walkthrough of the material flow and `documents/2_USER_MANUAL.md` for screenshots of each page.

## Commands

Local (non-Docker) dev, from repo root:
```
python manage.py runserver
python manage.py migrate
python manage.py makemigrations tracker
python manage.py test tracker          # tracker/tests.py is currently an empty placeholder
```

Docker (used for deployment, e.g. EC2):
```
docker compose up -d --build
docker compose logs -f
```
`docker/entrypoint.sh` waits for the DB port to open, then runs `migrate`, `collectstatic`, and starts gunicorn (`config.wsgi:application`) on port 8000. Restart policy is `unless-stopped`.

There is no configured linter/formatter in this repo — don't assume one.

## Configuration

Django settings (`config/settings.py`) import `config/settings_local.py` for defaults, then let env vars override every value — this is deliberate so the bare-metal Windows dev setup keeps working untouched while Docker/EC2 sets env vars instead. `settings_local.py` and `.env` are both gitignored (they hold real secrets/hostnames) and must be created directly on each machine/server; `.env.example` documents the expected keys.

There are **two separate databases**, both MySQL:
- `default` (`fault_tracker`) — everything this app owns and writes (users, dispatches, status history).
- `clappia` — a read-only external database (another team's system) holding the source service-ticket data. `tracker/db_router.py` (`ClappiaRouter`) pins the `ClappiaData` model to this connection and blocks migrations against it — never add write logic against `ClappiaData`.

## Architecture

Everything lives in one Django app, `tracker/`:
- `models.py` — `User` (custom auth model, `managed=False`, maps to an existing `users` table; passwords are stored/compared as plaintext, not hashed — see `check_password`), `ClappiaData` (read-only, external ticket data), `Dispatch`/`DispatchItem` (a dispatched batch and the individual physical parts in it), `DispatchItemStatusEvent` (append-only history log — `DispatchItem.status` is only the current value; this table is the source of truth for a part's full history and powers the admin "Material Lookup" search).
- `backends.py` — one `RoleBackend` subclass per role (`EngineerBackend`, `RegionalWarehouseBackend`, `WarehouseBackend`, `ServiceDeskBackend`, `ElectronicsBackend`, `AdminBackend`), each authenticating only against users with that specific `role`. Registered in `AUTHENTICATION_BACKENDS` in that order.
- `services.py` — shared logic that doesn't belong to one page, notably `get_material_lines_for_engineer` (unpivots a `ClappiaData` row into up to 5 dispatchable `MaterialLine`s: Power Card, Control Card, and up to 3 generic "material" slots) and `is_motor_or_pump` (keyword-matches a material name to route it down the repair/OEM path instead of tested-OK/dispatch). Only tickets on/after `DATA_CUTOFF_DATE` are considered eligible for dispatch — `ez_service` holds years of older/legacy rows that must stay excluded.
- `views.py` — one View class per role home page plus one `...ActionView` per role for its POST actions (Warehouse, MainWarehouse, ServiceDesk, Electronics, AdminUsers). This is where per-role branching and status transitions happen.
- `forms.py` — validation for each action's popup form (e.g. Electronics' diagnostic checklist, Add User).
- `urls.py` — one path per home page and per action endpoint; `HomeDispatchView` at `/` is the role-based landing router.
- `templates/tracker/` — one template per role home page, plus `admin_*.html` for the four Admin Dashboard sections (Dashboard Overview, User Management, Reports & Analytics, Material Lookup) and `admin_base.html`/`base.html` shells.
- `static/tracker/` — one `.js` file per page family handling popups, table filter/sort, and row expansion (plain JS, no framework/bundler).

### Things added in V1.3 (since V1.2) that are easy to trip over

- **Time zone:** `TIME_ZONE = 'Asia/Kolkata'` (hard-coded in `config/settings.py`, not an env var). Datetimes are still stored in UTC; only display/"today" are IST. Excel export converts with `timezone.localtime` (see `_d` in `views.py`).
- **Archive (admin only):** `DispatchItem.is_archived` + `ArchivedMaterialLine` (for tickets never dispatched). `DispatchItem.objects` is a manager that **hides archived rows** from every page/report/export; use `DispatchItem.all_objects` only where admin must see them (dashboard, lookup, archive view, and `get_material_lines_for_engineer`'s dispatch join). Archived rows are soft-deleted on purpose -- hard-deleting would let the same Clappia ticket line reappear as "Yet to Dispatch".
- **Excel export:** `ExportExcelView` (`/export/`), stdlib-only writer in `tracker/excel.py`. Pages post the keys of the rows currently shown; the server re-checks each against what that role may see. Engineers only get the first `ENGINEER_EXPORT_COLUMNS` columns.
- **What a service engineer may see:** only "Dispatched" or "Received at <destination>" plus the date (`engineer_status_label` in `services.py`, `DispatchItem.destination_received_date`). Never expose later stages to the engineer.
- **Per-item motor/pump receive:** `motor_receive.js` + `_receive_motor_dialog.html`; fields are suffixed with the item pk and read by `_motor_receive_forms`/`_apply_motor_receive` in `views.py`. The OEM dispatch dialogs (`_oem_dialogs.html`) are shared by the regional and main warehouse pages.
- **Regional warehouse** has no Tested OK / Scrap actions (enforced server-side in `WarehouseActionView`); P-serial cards and received motors/pumps can be dispatched to the OEM.
- **Reports & Analytics** is a placeholder ("coming soon"): the sidebar item is locked and `AdminReportsView` shows no data. Rebuild the charts before re-enabling the link.
- **Local test data:** `docker/make_local_test_seed.py` generates `docker/local-test-seed.sql` (dummy tickets/items at every stage) for a throwaway local MySQL -- never run it against RDS.

### Special-case routing rules to know before touching `DispatchItem` status logic

- A Power/Control Card whose `faulty_serial` starts with `P` (`DispatchItem.is_p_serial_card`) skips Service Desk and Electronics entirely — Main Warehouse's Receive action routes it straight to an OEM/Scrap decision (`pending_oem_scrap`).
- A generic "material" item is a motor/pump if its name contains "motor" or "pump" (`is_motor_or_pump`) — these follow the repair/OEM path rather than tested-OK/dispatch.
- If a regional warehouse forwards an item on, `forward_dispatch` is set and becomes the item's `effective_dispatch`/`effective_arrival_date` instead of the original `dispatch`. Only one further hop is modeled by design — a third hop should become its own event table, not a second FK.
- Status history (`DispatchItemStatusEvent`) uses `default=timezone.now`, not `auto_now_add`, deliberately — `auto_now_add` would overwrite historical timestamps set by backfill migrations.
