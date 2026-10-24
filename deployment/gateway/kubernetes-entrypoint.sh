#!/bin/sh
set -eu
: "${POD_NAMESPACE:?Kubernetes namespace is required}"
cluster_domain=${CLUSTER_DOMAIN:-cluster.local}
resolver=$(awk '/^nameserver[[:space:]]/ {print $2; exit}' /etc/resolv.conf)
test -n "$resolver"
case "$resolver" in *:*) resolver="[$resolver]" ;; esac
# Nginx's asynchronous resolver does not use resolv.conf search domains.
# Keep the shared routing/retry rules and substitute fully qualified Services.
sed \
  -e 's/worker_processes auto;/worker_processes 1;/' \
  -e "s/resolver 127\.0\.0\.11 /resolver $resolver /" \
  -e "s/server identity:8081/server identity.$POD_NAMESPACE.svc.$cluster_domain:8081/" \
  -e "s/server event-catalog:8082/server event-catalog-pods.$POD_NAMESPACE.svc.$cluster_domain:8082/" \
  -e "s/server admission:8083/server admission.$POD_NAMESPACE.svc.$cluster_domain:8083/" \
  -e "s/server web:80/server web.$POD_NAMESPACE.svc.$cluster_domain:80/" \
  /config/nginx.conf > /etc/nginx/nginx.conf
exec nginx "$@"
