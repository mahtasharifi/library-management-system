<h1 align="center">Library</h1>

<p align="center">
  A Django-based library management system with a Persian interface, staff dashboard, MFA, book requests, imports and background jobs.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white">
  <img alt="MariaDB" src="https://img.shields.io/badge/MariaDB%20%2F%20MySQL-003545?logo=mariadb&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
</p>

## About

Library is a full-stack Django application for managing digital and physical library workflows. It includes a public catalog, user accounts, borrowing and digital-book requests, staff administration, spreadsheet import and production-oriented deployment settings.

## Features

- Searchable catalog with hierarchical subject categories
- Physical borrowing and digital-book request flows
- User registration, profiles, notifications and password management
- TOTP multi-factor authentication with recovery codes
- Staff dashboard for books, users, requests, comments and imports
- XLSX import with validation and background processing
- Database-backed background jobs for email and import work
- Rate limiting, security middleware, health checks and protected metrics
- Separate development, test, CI and production settings

## Tech stack

| Area | Technology |
| --- | --- |
| Backend | Python 3.13, Django 5.2 |
| Database | SQLite for local development, MySQL/MariaDB for production |
| Frontend | Django Templates, HTML, CSS, vanilla JavaScript |
| Authentication | Django Auth, TOTP MFA |
| Files and imports | Pillow, openpyxl, filesystem / FTPS storage |
| Server | Gunicorn, Nginx |
| Tooling | Docker Compose, Ruff, Bandit, pip-audit, GitHub Actions |

## Project structure

```text
.
├── apps/
│   ├── accounts/        authentication, profiles and MFA
│   └── books/           catalog, requests, imports and staff tools
├── common/              shared middleware, security, health and i18n
├── config/settings/     development, test, CI and production settings
├── deploy/              Nginx, Gunicorn and environment examples
├── docs/                architecture and migration notes
├── static/              application CSS, JavaScript and images
├── templates/           shared layouts and components
├── Dockerfile
├── compose.yml
└── manage.py
```

## Local setup

Create and activate a virtual environment, then install the pinned dependencies:

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies and initialize the local SQLite database:

```bash
python -m pip install --upgrade pip
pip install -r requirements.lock
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`.

Run the background worker in a second terminal when testing queued tasks:

```bash
python manage.py run_task_worker
```

## Tests

```bash
python manage.py check --settings=config.settings.test
python manage.py test --settings=config.settings.test
```

Development checks:

```bash
pip install -r requirements-dev.txt
ruff check .
bandit -r apps common config -x '*/migrations/*,*/tests.py' -ll
pip-audit -r requirements.lock
```

## Docker

The repository includes a Docker Compose setup for Django, the background worker and Nginx. Production values are supplied through environment files based on the examples in `deploy/env/`.

```bash
cp deploy/env/runtime.env.example deploy/env/runtime.env
cp deploy/env/migration.env.example deploy/env/migration.env
cp deploy/env/proxy.env.example deploy/env/proxy.env
docker compose --env-file deploy/env/proxy.env up --build
```

Do not commit the generated `.env` files or production credentials.

## Security

Security-related code includes MFA, database-backed rate limiting, CSRF protection, authorization checks, secure production cookies, upload validation and environment-based secrets. See [SECURITY.md](SECURITY.md) for a concise overview.

## Notes

- [Architecture](docs/architecture.md)

## Author

**Mahta Sharifi**
