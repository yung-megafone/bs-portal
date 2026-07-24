# Contributing

B.S. Portal favors maintainability and explicit behavior over cleverness.

## Rules

1. Keep business logic out of templates.
2. Avoid giant `utils.py` modules.
3. Prefer domain-oriented apps and explicit service functions.
4. Use database constraints for important invariants where practical.
5. Add tests with behavior changes.
6. Never commit secrets.
7. Explain security-sensitive mechanisms in code comments or architecture docs when the reason is not obvious.
