FROM scratch
COPY probe /probe
COPY inv-supervisor /inv-supervisor
LABEL ai.saintvision.supervisor="deadline-v1"
USER 65532:65532
ENTRYPOINT ["/inv-supervisor"]
