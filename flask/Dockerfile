FROM python:3.5-slim

WORKDIR /app

# ensure compatible pip for old python
RUN pip install --upgrade "pip<21"

# install required packages
RUN pip install aiohttp

# copy backend code
COPY . .

EXPOSE 5000

CMD ["python", "main.py"]