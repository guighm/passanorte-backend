#!/bin/sh
# Renderiza kong/kong.yml (marcadores __JWT_SECRET__/__JWT_ISSUER__) para
# /tmp/kong.yml com as envs do compose e inicia o Kong DB-less.
# O arquivo renderizado vive apenas dentro do container (o segredo nunca volta
# ao host); a imagem kong não tem envsubst/python, por isso sed com escape.
set -eu

# Escapa &, / e \ para uso seguro em substituição sed
esc() { printf '%s' "$1" | sed 's/[&/\]/\\&/g'; }

sed \
    -e "s/__JWT_SECRET__/$(esc "${JWT_SECRET:?JWT_SECRET não definida}")/" \
    -e "s/__JWT_ISSUER__/$(esc "${JWT_ISSUER:-passanorte}")/" \
    /kong/kong.yml > /tmp/kong.yml
chmod 644 /tmp/kong.yml

exec /docker-entrypoint.sh kong docker-start