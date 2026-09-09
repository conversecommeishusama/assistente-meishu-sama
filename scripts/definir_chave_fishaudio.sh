#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Configura com segurança a chave de API da Fish Audio no .env do projeto.
#
# POR QUE ESTE SCRIPT: a chave NUNCA deve passar pelo chat/Copilot. Este
# script lê a chave no próprio terminal (sem eco, `read -s`) e a grava
# direto no .env — sem aparecer na tela nem no histórico da conversa.
#
# Uso:
#   bash scripts/definir_chave_fishaudio.sh
# ---------------------------------------------------------------------------
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$RAIZ/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERRO: .env não encontrado em $ENV_FILE" >&2
    exit 1
fi

echo "==========================================================="
echo "  Configuração segura — Fish Audio (voz Meishu-Sama)"
echo "==========================================================="
echo "A chave será digitada abaixo SEM aparecer na tela."
echo

# --- Lê a API key sem eco --------------------------------------
API_KEY=""
while [[ -z "$API_KEY" ]]; do
    read -rsp "Cole a sua API key da Fish Audio e pressione ENTER: " API_KEY
    echo
    if [[ -z "$API_KEY" ]]; then
        echo "  (vazio — tente novamente)" >&2
    fi
done

# Deduplica: se a chave foi colada múltiplas vezes (ex.: 2-3x seguidas),
# fica só com a PRIMEIRA ocorrência. Chaves Fish Audio têm ~50-60 chars.
if [[ "$API_KEY" == *"sk-fish"*"sk-fish"* ]]; then
    echo "  (detectei que a chave foi colada mais de uma vez — usando só a 1ª)"
    API_KEY="${API_KEY%%sk-fish*}sk-fish${API_KEY#*sk-fish}"
    # Se ainda houver múltiplas, corta na 2ª ocorrência.
    if [[ "$API_KEY" == *"sk-fish"*"sk-fish"* ]]; then
        API_KEY="${API_KEY%%sk-fish*}"
        API_KEY="${API_KEY%??}"  # remove o 'sk-fish' que ficou no final
    fi
fi

# Sanidade: chave deve ter tamanho razoável.
if [[ ${#API_KEY} -lt 30 || ${#API_KEY} -gt 80 ]]; then
    echo "AVISO: a chave tem tamanho incomum (${#API_KEY} chars; esperado ~50-60)." >&2
    read -rsp "Deseja continuar mesmo assim? (s/N) " confirma
    echo
    [[ "$confirma" == "s" || "$confirma" == "S" ]] || { echo "Abortado."; exit 1; }
fi

# --- Atualiza o .env (preservando o resto do arquivo) ----------
# Remove linha existente (se houver) e adiciona a nova no fim.
grep -v '^GOSHINSHO_FISH_AUDIO_API_KEY=' "$ENV_FILE" > "$ENV_FILE.tmp" || true
mv "$ENV_FILE.tmp" "$ENV_FILE"

{
    echo ""
    echo "# 2026-09-09: Fish Audio (voz Meishu-Sama) — API de TTS/clonagem"
    echo "GOSHINSHO_FISH_AUDIO_API_KEY=$API_KEY"
} >> "$ENV_FILE"

# Permissões restritas (só dono lê).
chmod 600 "$ENV_FILE"

echo
echo "==========================================================="
echo "  ✅ Configurado com sucesso!"
echo "  - GOSHINSHO_FISH_AUDIO_API_KEY: $(grep -c '^GOSHINSHO_FISH_AUDIO_API_KEY=.' "$ENV_FILE") entrada(s)"
echo "==========================================================="
echo "Nunca compartilhe esta chave no chat. Se vazou antes,"
echo "regenere no painel da Fish Audio (API Keys)."
