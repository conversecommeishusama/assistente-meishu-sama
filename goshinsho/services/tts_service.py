"""Serviço de TTS (texto → fala): edge-tts (vozes neurais gratuitas) + voz
clonada de Meishu-Sama via XTTS local (cross-lingual japonês → português).

2026-08-27: implementado para a Leitura Colaborativa do protótipo (/versao2).
Motivo: o speechSynthesis do navegador não roteia o áudio pelo perfil de
mídia do bluetooth no Android (carro) — apps como Spotify/Google Maps tocam
normalmente, mas o TTS do navegador fica mudo. O `<audio>` com um MP3 gerado
no servidor segue o perfil de mídia do bluetooth normalmente.

Edge TTS usa o serviço gratuito de síntese da Microsoft (vozes neurais).
Não requer API key. As vozes pt-BR: pt-BR-AntonioNeural (masc),
pt-BR-FranciscaNeural (fem), pt-BR-ThalitaMultilingualNeural (fem).

2026-09-01/02: voz 'meishu' — voz clonada de Meishu-Sama (amostra de áudio
histórica de 1952) falando PORTUGUÊS (cross-lingual) via XTTS v2 LOCAL
(Coqui, roda no próprio servidor — sem custo de API). O XTTS roda num venv
isolado (venv_xtts) via subprocess, porque o ambiente de produção (venv) não
tem o coqui-tts (evita conflito de transformers).

DIÁLOGO (2026-09-02): quando a voz escolhida é 'meishu' e o trecho começa com
um rótulo de fala, o falante decide o provedor:
  - "Meishu-Sama: ..."  → voz clonada (XTTS local)
  - "Interlocutor: ..." e demais rótulos que não são Meishu-Sama → Antônio
    (edge-tts, voz neural masculina) — para diferenciar os interlocutores.
  - texto corrido (sem rótulo) → voz clonada (XTTS), padrão da opção.

Config (via .env):
  GOSHINSHO_XTTS_PYTHON=/var/www/goshinsho/venv_xtts/bin/python
  GOSHINSHO_XTTS_AMOSTRA=/var/www/goshinsho/amostras_voz/amostra_meishu_30s_limpa.wav
  GOSHINSHO_XTTS_MODELO=tts_models/multilingual/multi-dataset/xtts_v2
  GOSHINSHO_XTTS_CACHE=/var/www/goshinsho/data/tts_xtts_cache
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import tempfile
import time

VOZES_PT_BR = {
    "antonio": "pt-BR-AntonioNeural",
    "francisca": "pt-BR-FranciscaNeural",
    "thalita": "pt-BR-ThalitaMultilingualNeural",
    # "meishu" é sentinela: encaminha para o XTTS local (voz clonada).
    "meishu": "__xtts_meishu__",
}
VOZ_PADRAO = "pt-BR-AntonioNeural"
VOZ_MEISHU = "meishu"
VOZ_INTERLOCUTOR = "pt-BR-AntonioNeural"  # edge-tts (Antônio) p/ não-Meishu

# Versão da amostra de voz usada na clonagem XTTS. Incluída na CHAVE do cache
# para que, ao trocar a amostra (ex.: para a remasterizada), os áudios antigos
# NÃO sejam reutilizados — força regeneração com a voz nova.
# 2026-09-05: v1 = amostra antiga (amostra_meishu_30s_limpa); v2 = remasterizada
# (amostra_meishu_oficial.wav, aprovada). Manter em sincronia com o gerador GPU
# (scripts/gerar_gpu.py → VOZ_MEISHU_CACHE).
VOZ_MEISHU_CACHE = "meishu:v2"

# Rótulos de fala nos diálogos (início de parágrafo). "Meishu-Sama" é a voz
# clonada; qualquer outro rótulo (Interlocutor, Alguém, Mestre...) é o
# interlocutor → Antônio.
_LABEL_MEISHU = re.compile(r"^\s*(?:meishu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:", re.IGNORECASE)
_LABEL_DIALOGO = re.compile(r"^\s*([^:]{2,40}):\s*")

# ---------------------------------------------------------------------------
# Transformação do texto para o TTS (2026-09-05)
#
# ANTES (bug): o front (leitura_tts.js) aplicava as pronúncias + sanitização e
# só então enviava o texto ao servidor. Isso (1) quebrava o roteamento — a fala
# "Meishu-Sama:" virava "Meichu-Sama:" e o servidor a classificava como
# Interlocutor → Antônio (em vez da voz clonada); e (2) fazia a chave do cache
# divergir da usada pelo gerador GPU (que usa o texto CRU).
#
# AGORA: o front envia o texto CRU; o servidor decide o falante pelo CRU e
# aplica a transformação (pronúncias + remoção de macrons + sanitização) aqui,
# de forma consistente para o app e para o gerador GPU.
# ---------------------------------------------------------------------------

# Tabela de pronúncias para o TTS. MESMA do leitura_tts.js (PRONUNCIAS) — ao
# alterar uma, altere a outra (e o gerador GPU scripts/gerar_gpu.py).
# Ordem importa: termos mais longos/compostos PRIMEIRO (senão "Meishu" "come"
# "Meishu-Sama").
PRONUNCIAS_TTS: list[tuple[str, str]] = [
    ("Meishu-Sama", "Meichu-Sama"),
    ("Meishu Sama", "Meichu Sama"),
    ("Meishu", "Meichu"),
    ("Johrei", "Jyorei"),
    ("Ohikari-Sama", "Oricari-Sama"),
    ("Ohikari", "Oricari"),
    ("Gokōwa-roku", "Gocoua-roku"),
    ("Gokowa-roku", "Gocoua-roku"),
    ("Mioshie-shū", "Miochie-shu"),
    ("Mioshie", "Miochie"),
    ("Daikōmyō", "Daicomio"),
    ("Kōmyō", "Comio"),
    ("Nyorai", "Niorai"),
    ("Jikan", "Jicã"),
    ("Tijotengoku", "Tijotengoku"),
    ("Shinsei", "Chinsei"),
    ("Hannya", "Rania"),
    ("Shukumei", "Chukumei"),
    ("Shinrei", "Chinrei"),
    ("Ōmikami", "Omicami"),
    ("Omikami", "Omicami"),
]

# Regra geral de macron (decisão 2026-09-05): o TTS não deve "ler" as vogais
# longas japonesas (ō/ū/ā/ē/ī) — remove o acento (vogal "normal") para qualquer
# palavra não coberta pela tabela acima (ex.: Byōbu → Byobu, Shōwa → Showa).
# NÃO afeta o texto da tela (só a cópia enviada ao TTS).
_MACRON_MAP = str.maketrans({
    "ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u",
    "Ā": "A", "Ē": "E", "Ī": "I", "Ō": "O", "Ū": "U",
})


def _normalizar_caracteres(texto: str) -> str:
    """Converte caracteres japoneses que quebram o TTS PT-BR para formas ASCII.

    O edge-tts FALHA (NoAudioReceived) com parênteses/aspas japonesas e blocos
    de kanji; o XTTS também não os lê. O texto da TELA não muda — só a cópia
    que vai para o sintetizador.
    """
    out = (texto or "")
    out = out.replace("（", "(").replace("）", ")")
    out = out.replace("「", '"').replace("」", '"')
    out = out.replace("『", '"').replace("』", '"')
    out = out.replace("【", "[").replace("】", "]")
    out = re.sub(r"[〜～]", " ", out)
    out = re.sub(r"[\u4e00-\u9fff]+", "", out)  # remove kanji
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\(\s*\)", "", out)
    return out.strip()


def _aplicar_pronuncias(texto: str) -> str:
    """Aplica a tabela de pronúncias (termo → pronúncia), case-insensitive.

    Mesma lógica do leitura_tts.js (aplicarPronuncias). Ordem preservada:
    mais longo primeiro, substituição global.
    """
    out = texto or ""
    for termo, pron in PRONUNCIAS_TTS:
        out = re.sub(re.escape(termo), pron, out, flags=re.IGNORECASE)
    return out


def _remover_macrons(texto: str) -> str:
    """Remove o acento das vogais longas japonesas (ō→o, ū→u, ā→a, ē→e, ī→i)."""
    return (texto or "").translate(_MACRON_MAP)


def _preparar_texto_xtts(texto: str) -> str:
    """Prepara o texto CRU para o XTTS (voz clonada) sintetizar.

    Aplica: normalização de caracteres → pronúncias → remoção de macrons →
    sanitização de pontuação (vírgulas, remove rótulo de fala e notas).
    """
    t = _normalizar_caracteres(texto)
    t = _aplicar_pronuncias(t)
    t = _remover_macrons(t)
    return _sanitizar_xtts(t)


def _preparar_texto_edge(texto: str) -> str:
    """Prepara o texto CRU para o edge-tts (Antônio/Francisca/Thalita).

    O edge lê a pontuação normalmente (não precisa virar vírgula), mas precisa
    das pronúncias e da remoção de kanji/macrons.
    """
    t = _normalizar_caracteres(texto)
    t = _aplicar_pronuncias(t)
    return _remover_macrons(t)


def _xtts_python() -> str:
    return os.environ.get(
        "GOSHINSHO_XTTS_PYTHON", "/var/www/goshinsho/venv_xtts/bin/python"
    ).strip()


def _xtts_amostra() -> str:
    return os.environ.get(
        "GOSHINSHO_XTTS_AMOSTRA",
        "/var/www/goshinsho/amostras_voz/amostra_meishu_30s_limpa.wav",
    ).strip()


def _xtts_modelo() -> str:
    return os.environ.get(
        "GOSHINSHO_XTTS_MODELO", "tts_models/multilingual/multi-dataset/xtts_v2"
    ).strip()


def voz_meishu_disponivel() -> bool:
    """True se a voz clonada de Meishu-Sama pode ser usada agora (XTTS pronto)."""
    return bool(_xtts_python() and os.path.exists(_xtts_python()) and _xtts_amostra()
                and os.path.exists(_xtts_amostra()))


def _identificar_falante(texto: str) -> str:
    """Identifica o falante de um trecho de diálogo (início do parágrafo).

    Retorna:
      - "meishu"  → fala de Meishu-Sama (voz clonada)
      - "outro"   → fala de interlocutor (não-Meishu) → Antônio
      - ""        → texto corrido (sem rótulo de fala)
    """
    t = (texto or "").lstrip()
    if _LABEL_MEISHU.match(t):
        return "meishu"
    m = _LABEL_DIALOGO.match(t)
    if m:
        return "outro"
    return ""


def _sanitizar_xtts(texto: str) -> str:
    """Prepara o texto para o XTTS ler sem vocalizar pontuação.

    O XTTS tende a ler ponto final como "ponto" e dois-pontos como "dois
    pontos". Troca pontuação problemática por pausas naturais:
    - ponto final ". " → vírgula (pausa curta que o XTTS respeita)
    - ";" e ":" → vírgula
    - remove notas editoriais [entre colchetes] / (entre parênteses)

    NOTA (2026-09-05): esta função recebe o texto JÁ transformado (pronúncias
    aplicadas + macrons removidos + caracteres normalizados), vindo de
    _preparar_texto_xtts.
    """
    out = texto
    # Remove o rótulo de fala (Meishu-Sama:/Interlocutor:) — já foi usado
    # para decidir a voz; não deve ser lido em voz alta.
    out = re.sub(r"^\s*[^:]{2,40}:\s*", "", out)
    out = out.replace(";", ",")
    out = out.replace(":", ",")
    # Ponto final → vírgula (quando seguido de espaço+maúscula ou fim).
    out = re.sub(r"\.(?=\s+[A-ZÀ-Ú])", ",", out)
    out = re.sub(r"\.\s*$", ",", out)
    # Notas editoriais.
    out = re.sub(r"\s*\[[^\]]*\]\s*", " ", out)
    out = re.sub(r"\s*\([^)]*\)\s*", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _quebrar_segmentos_xtts(texto: str, limite: int = 200) -> list[str]:
    """Quebra o texto em segmentos <= limite chars (limite do XTTS p/ pt-BR).

    O XTTS v2 TRUNCA áudio acima de ~203 chars por chamada na língua 'pt'.
    Divide em fronteiras de vírgula/ponto (pausas naturais) e depois por
    espaço se um segmento ainda for longo.
    """
    if len(texto) <= limite:
        return [texto]
    segs: list[str] = []
    atual = ""
    partes = re.split(r"(?<=[,;:.…])\s+", texto)
    for parte in partes:
        if len(atual) + len(parte) + 1 <= limite:
            atual = (atual + " " + parte).strip() if atual else parte
        else:
            if atual:
                segs.append(atual.strip())
            if len(parte) > limite:
                palavras = parte.split()
                atual = ""
                for palavra in palavras:
                    if len(atual) + len(palavra) + 1 <= limite:
                        atual = (atual + " " + palavra).strip() if atual else palavra
                    else:
                        segs.append(atual.strip())
                        atual = palavra
            else:
                atual = parte
    if atual.strip():
        segs.append(atual.strip())
    return segs


# Script helper que roda no venv_xtts (que tem o coqui-tts). Recebe o texto
# via stdin e grava o áudio no destino. O venv de produção NÃO tem o coqui-tts,
# então o tts_service chama este script via subprocess.
_XTTS_HELPER = r"""
import sys, os, time, re, subprocess

