FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements-lock.txt pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements-lock.txt && pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 veilmint && mkdir /data && chown veilmint /data
USER veilmint
ENV VEILMINT_DB=/data/synthetic-demo.sqlite3 VEILMINT_MODE=OBSERVE
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=2)"
CMD ["python", "-m", "uvicorn", "veilmint.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
