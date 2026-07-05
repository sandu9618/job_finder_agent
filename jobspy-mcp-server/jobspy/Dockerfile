FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY patches/add_sri_lanka_country.py patches/
RUN python patches/add_sri_lanka_country.py

COPY . .

ENTRYPOINT ["python", "main.py"]
