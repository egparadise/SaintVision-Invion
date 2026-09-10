FROM scratch
COPY probe /probe
COPY inv-supervisor /inv-supervisor
COPY git-root/ /
LABEL ai.saintvision.supervisor="deadline-v1"
LABEL ai.saintvision.output="bounded-streams-v1"
LABEL ai.saintvision.workspace="snapshot-tmpfs-v1"
USER 65532:65532
ENTRYPOINT ["/inv-supervisor"]
