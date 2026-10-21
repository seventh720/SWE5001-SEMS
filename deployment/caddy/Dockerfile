FROM golang:1.26.10-alpine AS builder
WORKDIR /src
COPY main.go .
# Preserve Caddy's version/modules; update the affected Go runtime and x/net only.
RUN go mod init sems/caddy \
    && go get github.com/caddyserver/caddy/v2@v2.11.7 golang.org/x/net@v0.60.0 \
    && go mod tidy \
    && CGO_ENABLED=0 go build -trimpath -ldflags='-w -s' -o /caddy .

FROM caddy:2.11.7-alpine
RUN apk upgrade --no-cache
COPY --from=builder /caddy /usr/bin/caddy
