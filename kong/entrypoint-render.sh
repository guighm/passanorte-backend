#!/bin/sh
# Public-key-only configuration; filenames match JWT header kid.
set -eu
umask 077
origin="${EDGE_CORS_ORIGIN:?Missing EDGE_CORS_ORIGIN}"
case "$origin" in
    http://*|https://*) ;;
    *) echo "Invalid CORS origin" >&2; exit 1 ;;
esac
case "$origin" in *[!a-zA-Z0-9.:/_-]*) echo "Invalid CORS origin" >&2; exit 1 ;; esac
sed "s|__EDGE_CORS_ORIGIN__|$origin|g" /kong/kong.yml > /tmp/kong.yml
printf '\nconsumers:\n  - username: passanorte-edge\n    jwt_secrets:\n' >> /tmp/kong.yml
found=0
for file in "${JWT_PUBLIC_KEYS_DIR:?Missing JWT_PUBLIC_KEYS_DIR}"/*.pem; do
    [ -f "$file" ] || continue
    kid="$(basename "$file" .pem)"
    case "$kid" in ''|*[!a-zA-Z0-9_-]*) echo "Invalid public key identifier" >&2; exit 1 ;; esac
    # Reject private material before producing a declarative config.
    grep -q '^-----BEGIN PUBLIC KEY-----$' "$file" || { echo "Invalid public key" >&2; exit 1; }
    printf '      - algorithm: RS256\n        key: "%s"\n        secret: unused-rsa-field\n        rsa_public_key: |\n' "$kid" >> /tmp/kong.yml
    sed 's/^/          /' "$file" >> /tmp/kong.yml
    printf '\n' >> /tmp/kong.yml
    found=1
done
[ "$found" = 1 ] || { echo "No public keys configured" >&2; exit 1; }
exec /docker-entrypoint.sh kong docker-start
