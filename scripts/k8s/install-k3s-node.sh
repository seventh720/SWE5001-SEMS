#!/bin/sh
# Run on a prepared EC2 node after writing its root-only K3s configuration.
set -eu

role=${1:?Usage: install-k3s-node.sh server|agent}
case "$role" in
  server|agent) ;;
  *) echo 'Role must be server or agent' >&2; exit 2 ;;
esac
if [ "$(id -u)" -ne 0 ]; then
  echo 'Run this script as root on the target node' >&2
  exit 2
fi
test -s /etc/rancher/k3s/config.yaml
if [ "$role" = agent ]; then
  test -s /etc/rancher/k3s/agent-token
fi

version='v1.36.5+k3s1'
installer=$(mktemp)
trap 'rm -f "$installer"' EXIT HUP INT TERM
curl --fail --silent --show-error --location --retry 3 \
  "https://raw.githubusercontent.com/k3s-io/k3s/$version/install.sh" \
  --output "$installer"
# The official installer checks the release binary against its SHA256 manifest.
INSTALL_K3S_VERSION="$version" INSTALL_K3S_EXEC="$role" sh "$installer"
k3s --version
