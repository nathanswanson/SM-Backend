FROM --platform=$BUILDPLATFORM python:3.12 AS installer

WORKDIR /app

RUN python -m pip install build
# COPY . .
COPY src/ /app/src/
COPY pyproject.toml /app/
COPY README.md /app/

RUN python -m build --wheel

FROM python:3.12-slim

WORKDIR /app

# backend
RUN pip install build
COPY --from=installer /app/dist/server_manager*.whl /app/
RUN WHL=$(ls server_manager*.whl) && pip install "${WHL}[kubernetes]" && rm "$WHL"

EXPOSE 8000

VOLUME [ "/data"]
ENTRYPOINT [ "/usr/local/bin/server_manager" ]
