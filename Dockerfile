FROM python:3.12-slim

WORKDIR /app

# git is needed by the git.* tools at runtime
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

# Install dependencies (cached layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

# Copy application code
COPY repopilot/ repopilot/

# Railway (and most PaaS) inject $PORT. Default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000

# Use shell form so $PORT expands at runtime.
CMD uv run uvicorn repopilot.api.main:app --host 0.0.0.0 --port ${PORT}
