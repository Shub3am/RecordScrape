# Runs the dashboard, manual runs and schedules on a server. Recording still happens on a desktop:
# flows are exported there and imported here.
# The base image carries the browsers and system libraries for the Playwright version uv.lock pins.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# CloakBrowser's binary license forbids redistributing it, so an image only holds it when whoever
# builds it opts in with --build-arg WITH_CLOAKBROWSER=1.
ARG WITH_CLOAKBROWSER=0

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev $([ "$WITH_CLOAKBROWSER" = 1 ] && echo --extra cloakbrowser)
# A no-op when Patchright's Chromium revision matches the one the base image already holds.
RUN patchright install chromium

COPY app.py ./
COPY recordscrape recordscrape
COPY vpr vpr
COPY templates templates
COPY static static

RUN mkdir /data && chown pwuser:pwuser /data
USER pwuser
# Downloads into ~/.cloakbrowser of the user the server runs as.
RUN if [ "$WITH_CLOAKBROWSER" = 1 ]; then python -m cloakbrowser install; fi

ENV RECORDSCRAPE_HOST=0.0.0.0 \
    RECORDSCRAPE_PORT=5001 \
    RECORDSCRAPE_DATA_DIR=/data
EXPOSE 5001
VOLUME /data

# xvfb-run never sees Xvfb's ready signal when it is PID 1 and hangs, so tini is PID 1. -g sends
# docker stop's SIGTERM to the whole group, reaching Python and Xvfb behind the xvfb-run shell.
ENTRYPOINT ["tini", "-g", "--"]
# xvfb-run gives runs with "Run headless" unticked a virtual screen to open their window on.
CMD ["xvfb-run", "--auto-servernum", "python", "app.py"]