def quebrar(t, limite=200):
    if len(t) <= limite:
        return [t]
    segs = []
    atual = ""
    for parte in re.split(r"(?<=[,;:.…])\s+", t):
        if len(atual) + len(parte) + 1 <= limite:
            atual = (atual + " " + parte).strip() if atual else parte
        else:
            if atual:
                segs.append(atual.strip())
            if len(parte) > limite:
                palavras = parte.split()
                atual = ""
                for p in palavras:
                    if len(atual) + len(p) + 1 <= limite:
                        atual = (atual + " " + p).strip() if atual else p
                    else:
                        segs.append(atual.strip())
                        atual = p
            else:
                atual = parte
    if atual.strip():
        segs.append(atual.strip())
    return segs

def main():
    texto = sys.stdin.read()
    destino = sys.argv[1]
    amostra = sys.argv[2]
    modelo = sys.argv[3] if len(sys.argv) > 3 else "tts_models/multilingual/multi-dataset/xtts_v2"
    t0 = time.time()
    from TTS.api import TTS
    tts = TTS(modelo).to("cpu")
    segs = quebrar(texto)
    tmp_dir = os.path.dirname(os.path.abspath(destino))
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_files = []
    try:
        for i, seg in enumerate(segs):
            tmp = os.path.join(tmp_dir, f"_xtts_seg_{os.getpid()}_{i}.wav")
            tts.tts_to_file(text=seg, speaker_wav=amostra, language="pt", file_path=tmp)
            # 2026-09-02: remove silêncio nas bordas de cada segmento para a
            # concatenação não criar "gap" (parada) entre os segmentos. O
            # XTTS costuma deixar ~0,3-0,5s de silêncio no início/fim.
            # start_silence=0.15 remove pausas de até ~0,15s nas bordas (mais
            # agressivo que o default) para a junção ficar contínua.
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp,
                 "-af", ("silenceremove=start_periods=1:start_threshold=-40dB:"
                         "start_silence=0.15,areverse,"
                         "silenceremove=start_periods=1:start_threshold=-40dB:"
                         "start_silence=0.15,areverse"),
                 "-ar", "24000", "-ac", "1", tmp + ".c.wav"],
                check=True, capture_output=True,
            )
            os.replace(tmp + ".c.wav", tmp)
            tmp_files.append(tmp)
        lista = os.path.join(tmp_dir, f"_xtts_lista_{os.getpid()}.txt")
        with open(lista, "w") as f:
            for t in tmp_files:
                f.write(f"file '{t}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista,
             "-c:a", "libmp3lame", "-q:a", "2", destino],
            check=True, capture_output=True,
        )
        try:
            os.remove(lista)
        except OSError:
            pass
    finally:
        for t in tmp_files:
            try:
                os.remove(t)
            except OSError:
                pass
    sys.stderr.write(f"XTTS ok em {time.time()-t0:.0f}s, {len(segs)} seg(s)\n")

