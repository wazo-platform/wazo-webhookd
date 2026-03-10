# Testing and Development Guidelines
- TDD is non-negotiable. Always write the tests first and ensure they fail before implementing the fix. Move in baby steps through the red-green-refactor cycles.
- Do your best to test the exposed API, its inputs and outputs, rather than implementation details.
- When planning, implement in a branch and open a PR.
- Once done, run pre-commit quality checks in order to avoid additional fix commits.
- Use pytest as the test runner. Use pytest-cov for coverage reporting.
- Prefer unittest.mock.patch or pytest fixtures for mocking. Use dependency injection to keep tests clean.
- Always activate the virtualenv before running any command: source .venv/bin/activate

# Definition of Done
- A task is not done if the linter is not passing for the whole project.
- A task is not done if it has new behavior without tests to ensure the new behavior.
- A task is not done if type hints are missing on new public functions/methods.
- A task is not done if mypy report new errors.

# Context
- The app is built on top of the backend server exposing an API, documented on: https://api.wazo.io
- For end-to-end testing purposes, you can use server stack.dev.wazo.io, with user ..., password ....
- Use steady HTTP requests in integration tests.
- Respect SOLID principles. Implement stubs when interacting with external services.

# Python Conventions
- Use pyproject.toml as the single source for project metadata, dependencies, and tool config.
- Target Python 3.11+.
- Use type hints everywhere. Run mypy in strict mode on new code.
- Formatting/linting: black/isort
- Imports: use absolute imports. Let isort handle sorting (isort-compatible rules).
- Logging over print. Use logging.getLogger(__name__).
- No bare except:. Always catch specific exceptions.

# Architecture
