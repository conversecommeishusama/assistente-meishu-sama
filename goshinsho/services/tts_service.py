"""Serviço de TTS (texto → fala) usando edge-tts (vozes neurais gratuitas).

2026-08-27: implementado para a Leitura Colaborativa do protótipo (/versao2).
Motivo: o speechSynthesis do navegador não roteia o áudio pelo perfil de
mídia do bluetooth no Android (carro) — apps como Spotify/Google Maps tocam
normalmente, mas o TTS do navegador fica mudo. O `<audio>` com um MP3 gerado
no servidor segue o perfil de mídia do bluetooth normalmente.

Edge TTS usa o serviço gratuito de síntese da Microsoft (vozes neurais).
Não requer API key. As vozes pt-BR: pt-BR-AntonioNeural (masc), 
pt-BR-FranciscaNeural (fem), pt-BR-ThalitaMultilingualNeural (fem).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import time

VOZES_PT_BR = {
    "antonio": "pt-BR-AntonioNeural",
    "francisca": "pt-BR-FranciscaNeural",
    "thalita": "pt-BR-ThalitaMultilingualNeural",
}
VOZ_PADRAO = "pt-BR-AntonioNeural"

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


def _chave_cache(texto: str, voz: str, rate: str) -> str:
    raw = f"{voz}|{rate}|{texto}"
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
    """Gera o áudio MP3 do texto e retorna o caminho do arquivo (com cache)."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vazio")
    voz_real = VOZES_PT_BR.get((voz or "").lower(), VOZ_PADRAO)
    if (rate or "").strip() == "":
        rate = "+0%"

    chave = _chave_cache(texto, voz_real, rate)
    destino = os.path.join(_cache_dir(), f"{chave}.mp3")
    if os.path.exists(destino):
        return destino

    _limpar_cache_antigo()

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

    if not os.path.exists(destino):
        raise RuntimeError("edge-tts não gerou o áudio")
    return destino
