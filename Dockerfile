FROM qinbatista/xray-reality@sha256:5739b13a9253a4b43434fb1f69fc69dc23db296ca55b0784c7c5ad729f0400a1 AS xray
FROM ghcr.io/sagernet/sing-box@sha256:0788ffbddab2c68a99a2dd4780bbc50902f159af6f589df3ee74a8389d278279 AS singbox
FROM python:3.13-alpine@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8

RUN apk add --no-cache ca-certificates
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
COPY --from=singbox /usr/local/bin/sing-box /usr/local/bin/sing-box
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY runtime/ /app/runtime/
COPY vless-reality/ /app/vless-reality/
COPY hysteria2/ /app/hysteria2/
COPY hysteria2-salamander/ /app/hysteria2-salamander/
COPY tuic/ /app/tuic/
COPY trojan/ /app/trojan/
LABEL org.opencontainers.image.source="https://github.com/qinbatista/DockerVPN"
ENTRYPOINT ["python", "/app/runtime/supervisor.py"]
CMD ["serve"]
