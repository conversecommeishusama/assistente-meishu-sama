#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Configura com segurança a chave de API da ElevenLabs no .env do projeto.
#
# POR QUE ESTE SCRIPT: a chave NUNCA deve passar pelo chat/Copilot. Este
# script lê a chave no próprio terminal (sem eco, `read -s`) e a grava
# direto no .env — sem aparecer na tela nem no histórico da conversa.
#
# Uso:
#   bash scripts/definir_chave_elevenlabs.sh
#
# Ele também permite informar (opcional) o voice_id da voz clonada
# (GOSHINSHO_MEISHU_VOICE_ID), que você obtém após clonar a voz no painel
# da ElevenLabs (URL .../voice-library/<VOICE_ID>).
# ---------------------------------------------------------------------------
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$RAIZ/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERRO: .env não encontrado em $ENV_FILE" >&2
    exit 1
fi

echo "==========================================================="
echo "  Configuração segura — ElevenLabs (voz Meishu-Sama)"
echo "==========================================================="
echo "A chave será digitada abaixo SEM aparecer na tela."
echo

# --- Lê a API key sem eco --------------------------------------
API_KEY=""
while [[ -z "$API_KEY" ]]; do
    read -rsp "Cole a sua API key da ElevenLabs (sk_...) e pressione ENTER: " API_KEY
    echo
    if [[ -z "$API_KEY" ]]; then
        echo "  (vazio — tente novamente)" >&2
    fi
done

# Sanidade: chave deve começar com "sk_" e ter >= 40 chars.
if [[ "$API_KEY" != sk_* || ${#API_KEY} -lt 40 ]]; then
    echo "AVISO: a chave não parece uma chave ElevenLabs válida (esperado sk_... com ~55+ chars)." >&2
    read -rsp "Deseja continuar mesmo assim? (s/N) " confirma
    echo
    [[ "$confirma" == "s" || "$confirma" == "S" ]] || { echo "Abortado."; exit 1; }
fi

# --- Lê o voice_id (opcional) ----------------------------------
echo
echo "OPCIONAL: se você JÁ clonou a voz no painel da ElevenLabs,"
echo "informe o voice_id (o ID longo na URL da voz). Se ainda não"
echo "clonou, deixe em branco para configurar depois."
read -rsp "Voice ID (opcional, ENTER para pular): " VOICE_ID
echo

# --- Atualiza o .env (preservando o resto do arquivo) ----------
# Remove linhas existentes (se houver) e adiciona as novas no fim.
grep -v '^GOSHINSHO_ELEVENLABS_API_KEY=' "$ENV_FILE" > "$ENV_FILE.tmp" || true
grep -v '^GOSHINSHO_MEISHU_VOICE_ID=' "$ENV_FILE.tmp" > "$ENV_FILE.tmp2" || true
mv "$ENV_FILE.tmp2" "$ENV_FILE"

{
    echo ""
    echo "# 2026-09-01: voz clonada Meishu-Sama (ElevenLabs) — cross-lingual JP→PT"
    echo "GOSHINSHO_ELEVENLABS_API_KEY=$API_KEY"
    echo "GOSHINSHO_MEISHU_VOICE_ID=${VOICE_ID:-}"
} >> "$ENV_FILE"

# Permissões restritas (só dono lê).
chmod 600 "$ENV_FILE"

echo
echo "==========================================================="
echo "  ✅ Configurado com sucesso!"
echo "  - GOSHINSHO_ELEVENLABS_API_KEY: $(grep -c '^GOSHINSHO_ELEVENLABS_API_KEY=sk_' "$ENV_FILE") entrada(s)"
echo "  - GOSHINSHO_MEISHU_VOICE_ID: $(grep '^GOSHINSHO_MEISHU_VOICE_ID=' "$ENV_FILE" | sed 's/.*=//')"
echo "==========================================================="
echo "Nunca compartilhe esta chave no chat. Se vazou antes,"
echo "regenere no painel da ElevenLabs (Settings → API Keys)."
