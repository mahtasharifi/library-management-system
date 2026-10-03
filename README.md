<h1 align="center">Library Management System</h1>

<p align="center">
  A production-oriented Django library management system adapted from a real-world deployment for Nesha Group.
</p>

<p align="center">
  <a href="https://library.neshagroup.ir/"><strong>Live Production System</strong></a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white">
  <img alt="MariaDB / MySQL" src="https://img.shields.io/badge/MariaDB%20%2F%20MySQL-003545?logo=mariadb&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
</p>

## About

This repository contains a public version of a library management system originally developed for a real-world deployment at **Nesha Group**.

The production system supports digital and physical library workflows, including book management, borrowing and request processes, user accounts, notifications, staff administration, spreadsheet imports, access control, and operational tools.

Company-specific data, credentials, private configuration, and internal information have been removed or replaced in this public repository, while the core architecture and major application features have been preserved and improved.

> **Public repository notice:** this repository is an adapted portfolio version of the production codebase. It does not contain private company data, credentials, or internal-only configuration.

## Highlights

- Production-derived Django application based on a real organizational workflow
- TOTP multi-factor authentication with recovery codes
- Digital and physical book management
- Borrowing and digital-book request workflows
- Role-based staff administration
- XLSX import with validation and background processing
- Database-backed background job queue
- Security middleware and database-backed rate limiting
- Health checks and protected operational metrics
- Dockerized deployment with Gunicorn and Nginx
- CI checks with tests, Ruff, Bandit, pip-audit, and Docker build verification

## Features

### Library & Catalog

- Searchable catalog for digital and physical books
- Hierarchical subject categories
- Physical borrowing workflows
- Digital-book requests and controlled downloads
- User book requests and notifications

### Accounts & Security

- User registration and profile management
- TOTP multi-factor authentication
- One-time recovery codes
- Role-based authorization
- Database-backed rate limiting
- CSRF protection
- Secure production settings

### Administration

- Staff dashboard for books, users, requests, comments, and imports
- XLSX import with validation
- Background processing for imports and email
- Administrative MFA reset and key-rotation tools

### Operations

- Health and readiness endpoints
- Protected operational metrics
- Environment-based configuration
- Separate development, test, CI, and production settings
- Docker, Gunicorn, and Nginx deployment

## Tech Stack

| Area | Technologies |
| --- | --- |
| Backend | Python 3.13, Django 5.2 |
| Database | MySQL / MariaDB, SQLite for local development |
| Frontend | Django Templates, HTML, CSS, Vanilla JavaScript |
| Authentication | Django Auth, TOTP MFA |
| Data & Files | openpyxl, Pillow, FTPS / filesystem storage |
| Deployment | Docker Compose, Gunicorn, Nginx |
| Quality | Ruff, Bandit, pip-audit |
| CI/CD | GitHub Actions, Dependabot |

## Architecture

The project follows a modular Django structure with clear application boundaries:

- `apps/accounts/` — authentication, profiles, and MFA
- `apps/books/` — catalog, borrowing, requests, imports, and staff workflows
- `apps/books/services/` — business logic and application services
- `apps/books/repositories/` — reusable query and data-access logic
- `common/` — shared security, middleware, health checks, metrics, and localization
- `config/settings/` — separate development, test, CI, and production configuration

See [Architecture Notes](docs/architecture.md) for more details.

## Background Processing

Email delivery and spreadsheet imports are processed through a database-backed job queue.

A dedicated Django worker:

- claims queued jobs
- records worker heartbeats
- handles failures
- recovers stale locks

This keeps the current deployment lightweight while leaving a clear path to migrate to systems such as Celery and Redis if workload requirements grow.

## Project Structure

```text
.
├── apps/
│   ├── accounts/        authentication, profiles, and MFA
│   └── books/           catalog, requests, imports, and staff tools
├── common/              shared middleware, security, health, and i18n
├── config/settings/     development, test, CI, and production settings
├── deploy/              Nginx, Gunicorn, and environment examples
├── docs/                architecture and migration notes
├── static/              application CSS, JavaScript, and images
├── templates/           shared layouts and components
├── Dockerfile
├── compose.yml
└── manage.py
```

## Local Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
```

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Install the pinned dependencies and initialize the local database:

```bash
python -m pip install --upgrade pip
pip install -r requirements.lock
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The application will be available at:

```text
http://127.0.0.1:8000/
```

Run the background worker in a second terminal when testing queued tasks:

```bash
python manage.py run_task_worker
```

## Tests

Run Django checks and the automated test suite:

```bash
python manage.py check --settings=config.settings.test
python manage.py test --settings=config.settings.test
```

Install development dependencies and run quality checks:

```bash
pip install -r requirements-dev.txt
ruff check .
bandit -r apps common config -x '*/migrations/*,*/tests.py' -ll
pip-audit -r requirements.lock
```

## Quality & CI

Every push and pull request is checked with:

- Django system checks
- Automated tests
- Ruff linting
- Bandit security analysis
- Dependency vulnerability auditing with `pip-audit`
- Docker image build verification

## Docker

The repository includes a Docker Compose setup for Django, the background worker, and Nginx.

Production values are supplied through environment files based on the examples in `deploy/env/`.

```bash
cp deploy/env/runtime.env.example deploy/env/runtime.env
cp deploy/env/migration.env.example deploy/env/migration.env
cp deploy/env/proxy.env.example deploy/env/proxy.env
docker compose --env-file deploy/env/proxy.env up --build
```

Do not commit generated `.env` files or production credentials.

## Security

Security is treated as part of the application architecture rather than an afterthought.

The project includes:

- TOTP MFA with encrypted secrets
- One-time recovery codes and replay protection
- Database-backed rate limiting
- Server-side authorization checks
- CSRF protection
- Upload and spreadsheet validation
- Secure production cookies and HSTS
- Content Security Policy
- Environment-based secret management

See [SECURITY.md](SECURITY.md) for implementation notes.

## Live Deployment

The production system is available at:

**https://library.neshagroup.ir/**

The public repository is an adapted version of the production codebase and does not expose company-specific private data or credentials.

## Documentation

- [Architecture Notes](docs/architecture.md)
- [Security Notes](SECURITY.md)

## Author

**Mahta Sharifi**

Backend Developer focused on Python, Django, internal systems, and database-driven applications.
