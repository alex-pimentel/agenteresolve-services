# Agenteresolve object store: MinIO (S3-compatible) for gateway + workers.
# Deployed via Coolify on the Oracle server (tailnet-only, port 9000).
# Ephemeral tmp bucket semantics: gateway/workers auto-create the bucket on
# boot; restart limpo do container zera os objetos pendentes (aceitável:
# resultados expiram em 24h e jobs falhos são reenviados).
FROM minio/minio:latest

EXPOSE 9000 9001

# MINIO_ROOT_USER / MINIO_ROOT_PASSWORD vêm das envs do Coolify.
CMD ["server", "/data", "--address", ":9000", "--console-address", ":9001"]
