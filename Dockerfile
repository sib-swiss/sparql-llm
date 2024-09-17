FROM docker.io/tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

ENV PYTHONUNBUFFERED='1'

RUN pip install --upgrade pip

# COPY requirements.txt ./
# RUN pip install -r requirements.txt


COPY . /app/
# COPY ./scripts/prestart.sh /app/

RUN pip install -e "."

ENV PYTHONPATH=/app
ENV MODULE_NAME=src.sparql_llm.api
# ENV VARIABLE_NAME=app
