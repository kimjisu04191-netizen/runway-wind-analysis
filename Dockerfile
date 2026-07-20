FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY assets/ ./assets/
COPY .streamlit/config.toml .streamlit/config.toml

ENV PORT=8080
EXPOSE 8080

# Cloud Run이 주입하는 $PORT를 그대로 사용 (셸 형식 CMD여야 환경변수가 확장됨)
CMD streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
