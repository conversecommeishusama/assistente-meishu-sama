#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria estrutural da segmentação, antes do rebuild dos índices.

Não reinventa a segmentação: chama as **mesmas funções de produção** que o
`build_clean_large_indexes.py` usa (`_load_spec_for`, `article_entries_from_spec`,
`split_chunks`, `pode_cortar_por_tamanho`), para que o resultado aqui seja
exactamente o que o índice vai receber.

Regra do projeto (decisão de 14/07/2026, `build_clean_large_indexes.py`):
a segmentação é sempre pela divisão estrutural do autor — **um artigo = um
segmento**. O corte por contagem de caracteres existe só como excepção nas três
séries de palavra oral (`gokowa_roku_qa`, `ochishiji_roku`, `mioshie_shu`) e
nos 4 ficheiros sem spec documentados em `pode_cortar_por_tamanho`; mesmo aí
nunca parte um turno de fala (`Interlocutor:` / `Meishu-Sama:`).

Duas categorias de achado, ambas necessárias para o veredicto:

  ERRO     -- viola a regra acima ou perde conteúdo; bloqueia o rebuild.
  PREVISTO -- desvio consciente, documentado no código; contabilizado para que
              o veredicto "0 erros" não esconda nada.

Uso:
    .venv/bin/python scripts/auditar_segmentacao_estrutural.py
    .venv/bin/python scripts/auditar_segmentacao_estrutural.py --lista
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

import build_clean_large_indexes as B  # noqa: E402
from apply_manual_livros_segmentacao import (  # noqa: E402
    _eh_inicio_de_bloco as eh_inicio_de_bloco,
    inicio_do_corpo,
    posicoes_das_ancoras,
)

MIN_CHUNK = 40
LIMITE_EMBEDDING = 3200          # e5-large: 512 tokens ~ 3200 chars
FAIXA_RATIO = (1.2, 6.0)         # PT/JP por artigo, referência global


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


