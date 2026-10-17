# Agenteresolve object store: RustFS (S3-compatible) for gateway + workers.
# Deployed via Coolify on the Oracle server (tailnet-only, port 9000).
#
# Por que RustFS e não MinIO: o repositório `minio/minio` foi REMOVIDO do
# Docker Hub (registry devolve 401/manifest inexistente) e o projeto upstream
# está arquivado, então o build falhava em ~45 s sem log de erro. O RustFS é
# drop-in: mesmas portas 9000 (S3) e 9001 (console), mesma API S3, mesmo
# diretório /data e imagem multi-arch (arm64, que é o caso do Oracle).
#
# Envs esperadas (definidas pelo Coolify / deploy-backends.sh):
#   RUSTFS_ACCESS_KEY / RUSTFS_SECRET_KEY  -> credenciais R2
#   RUSTFS_VOLUMES=/data
#   RUSTFS_ADDRESS=0.0.0.0:9000
#   RUSTFS_CONSOLE_ADDRESS=0.0.0.0:9001
#   RUSTFS_UNSAFE_BYPASS_DISK_CHECK=true   -> volume único em overlayfs
# Health: GET /health na porta 9000 (o console responde em
# /rustfs/console/health na 9001).
#
# Ephemeral tmp bucket semantics: gateway/workers auto-create the bucket on
# boot; restart limpo do container zera os objetos pendentes (aceitável:
# resultados expiram em 24h e jobs falhos são reenviados).
FROM rustfs/rustfs:latest

EXPOSE 9000 9001

# ENTRYPOINT/CMD da imagem já sobem o servidor lendo as envs acima; /data já
# vem criado com dono `rustfs` (uid 10001) na própria imagem.