main()
"""


def _sintetizar_xtts(texto: str, destino: str, *, rate: str = "+0%") -> None:
    """Gera áudio via XTTS local (Coqui) rodando no venv_xtts (subprocess).

    O XTTS clona a voz a partir da amostra (amostra_meishu_30s_limpa.wav) e
    sintetiza o texto em português (cross-lingual: voz treinada em japonês
    falando PT). Cada chamada carrega o modelo (~30s na 1ª; o cache em disco
    do Flask evita regenerar o mesmo trecho).
    """
    python = _xtts_python()
    amostra = _xtts_amostra()
    modelo = _xtts_modelo()
    if not python or not os.path.exists(python):
        raise RuntimeError("XTTS não configurado (GOSHINSHO_XTTS_PYTHON)")
    if not amostra or not os.path.exists(amostra):
        raise RuntimeError(f"Amostra de voz não encontrada: {amostra}")

    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    proc = subprocess.run(
        [python, "-c", _XTTS_HELPER, destino, amostra, modelo],
        input=texto.encode("utf-8"),
        capture_output=True,
        timeout=900,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"XTTS falhou (rc={proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')[-500:]}"
        )
    if not os.path.exists(destino) or os.path.getsize(destino) == 0:
        raise RuntimeError("XTTS não gerou o áudio")


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

    - voz "meishu": voz clonada de Meishu-Sama (XTTS local). Quando o trecho
      é um diálogo (começa com rótulo de fala), o falante decide o provedor:
        * "Meishu-Sama:" → XTTS (voz clonada)
        * "Interlocutor:" e outros rótulos → Antônio (edge-tts)
        * texto corrido (sem rótulo) → XTTS (voz clonada, padrão da opção)
      Se o XTTS não estiver disponível, faz fallback para o Antônio.
    - demais vozes (antonio/francisca/thalita): edge-tts (gratuito).

    2026-09-05: o `texto` recebido é o CRU (como está no arquivo). O falante é
    decidido pelo CRU (corrige o bug em que a pronúncia do front "Meichu-Sama:"
    era classificada como Interlocutor). A transformação de pronúncia/macron/
    sanitização acontece AQUI no servidor, e a chave do cache usa o texto CRU
    (alinhado com o gerador GPU).
    """
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vazio")

    voz_origem = (voz or "").lower()
    if (rate or "").strip() == "":
        rate = "+0%"

    # Decide o provedor real com base na voz pedida + falante do diálogo.
    # O falante é identificado no texto CRU (sem pronúncias aplicadas).
    if voz_origem == VOZ_MEISHU:
        if not voz_meishu_disponivel():
            # Fallback transparente: XTTS indisponível → Antônio (edge).
            return _sintetizar_com_cache("edge", VOZ_PADRAO, texto, rate)
        falante = _identificar_falante(texto)
        if falante == "outro":
            # Interlocutor (não-Meishu) → Antônio (edge-tts).
            return _sintetizar_com_cache("edge", VOZ_INTERLOCUTOR, texto, rate)
        # Meishu-Sama ou texto corrido → XTTS (voz clonada).
        return _sintetizar_com_cache("xtts", VOZ_MEISHU_CACHE, texto, rate)

    voz_real = VOZES_PT_BR.get(voz_origem, VOZ_PADRAO)
    return _sintetizar_com_cache("edge", voz_real, texto, rate)


