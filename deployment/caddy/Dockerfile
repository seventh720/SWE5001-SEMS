FROM golang:1.26.10-alpine AS builder
WORKDIR /src
COPY main.go .
# Keep standard modules and pin Smallstep's upstream migration off go-jose v3.
RUN go mod init sems/caddy \
    && go get github.com/caddyserver/caddy/v2@v2.11.9 \
        go.step.sm/crypto@v0.92.0 \
        github.com/smallstep/certificates@v0.30.3-0.20261105213751-6d5a251fbe01 \
        github.com/go-jose/go-jose/v4@v4.1.9 \
    && go mod tidy \
    && CGO_ENABLED=0 go build -trimpath -ldflags='-w -s' -o /caddy .

FROM caddy:2.11.9-alpine
RUN apk upgrade --no-cache
COPY --from=builder /caddy /usr/bin/caddy
