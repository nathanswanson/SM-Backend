FROM --platform=$BUILDPLATFORM python:3.12 AS installer

WORKDIR /app


# COPY . .
COPY src/ /app/src/
COPY pyproject.toml /app/
COPY README.md /app/

# COPY . . 
RUN python -m pip install build
RUN python -m build --wheel

RUN echo $(ls /app/dist/)
FROM python:3.12-slim

WORKDIR /app

# backend
COPY --from=installer /app/dist/server_manager*.whl /app/
RUN pip install build
RUN WHL=$(ls server_manager*.whl) && pip install "${WHL}[kubernetes]" && rm "$WHL"

EXPOSE 8000

VOLUME [ "/data"]
ENTRYPOINT [ "/usr/local/bin/server_manager" ]
