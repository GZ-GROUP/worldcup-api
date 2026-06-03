FROM python:3.11-slim

WORKDIR /code

# Copiar y instalar dependencias
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copiar archivos de la aplicación
COPY ./main.py /code/main.py
COPY ./data.csv /code/data.csv

EXPOSE 8000

# ✅ IMPORTANTE: --host 0.0.0.0 para que sea accesible en Docker
CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
