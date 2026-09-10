ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY container_worker.py /opt/saintvision/worker.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /workspace
USER 65532:65532
ENTRYPOINT ["python", "-I", "/opt/saintvision/worker.py"]
