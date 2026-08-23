#!/usr/bin/env bash
# Helper para gravar a connection string do Postgres no .env SEM expor o valor
# no histórico do terminal (read -s) e sem que ela passe por nenhum chat.
# Uso: bash scripts/definir_connection_string.sh
set -euo pipefail

ENV_FILE="/var/www/goshinsho/.env"

echo ""
echo "Cole a connection string do Supabase (postgresql://...) e pressione Enter."
echo "(o texto digitado fica oculto -- nada será exibido nem salvo no histórico)"
echo ""
read -r -s -p "Connection string: " CONN
echo ""
echo ""

# Remove espaços em branco acidentais ao redor
CONN="$(printf '%s' "$CONN" | tr -d '[:space:]')"

if [[ -z "$CONN" ]]; then
    echo "❌ Nada foi colado. Nenhuma mudança feita."
    exit 1
fi

case "$CONN" in
    postgresql://*|postgres://*)
        ;;
    *)
        echo "❌ Formato inválido. Deve começar com postgresql:// ou postgres://"
        echo "   (pegue em Supabase → Project Settings → Database → Connection string → URI → Direct connection)."
        exit 1
        ;;
esac

# Mostra só a parte não-secreta (usuário@host:porta/db) para o usuário confirmar
# que é o banco certo. Nunca exibe a senha.
HOST_PART="$(printf '%s' "$CONN" | sed -E 's#^postgres(ql)?://([^:]+):[^@]+@#postgres\1://\2:***@#')"
echo "✅ Formato OK. Conexão identificada como: $HOST_PART"

# Remove linha antiga (se existir) e adiciona a nova
if grep -q "^POSTGRES_CONNECTION_STRING=" "$ENV_FILE"; then
    grep -v "^POSTGRES_CONNECTION_STRING=" "$ENV_FILE" > "${ENV_FILE}.tmp"
    mv "${ENV_FILE}.tmp" "$ENV_FILE"
    echo "↻ Substituída uma entrada POSTGRES_CONNECTION_STRING anterior."
fi

echo "POSTGRES_CONNECTION_STRING=$CONN" >> "$ENV_FILE"
echo ""
echo "✅ Gravada no $ENV_FILE"
echo ""
