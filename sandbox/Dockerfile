FROM python:3.12.10-slim
RUN pip install --no-cache-dir numpy==2.2.5 pandas==2.2.3 matplotlib==3.10.1
COPY runner.py /runner.py
USER 10001:10001
ENTRYPOINT ["python", "-I", "/runner.py"]
