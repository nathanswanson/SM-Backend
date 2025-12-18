FROM python:3.12 AS installer

WORKDIR /app


COPY . .

RUN python -m pip install build
RUN python -m build --wheel

RUN echo $(ls /app/dist/)
FROM ubuntu:questing

WORKDIR /app

# backend
COPY --from=installer /app/dist/server_manager*.whl /app/

RUN apt-get update && \
    apt-get install -y unzip pipx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pipx install server_manager*.whl && rm server_manager*.whl

EXPOSE 8000

VOLUME [ "/data"]
ENTRYPOINT [ "/root/.local/bin/server_manager" ]
