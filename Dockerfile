FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

EXPOSE 3000
EXPOSE 6000

CMD ["python", "app.py"]
