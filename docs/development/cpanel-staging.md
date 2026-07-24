# cPanel Staging Deployment

Target: `dev.bssply.co` on GoDaddy cPanel

This guide is tailored to the currently observed GoDaddy cPanel environment. Exact field labels may still vary.

## 1. Create the subdomain

Create `dev.bssply.co` with a document/application location separate from WordPress.

## 2. Protect staging before application login

Use cPanel/Apache directory protection or equivalent web-server authentication if available. This is an additional barrier, not a replacement for Django authentication.

## 3. Create the Python application

In **Setup Python App**:

- Python version: 3.11.15
- application root: a dedicated path such as `bs-portal-dev`
- application URL: `dev.bssply.co`
- startup file: `passenger_wsgi.py`
- entry point: `application`

Exact field names vary by cPanel distribution.

## 4. Upload/clone the repository

Place the repository in the application root. The supplied root-level `passenger_wsgi.py` adds the `portal/` directory to Python's import path.

## 5. Install dependencies

Activate the virtual environment shown by cPanel and run:

```bash
pip install -r requirements.txt
```

## 6. Configure environment variables

At minimum:

```text
DJANGO_SETTINGS_MODULE=config.settings.staging
DJANGO_SECRET_KEY=<strong random value>
DJANGO_ALLOWED_HOSTS=dev.bssply.co
DJANGO_CSRF_TRUSTED_ORIGINS=https://dev.bssply.co
MYSQL_DATABASE=<staging database>
MYSQL_USER=<staging user>
MYSQL_PASSWORD=<staging password>
MYSQL_HOST=localhost
MYSQL_PORT=3306
```

Never store these values in Git.

## 7. Initialize

From the activated cPanel virtual environment:

```bash
python portal/manage.py migrate
python portal/manage.py collectstatic --noinput
python portal/manage.py createsuperuser
```

## 8. Restart Passenger

Use cPanel's restart control or touch the Passenger restart marker if your host documents that method.

## 9. Verify

- `/health/` returns `{"status":"ok"}`
- `/accounts/login/` shows Django login
- `/` redirects unauthenticated users to login
- admin is reachable only after authentication/authorization

## Staging policy

Use synthetic data only. Do not promote the staging database to production. Production should be a separate app deployment and separate database using an approved release of the same codebase.
