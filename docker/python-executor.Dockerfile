# python-executor.Dockerfile — the UNTRUSTED container: runs only the
# model's generated Python code. Deliberately does NOT copy src/db/ or
# src/core/ — this container has no filesystem access to the database or
# any scenario logic at all; its only path to data is a network call to the
# tool-server, which is the whole point of the trust boundary.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir requests flask

COPY src/executors/python_executor/ .

EXPOSE 8001

CMD ["python", "exec_server.py"]
