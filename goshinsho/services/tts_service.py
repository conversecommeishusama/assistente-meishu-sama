"""Serviço de TTS (texto → fala): edge-tts (vozes neurais gratuitas) + voz
clonada de Meishu-Sama via ElevenLabs (cross-lingual japonês → português).

2026-08-27: implementado para a Leitura Colaborativa do protótipo (/versao2).
Motivo: o speechSynthesis do navegador não roteia o áudio pelo perfil de
mídia do bluetooth no Android (carro) — apps como Spotify/Google Maps tocam
normalmente, mas o TTS do navegador fica mudo. O `<audio>` com um MP3 gerado
no servidor segue o perfil de mídia do bluetooth normalmente.

Edge TTS usa o serviço gratuito de síntese da Microsoft (vozes neurais).
Não requer API key. As vozes pt-BR: pt-BR-AntonioNeural (masc),
pt-BR-FranciscaNeural (fem), pt-BR-ThalitaMultilingualNeural (fem).

2026-09-01: voz 'meishu' — voz clonada de Meishu-Sama (amostra de áudio
histórica) via ElevenLabs, falando PORTUGUÊS (cross-lingual). Quando a
chave/voice_id não estiverem configurados (ou a API falhar), faz fallback
para o Antonio (edge-tts) para nunca deixar o usuário sem áudio.

Config (via .env):
  GOSHINSHO_ELEVENLABS_API_KEY=sk_...
  GOSHINSHO_MEISHU_VOICE_ID=<voice_id da ElevenLabs>
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time

VOZES_PT_BR = {
    "antonio": "pt-BR-AntonioNeural",
    "francisca": "pt-BR-FranciscaNeural",
    "thalita": "pt-BR-ThalitaMultilingualNeural",
    # "meishu" é sentinela: encaminha para a ElevenLabs (voz clonada).
    "meishu": "__elevenlabs_meishu__",
}
VOZ_PADRAO = "pt-BR-AntonioNeural"
VOZ_MEISHU = "meishu"

# Modelo multilíngue da ElevenLabs — voz treinada em japonês falando PT.
_ELEVENLABS_MODELO = "eleven_multilingual_v2"


def _chave_elevenlabs() -> str:
    return os.environ.get("GOSHINSHO_ELEVENLABS_API_KEY", "").strip()


def _voice_id_meishu() -> str:
    return os.environ.get("GOSHINSHO_MEISHU_VOICE_ID", "").strip()


def voz_meishu_disponivel() -> bool:
    """True se a voz clonada de Meishu-Sama pode ser usada agora."""
    return bool(_chave_elevenlabs() and _voice_id_meishu())


def _sintetizar_elevenlabs(texto: str, destino: str, *, rate: str = "+0%") -> None:
    """Gera o áudio via ElevenLabs (voz clonada) e salva em `destino`.

    Usa a voz 'meishu' (GOSHINSHO_MEISHU_VOICE_ID) com o modelo multilíngue,
    que permite a voz treinada em japonês falar português.
    """
    import requests

    chave = _chave_elevenlabs()
    voice_id = _voice_id_meishu()
    if not chave or not voice_id:
        raise RuntimeError("ElevenLabs não configurado (chave/voice_id)")

    # rate: o parâmetro da edge-tts é "+0%"/"-10%" — converte para o formato
    # da ElevenLabs ("speed" é multiplicador: 1.0 = normal, 0.9 = -10%).
    speed = 1.0
    if rate:
        try:
            speed = 1.0 + (float(rate.replace("%", "").replace("+", "")) / 100.0)
        except ValueError:
            speed = 1.0
    speed = max(0.5, min(2.0, speed))

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    resp = requests.post(
        url,
        headers={
            "xi-api-key": chave,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        },
        json={
            "text": texto,
            "model_id": _ELEVENLABS_MODELO,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.3,
                "use_speaker_boost": True,
            },
        },
        params={"output_format": "mp3_44100_128"},
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}"
        )
    with open(destino, "wb") as f:
        f.write(resp.content)


# Cache em disco dos áudios gerados (evita regerar o mesmo texto).
_CACHE_DIR = None
_CACHE_TTL_S = 60 * 60 * 24 * 30  # 30 dias


def _cache_dir() -> str:
    global _CACHE_DIR
    if _CACHE_DIR is None:
        base = os.environ.get("GOSHINSHO_TTS_CACHE", "/tmp/goshinsho_tts_cache")
        os.makedirs(base, exist_ok=True)
        _CACHE_DIR = base
    return _CACHE_DIR


def _chave_cache(provedor_voz: str, texto: str, rate: str) -> str:
    raw = f"{provedor_voz}|{rate}|{texto}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _limpar_cache_antigo() -> None:
    """Remove arquivos de cache mais antigos que o TTL (chamado a cada geração)."""
    try:
        agora = time.time()
        for nome in os.listdir(_cache_dir()):
            caminho = os.path.join(_cache_dir(), nome)
            try:
                if os.path.isfile(caminho) and agora - os.path.getmtime(caminho) > _CACHE_TTL_S:
                    os.remove(caminho)
            except OSError:
                pass
    except OSError:
        pass


def sintetizar(texto: str, voz: str | None = None, rate: str = "+0%") -> str:
    """Gera o áudio MP3 do texto e retorna o caminho do arquivo (com cache).

    - voz "meishu": usa a ElevenLabs (voz clonada de Meishu-Sama, cross-lingual).
      Se a voz não estiver configurada/disponível, faz fallback para o Antonio.
    - demais vozes (antonio/francisca/thalita): edge-tts (gratuito).
    """
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vazio")

    voz_origem = (voz or "").lower()
    usando_meishu = voz_origem == VOZ_MEISHU and voz_meishu_disponivel()

    if voz_origem == VOZ_MEISHU and not usando_meishu:
        # Fallback transparente: voz clonada indisponível → Antonio.
        voz_origem = "antonio"
    voz_real = VOZES_PT_BR.get(voz_origem, VOZ_PADRAO)

    if (rate or "").strip() == "":
        rate = "+0%"

    # A chave de cache precisa incluir o provedor (evita colisão de cache
    # entre edge-tts e ElevenLabs para o mesmo texto).
    provedor = "el" if usando_meishu else "edge"
    chave = _chave_cache(f"{provedor}:{voz_real}", texto, rate)
    destino = os.path.join(_cache_dir(), f"{chave}.mp3")
    if os.path.exists(destino):
        return destino

    _limpar_cache_antigo()

    if usando_meishu:
        # ElevenLabs — chamada HTTP síncrona simples.
        try:
            _sintetizar_elevenlabs(texto, destino, rate=rate)
        except Exception:
            # Fallback para o edge-tts se a ElevenLabs falhar.
            if os.path.exists(destino):
                try:
                    os.remove(destino)
                except OSError:
                    pass
            voz_real = VOZ_PADRAO
            chave = _chave_cache("edge:" + voz_real, texto, rate)
            destino = os.path.join(_cache_dir(), f"{chave}.mp3")
            _gerar_edge(texto, voz_real, rate, destino)
    else:
        _gerar_edge(texto, voz_real, rate, destino)

    if not os.path.exists(destino):
        raise RuntimeError("TTS não gerou o áudio")
    return destino


def _gerar_edge(texto: str, voz_real: str, rate: str, destino: str) -> None:
    """Gera áudio via edge-tts (async) salvando em `destino`."""

    async def _gerar() -> None:
        import edge_tts

        communicate = edge_tts.Communicate(texto, voz_real, rate=rate)
        # Salva direto no destino (edge-tts aceita path).
        await communicate.save(destino)

    try:
        asyncio.run(_gerar())
    except RuntimeError:
        # Loop já rodando (ex.: chamado de dentro de um async context) — usa
        # um loop novo em thread.
        import threading

        resultado: list[str] = []
        def _run() -> None:
            asyncio.run(_gerar())
            resultado.append(destino)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=60)
        if not resultado:
            raise RuntimeError("edge-tts timeout")
    except Exception:
        # Em caso de erro, remove arquivo parcial.
        if os.path.exists(destino):
            try:
                os.remove(destino)
            except OSError:
                pass
        raise