class Auditoria:
    def __init__(self) -> None:
        self.erros: list[str] = []
        self.previstos: list[str] = []
        self.cat: Counter = Counter()
        self.tot: Counter = Counter()
        self.por_obra: dict[str, dict] = {}
        self.cortes_orais: list[tuple[str, str]] = []

    # ------------------------------------------------------------- registo
    def erro(self, obra: str, cat: str, msg: str) -> None:
        self.erros.append(f"[{cat}] {obra}: {msg}")
        self.cat[cat] += 1

    def previsto(self, obra: str, cat: str, msg: str) -> None:
        self.previstos.append(f"[{cat}] {obra}: {msg}")
        self.cat[cat] += 1

    # -------------------------------------------------------------- varre
    def audita(self, lang: str, directory: Path) -> None:
        for path in sorted(directory.glob("*.txt")):
            if not B._obra_no_canal(path.name, "chat"):
                self.tot[f"{lang}/fora_do_canal"] += 1
                continue
            spec = B._load_spec_for(path.name)
            par = B._par_emparelhado(lang, path.name)
            self.audita_obra(lang, path, par, spec)

    def audita_obra(self, lang: str, path: Path, par: Path | None,
                    spec: dict | None) -> None:
        nome = path.name
        chave = par.name if (par is not None and lang == "jp") else nome
        info = self.por_obra.setdefault(chave, {})
        lang_info = info.setdefault("langs", {}).setdefault(lang, {})

        arts = (spec or {}).get("articles") or []
        profile = (spec or {}).get("profile")

        # --- obras sem divisão autoral registada ------------------------
        if not spec or len(arts) <= 1:
            motivo = "sem spec" if not spec else f"spec de {len(arts)} artigo"
            entradas = [B.file_entry(path, lang, par)]
            lang_info.update(artigos=len(arts), entradas=1, oral=True)
            self.tot["obras_sem_divisao"] += 1
            self.previsto(nome, "obra-inteira",
                          f"{motivo}: indexada como 1 entrada e cortada por "
                          f"tamanho (decisão de `pode_cortar_por_tamanho`)")
            self.audita_chunks(nome, lang, entradas)
            return

        oral = B.pode_cortar_por_tamanho(profile)
        lang_info.update(artigos=len(arts), oral=oral, profile=profile)
        info["profile"] = profile
        if oral:
            self.cortes_orais.append((nome, profile or "(sem perfil)"))

        # --- 1. estrutura da spec ---------------------------------------
        for campo in ("pt_anchor", "jp_anchor"):
            faltam = [i for i, a in enumerate(arts, 1)
                      if not (a.get(campo) or "").strip()]
            if faltam:
                self.erro(nome, "ancora-vazia",
                          f"{campo} em branco nos artigos {faltam[:8]}")
            vals = [(a.get(campo) or "").strip() for a in arts]
            rep = {v: n for v, n in Counter(vals).items() if v and n > 1}
            if rep:
                # não é erro: o cursor avança, cada ocorrência seguinte resolve
                # para o sítio certo (títulos repetidos em séries de poemas)
                self.previsto(nome, "ancora-repetida",
                              f"{campo} repetida em {len(rep)} valor(es) "
                              f"({[v[:30] for v in list(rep)[:3]]}) — "
                              f"resolvida pelo cursor")

        # --- 2. âncoras no texto limpo ----------------------------------
        texto = B.clean_body(B.read_text(path))
        inicio = inicio_do_corpo(texto)
        campo = "jp_anchor" if lang == "jp" else "pt_anchor"
        ancoras = [(a.get(campo) or "").strip() for a in arts]
        pos: list[int] = []
        try:
            pos = posicoes_das_ancoras(texto, ancoras, label=nome,
                                       inicio=inicio)
        except ValueError as exc:
            self.erro(nome, "ancora-nao-resolve", f"[{lang}] {exc}")
            return
        for i, q in enumerate(pos, start=1):
            if i == 1:
                # a posição da âncora 1 não é fronteira de nada: o artigo 1
                # começa em `inicio` (o corte real é a âncora 2)
                continue
            ant = texto[q - 1] if q else "\n"
            if ant.isalnum():
                self.erro(
                    nome, "corte-ilegitimo",
                    f"[{lang}] artigo {i}: {ancoras[i - 1][:45]!r} corta dentro "
                    f"da palavra {texto[max(0, q - 12):q]!r}|{texto[q:q + 12]!r}")
            elif not eh_inicio_de_bloco(texto, q):
                # corte depois de espaço/pontuação: começa uma frase, verso ou
                # marcador inline. É a divisão do autor, só não está no início
                # da linha -- não parte palavra nem frase.
                self.previsto(
                    nome, "corte-em-limite",
                    f"[{lang}] artigo {i}: {ancoras[i - 1][:40]!r} começa após "
                    f"{texto[max(0, q - 12):q]!r}, dentro de um parágrafo "
                    f"(limite de frase/marcador, não de linha)")

        if pos != sorted(pos) or len(set(pos)) != len(pos):
            self.erro(nome, "ancora-fora-de-ordem",
                      f"[{lang}] posições não estritamente crescentes")

        # 2b. o cabeçalho gerado é saltado; o resto antes da 1.ª âncora passa
        # a integrar o artigo 1 (`split_by_anchors(..., inicio=...)`)
        if inicio:
            self.previsto(nome, "cabecalho-saltado",
                          f"[{lang}] {inicio} chars de cabeçalho gerado "
                          f"(metadados) ficam fora do índice")
        if pos and pos[0] > inicio:
            self.previsto(nome, "prefixo-no-artigo-1",
                          f"[{lang}] {pos[0] - inicio} chars antes do 1.º artigo "
                          f"passam a integrá-lo: "
                          f"{norm(texto[inicio:pos[0]])[:70]!r}")

        # --- 3. o rebuild não pode cair no fallback silencioso ----------
        entradas = B.article_entries_from_spec(path, lang, par, spec)
        if entradas is None:
            self.erro(nome, "fallback-silencioso",
                      f"[{lang}] `article_entries_from_spec` devolveu None com "
                      f"{len(arts)} artigos — o rebuild indexaria a obra inteira "
                      f"como 1 entrada")
            return
        if len(entradas) != len(arts):
            self.erro(nome, "entradas!=artigos",
                      f"[{lang}] {len(entradas)} entradas para {len(arts)} "
                      f"artigos")
            return
        lang_info["entradas"] = len(entradas)

        # --- 3b. cobertura: cada artigo tem de ser exactamente a sua fatia ---
        for i, ent in enumerate(entradas, start=1):
            if "=== ARTIGO ===" in ent["body"] or \
                    "Ficheiro de trabalho" in ent["body"]:
                self.erro(nome, "cabecalho-no-corpo",
                          f"[{lang}] artigo {i}: cabeçalho gerado vazou para o "
                          f"corpo indexado")
        for i, ent in enumerate(entradas, start=1):
            ini_i = inicio if i == 1 else pos[i - 1]
            fim_i = pos[i] if i < len(pos) else len(texto)
            if norm(ent["body"]) != norm(texto[ini_i:fim_i]):
                self.erro(nome, "fatia-desalinhada",
                          f"[{lang}] artigo {i}: o corpo não corresponde à fatia "
                          f"[{ini_i}:{fim_i}] do texto limpo "
                          f"({len(norm(ent['body']))} vs "
                          f"{len(norm(texto[ini_i:fim_i]))} chars)")

        # --- 3c. cobertura independente ---------------------------------
        # Comparação sem nenhum espaço em branco: se um carácter de conteúdo
        # ficou de fora (ou entrou duas vezes), a soma dos artigos deixa de
        # reproduzir o ficheiro. É o teste que não depende das posições
        # usadas para construir os corpos.
        sem_espaco = lambda s: re.sub(r"\s+", "", s)
        soma = "".join(sem_espaco(e["body"]) for e in entradas)
        total_txt = sem_espaco(texto[inicio:])
        if soma != total_txt:
            self.erro(nome, "cobertura",
                      f"[{lang}] os {len(entradas)} artigos não reproduzem o "
                      f"ficheiro: {len(soma)} chars de conteúdo contra "
                      f"{len(total_txt)} (diferença "
                      f"{len(total_txt) - len(soma)})")

        # --- 4. um artigo = um segmento --------------------------------
        self.tot[f"{lang}/artigos"] += len(arts)
        for i, (ent, _art) in enumerate(zip(entradas, arts), start=1):
            corpo = ent["body"]
            titulo = ent.get("title") or ""
            partes = B.split_chunks(corpo, cortar_por_tamanho=oral)
            piso = 1 if (ent.get("autoral") and len(partes) == 1) else MIN_CHUNK
            validos = [p for p in partes if len(p.strip()) >= piso]
            descartados = [p for p in partes if len(p.strip()) < piso]

            if not oral and len(partes) != 1:
                self.erro(nome, "escrita-dividida",
                          f"[{lang}] artigo {i}: palavra escrita originou "
                          f"{len(partes)} chunks (regra: 1)")
            if not validos:
                # o artigo inteiro não chega ao índice: só é perda se o texto
                # não estiver já no título da entrada
                nb, nt = norm(corpo), norm(titulo)
                if nb and nb not in nt:
                    self.erro(nome, "artigo-desaparece",
                              f"[{lang}] artigo {i}: corpo de {len(corpo)} "
                              f"chars < {MIN_CHUNK} e fora do título — não "
                              f"entra no índice: {nb[:70]!r}")
                else:
                    self.tot["entradas_sem_corpo"] += 1
                    self.tot["chars_entradas_sem_corpo"] += len(corpo)
                continue
            for d in descartados:
                dn = norm(d)
                if len(dn) >= 15 and dn not in norm(titulo):
                    self.erro(nome, "chunk-descartado",
                              f"[{lang}] artigo {i}: {len(dn)} chars "
                              f"descartados pelo limite de {MIN_CHUNK} e fora "
                              f"do título: {dn[:70]!r}")
                else:
                    self.previsto(nome, "rotulo-curto",
                                  f"[{lang}] artigo {i}: fragmento de "
                                  f"{len(dn)} chars já coberto pelo título: "
                                  f"{dn[:45]!r}")
            # 4a. nenhum texto do artigo pode faltar nos chunks
            juntos = norm("".join(validos))
            for frase in self.frases_largas(corpo):
                if frase not in juntos:
                    self.erro(nome, "frase-perdida",
                              f"[{lang}] artigo {i}: {frase[:70]!r}")
                    break
            # 4b. palavra oral: nenhum corte pode separar um rótulo de fala
            # do trecho que ele identifica. Exigir rótulo em TODO pedaço seria
            # falso positivo: enquanto nenhum falante foi apresentado, não há
            # rótulo a repetir (medido: 5 de 1.265 pedaços, 0 com rótulo
            # anterior no mesmo corpo).
            if oral and B.SPEAKER_LABEL_RE.search(corpo):
                for j, c in enumerate(validos[1:], start=2):
                    if B.SPEAKER_LABEL_RE.match(c.lstrip()):
                        continue
                    q = corpo.find(c.strip()[:40])
                    if q < 0:
                        continue
                    if any(m.start() < q < m.end()
                           for m in B.SPEAKER_LABEL_RE.finditer(corpo)):
                        self.erro(nome, "corte-no-rotulo",
                                  f"[{lang}] artigo {i}: chunk {j} corta o "
                                  f"rótulo de fala: {c[:50]!r}")
                        break
                    if B.SPEAKER_LABEL_RE.search(corpo[:q]):
                        self.erro(nome, "corte-em-turno",
                                  f"[{lang}] artigo {i}: chunk {j} começa sem "
                                  f"o rótulo do falante já apresentado: "
                                  f"{c[:50]!r}")
                        break
            self.tot["chunks"] += len(validos)
            if len(validos) > 1:
                self.tot["chunks_multiplos"] += 1

        # --- 5. limite do embedding ------------------------------------
        for ent in entradas:
            if len(ent["body"]) > LIMITE_EMBEDDING and not oral:
                self.tot["artigos_acima_limite"] += 1
                self.tot["chars_alem_limite"] += (
                    len(ent["body"]) - LIMITE_EMBEDDING)
        info.setdefault("tamanhos", {})[lang] = [len(e["body"])
                                                 for e in entradas]

    # ------------------------------------------------------------- auxiliares
    @staticmethod
    def frases_largas(corpo: str) -> list[str]:
        out = []
        for f in re.split(r"(?<=[.!?。！？])\s+|\n+", corpo):
            f = norm(f)
            if len(f) >= 40:
                out.append(f)
        return out[:40]

    def audita_chunks(self, nome: str, lang: str,
                      entradas: list[dict]) -> None:
        for ent in entradas:
            cortar = ent.get("cortar_por_tamanho", True)
            partes = B.split_chunks(ent["body"], cortar_por_tamanho=cortar)
            validos = [p for p in partes if len(p.strip()) >= MIN_CHUNK]
            self.tot["chunks"] += len(validos)
            for p in partes:
                if len(p.strip()) < MIN_CHUNK and norm(p) and \
                        norm(p) not in norm(ent.get("title") or ""):
                    self.erro(nome, "chunk-descartado",
                              f"[{lang}] obra sem divisão: {norm(p)[:70]!r}")

    # ------------------------------------------------------------- pares
    def compara_par(self) -> None:
        for nome, info in sorted(self.por_obra.items()):
            langs = info.get("langs", {})
            if "pt" in langs and "jp" in langs:
                pt, jp = langs["pt"], langs["jp"]
                if pt.get("artigos") != jp.get("artigos"):
                    self.erro(nome, "pt!=jp",
                              f"{pt.get('artigos')} artigos em PT, "
                              f"{jp.get('artigos')} em JP")
                continue
            if langs:
                so = next(iter(langs))
                self.previsto(nome, "obra-sem-par", f"existe só em {so.upper()}")

    def compara_tamanhos(self) -> None:
        """Volume PT/JP por artigo, contra a mediana da própria obra.

        Não é um teste de segmentação: mede quanto texto a tradução ocupa em
        relação ao original. Serve de sinal para revisão editorial (artigo cuja
        tradução ficou mais curta ou que absorveu texto de outro), não como
        critério de fronteira -- a fronteira é verificada por
        `corte-ilegitimo`/`corte-em-limite`, que olham o texto, não o tamanho.
        """
        for nome, info in sorted(self.por_obra.items()):
            tam = info.get("tamanhos", {})
            pt, jp = tam.get("pt"), tam.get("jp")
            if not pt or not jp or len(pt) != len(jp):
                continue
            razoes = [a / b for a, b in zip(pt, jp) if a > 150 and b > 150]
            if len(razoes) < 4:
                continue
            mediana = statistics.median(razoes)
            if not (FAIXA_RATIO[0] <= mediana <= FAIXA_RATIO[1]):
                self.avisos.append(
                    f"{nome}: razão PT/JP mediana {mediana:.2f} fora de "
                    f"{FAIXA_RATIO} — o par PT/JP desta obra merece revisão")
            for i, (a, b) in enumerate(zip(pt, jp), start=1):
                if a < 250 or b < 250:
                    continue
                r = a / b
                if r < mediana / 2.5 or r > mediana * 2.5:
                    self.previsto(nome, "volume-pt-jp",
                                  f"artigo {i}: PT {a} chars / JP {b} chars "
                                  f"(razão {r:.2f}, mediana {mediana:.2f}) — "
                                  f"volume de tradução, fronteira verificada")

    def audita_sem_corpo(self) -> None:
        """Entradas da spec cujo corpo é só título/linha de rosto."""
        n = self.tot["entradas_sem_corpo"]
        c = self.tot["chars_entradas_sem_corpo"]
        if not n:
            return
        total = self.tot["pt/artigos"] * 1.0
        self.previsto("acervo", "entradas-sem-corpo",
                      f"{n} entradas da spec ({c} chars, ~{c / 5_400_000:.2%} "
                      f"do texto indexável) têm por corpo apenas o título ou a "
                      f"linha de rosto já presente no campo `title`; o builder "
                      f"descarta-as pela regra dos {MIN_CHUNK} chars "
                      f"(`build_chunks`). Nenhuma perde prosa de artigo.")
        _ = total

    # ------------------------------------------------------------- relatório
    def relatorio(self, listar: bool) -> int:
        print("=" * 74)
        print("AUDITORIA DA SEGMENTAÇÃO ESTRUTURAL (pré-rebuild)")
        print("=" * 74)
        for k in sorted(self.tot):
            print(f"  {k:<34} {self.tot[k]}")

        perfis = Counter(p or "(sem perfil)" for _, p in self.cortes_orais)
        print(f"\n  obras com corte por tamanho: {len(self.cortes_orais)}")
        for p, n in perfis.most_common():
            print(f"      {p:<26} {n}")

        if self.cat:
            print("\n" + "=" * 74)
            print("ACHADOS POR CATEGORIA")
            print("=" * 74)
            for k, v in self.cat.most_common():
                print(f"  {v:>6}  {k}")

        print("\n" + "=" * 74)
        if self.erros:
            print(f"ERROS: {len(self.erros)}")
            limite = len(self.erros) if listar else 40
            for e in self.erros[:limite]:
                print("  -", e)
            if len(self.erros) > limite:
                print(f"  ... +{len(self.erros) - limite}")
        else:
            print("ERROS: 0")

        if self.previstos:
            print(f"\nDESVIOS PREVISTOS (documentados, não bloqueiam): "
                  f"{len(self.previstos)}")
            limite = len(self.previstos) if listar else 15
            for p in self.previstos[:limite]:
                print("  ·", p)
            if len(self.previstos) > limite:
                print(f"  ... +{len(self.previstos) - limite}")
        return 1 if self.erros else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lista", action="store_true",
                    help="mostra todos os achados, sem truncar")
    args = ap.parse_args()

    a = Auditoria()
    a.audita("pt", B.PT_DIR)
    a.audita("jp", B.JP_DIR)
    a.compara_par()
    a.compara_tamanhos()
    a.audita_sem_corpo()
    return a.relatorio(args.lista)


if __name__ == "__main__":
    raise SystemExit(main())
