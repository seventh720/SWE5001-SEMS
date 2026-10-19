FROM postgres:17-alpine
# Use Alpine's small privilege-switch helper instead of the bundled Go binary.
# The upstream entrypoint only invokes `gosu postgres ...`; su-exec preserves that behavior.
RUN apk upgrade --no-cache \
    && apk add --no-cache su-exec \
    && sed -i 's/exec gosu postgres/exec su-exec postgres/' /usr/local/bin/docker-entrypoint.sh \
    && ! grep -q gosu /usr/local/bin/docker-entrypoint.sh \
    && rm /usr/local/bin/gosu
COPY --chmod=644 init.sh /docker-entrypoint-initdb.d/01-init.sh
