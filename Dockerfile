# One image for every container target. Built once per bench run and deployed by
# digest wherever the target accepts an image (see docs/adr/ADR-0002).
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /srv
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/

RUN useradd --system --uid 10001 bench
USER 10001

EXPOSE 8080
# Every target injects PORT; one worker so a target's CPU share is the only variable.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --no-access-log"]
