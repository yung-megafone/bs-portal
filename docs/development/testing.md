# Testing

Run Django's test suite:

```bash
python portal/manage.py test --settings=config.settings.test
```

The test settings still expect PostgreSQL so constraints and SQL behavior stay representative of deployment.

Environment variables beginning with `TEST_POSTGRES_` can override the test database connection. If omitted, the regular `POSTGRES_` connection values are reused and Django creates its normal prefixed test database.
