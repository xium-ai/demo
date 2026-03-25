FROM alpine:3.21

ARG XOSP_VERSION=latest
ARG GITHUB_REPO=xium-ai/releases

RUN apk add --no-cache curl ca-certificates

RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then SUFFIX="linux_arm64"; \
    elif [ "$ARCH" = "x86_64" ]; then SUFFIX="linux_amd64"; \
    else echo "Unbekannte Architektur: $ARCH" && exit 1; fi && \
    if [ "$XOSP_VERSION" = "latest" ]; then \
      URL="https://github.com/${GITHUB_REPO}/releases/latest/download/xosp_${SUFFIX}"; \
    else \
      URL="https://github.com/${GITHUB_REPO}/releases/download/${XOSP_VERSION}/xosp_${SUFFIX}"; \
    fi && \
    echo "Lade xosp von: $URL" && \
    curl -fsSL "$URL" -o /usr/local/bin/xosp && \
    chmod +x /usr/local/bin/xosp

EXPOSE 9100

CMD ["/usr/local/bin/xosp"]
