FROM python:3.12.10-slim
WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install --with-deps chromium
COPY backend/app app
RUN useradd -u 10001 -m agent && mkdir -p /app/data/files && chown -R agent:agent /app/data
USER agent
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
