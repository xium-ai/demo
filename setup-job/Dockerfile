FROM python:3.12-alpine

WORKDIR /setup
COPY xos_setup.py .

# PYTHONUNBUFFERED=1 -- sonst sieht man keine Logs bevor der Container stirbt
ENV PYTHONUNBUFFERED=1

CMD ["python", "/setup/xos_setup.py"]
