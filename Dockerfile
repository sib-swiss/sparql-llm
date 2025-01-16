FROM docker.io/python:3.11

WORKDIR /app

ENV PYTHONUNBUFFERED='1'

RUN pip install --upgrade pip

# COPY requirements.txt ./
# RUN pip install -r requirements.txt


COPY . /app/

WORKDIR /app/packages/expasy-agent

RUN pip install -e ".[cpu]" "../sparql-llm"

# ENV PYTHONPATH=/app/packages/expasy-agent
# ENV MODULE_NAME=src.expasy_agent.api

# https://github.com/tiangolo/uvicorn-gunicorn-docker/blob/master/docker-images/gunicorn_conf.py

CMD ["uvicorn", "src.expasy_agent.api:app", "--host", "0.0.0.0", "--port", "80", "--workers", "8"]
# CMD ["uvicorn", "src.expasy_agent.api", "--host", "0.0.0.0", "--port", "80", "--workers", "4", "--http", "h11"]
