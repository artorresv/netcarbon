FROM tiangolo/uvicorn-gunicorn:python3.10

COPY ./app/api/requirements.txt /tmp/requirements.txt
RUN pip install wheel && pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app

COPY ./app/api /app

EXPOSE 8000

CMD ["fastapi", "run", "main.py", "--port", "8000"]