FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

ENV PYTHONUNBUFFERED='1'

RUN pip install --upgrade pip

# COPY requirements.txt ./
# RUN pip install -r requirements.txt


COPY . /app/
# COPY ./scripts/prestart.sh /app/

RUN pip install -e ".[cpu]"

ENV PYTHONPATH=/app
ENV MODULE_NAME=src.expasy_chat.api
# ENV VARIABLE_NAME=app