def _sintetizar_com_cache(provedor: str, voz_real: str, texto: str, rate: str) -> str:
    """Gera o áudio (edge-tts ou XTTS) com cache em disco, conforme o provedor.

    `texto` é sempre o CRU (como no arquivo). A chave do cache é calculada
    sobre o texto cru — é o que permite ao gerador GPU (scripts/gerar_gpu.py)
    produzir arquivos com o MESMO nome que o app procura. Para o XTTS,
    `voz_real` carrega a versão da amostra (ex.: "meishu:v2") para forçar
    regeneração ao trocar a amostra.
    """
    chave = _chave_cache(f"{provedor}:{voz_real}", texto, rate)
    destino = os.path.join(_cache_dir(), f"{chave}.mp3")
    if os.path.exists(destino):
        return destino

    _limpar_cache_antigo()

    if provedor == "xtts":
        # Voz clonada (Meishu-Sama) via XTTS local. Prepara o texto no servidor:
        # normaliza caracteres, aplica pronúncias, remove macrons e sanitiza.
        texto_tts = _preparar_texto_xtts(texto)
        if not texto_tts:
            raise ValueError("texto vazio após preparar")
        try:
            _sintetizar_xtts(texto_tts, destino, rate=rate)
        except Exception:
            # Fallback: se o XTTS falhar, tenta o Antônio (edge-tts).
            if os.path.exists(destino):
                try:
                    os.remove(destino)
                except OSError:
                    pass
            destino_fb = _sintetizar_com_cache("edge", VOZ_PADRAO, texto, rate)
            return destino_fb
    else:
        # Edge-tts: também recebe o texto preparado (pronúncias + sem kanji/
        # macron), pois precisa ler "Meichu-Sama", "Jyorei", etc. corretamente.
        texto_edge = _preparar_texto_edge(texto)
        if not texto_edge:
            raise ValueError("texto vazio após preparar")
        _gerar_edge(texto_edge, voz_real, rate, destino)

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
