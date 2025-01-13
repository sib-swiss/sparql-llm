FROM docker.io/tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

ENV PYTHONUNBUFFERED='1'

RUN pip install --upgrade pip

# COPY requirements.txt ./
# RUN pip install -r requirements.txt


COPY . /app/
# COPY ./scripts/prestart.sh /app/

WORKDIR /app/packages/expasy-agent

RUN pip install -e ".[cpu]" "../sparql-llm"

ENV PYTHONPATH=/app/packages/expasy-agent
ENV MODULE_NAME=src.expasy_agent.api
# ENV VARIABLE_NAME=app
