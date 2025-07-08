FROM python:3.12
WORKDIR /surv
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x start.sh
CMD ["./start.sh"]