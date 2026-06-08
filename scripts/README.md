# Scripts

Utility scripts for the DevinLite / repopilot project.

## install_rate_limit_deps.sh

Installs and verifies the packages required for the rate-limiting middleware
feature into the project's `.venv` virtual environment.

**Packages installed**

| Package  | Purpose                                              |
|----------|------------------------------------------------------|
| slowapi  | Rate-limiting middleware for FastAPI (Starlette)     |
| mypy     | Static type-checking                                 |
| ruff     | Fast Python linter / formatter                       |

**Usage**

```bash
cd /Users/shashank/devinlite
bash scripts/install_rate_limit_deps.sh
```

The script will exit with a non-zero status code and print a clear error
message if any step fails.  Run it again after fixing the issue (e.g.
missing virtual environment).
