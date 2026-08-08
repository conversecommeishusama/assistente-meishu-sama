"""Remove o negrito markdown usado como convenção de título.

Decisão do usuário (2026-08-08): 944 ocorrências em 24 das 137 obras; as outras
113 usam texto simples. O título continua sendo título pela segmentação, não
pelo asterisco -- e o `**` aparece cru para quem lê a resposta da busca, que
não interpreta markdown.

Dois casos, tratados de forma diferente:

  876 ocupam a linha inteira -- basta tirar os asteriscos.
  103 abrem o parágrafo com o corpo colado ("**Título** Sobre este ponto...").
      Tirar só os asteriscos funde o título ao texto, então aqui entra também
      a quebra de parágrafo, deixando-os como nas outras 113 obras.

Não toca em `**` que não feche na mesma linha nem em ênfase dentro de frase
(negrito com texto antes E depois na mesma linha).

Uso:
    python3 scripts/remove_negrito_titulo.py            # diagnóstico
    python3 scripts/remove_negrito_titulo.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import reaplica_semantico as R  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

NEGRITO = re.compile(r"\*\*([^*\n]+)\*\*")


def limpa(texto: str) -> tuple[str, int, int]:
    saida, cursor, so_linha, abre = [], 0, 0, 0
    for m in NEGRITO.finditer(texto):
        ini_linha = texto.rfind("\n", 0, m.start()) + 1
        fim_linha = texto.find("\n", m.end())
        if fim_linha < 0:
            fim_linha = len(texto)
        antes = texto[ini_linha:m.start()].strip()
        depois = texto[m.end():fim_linha].strip()

        if antes:
            continue                      # ênfase no meio da frase: não mexe
        saida.append(texto[cursor:m.start()])
        if depois:
            saida.append(m.group(1).strip() + "\n\n")
            cursor = m.end()
            while cursor < len(texto) and texto[cursor] in " \t":
                cursor += 1
            abre += 1
        else:
            saida.append(m.group(1).strip())
            cursor = m.end()
            so_linha += 1
    saida.append(texto[cursor:])
    return "".join(saida), so_linha, abre


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tot_l = tot_a = obras = 0

    for p in sorted(R.PT_FONTE.glob("*.txt")):
        texto = p.read_text(encoding="utf-8")
        if "**" not in texto:
            continue
        novo, nl, na = limpa(texto)
        if novo == texto:
            continue
        obras += 1
        tot_l += nl
        tot_a += na
        print(f"  {p.name[:44]:<46} {nl:>4} de linha, {na:>3} abrindo parágrafo")
        if aplicar:
            p.with_suffix(f".txt.bak_pre_negrito_{carimbo}").write_text(
                texto, encoding="utf-8")
            p.write_text(novo, encoding="utf-8")
            st = R.PT_STAGING / p.name
            if st.exists():
                st.write_text(novo, encoding="utf-8")

    print(f"\n{tot_l} de linha inteira + {tot_a} abrindo parágrafo, em {obras} obras")
    if not aplicar:
        print("(diagnóstico apenas -- rode com --aplicar)")
        return

    ruins = 0
    for p in sorted(R.PT_FONTE.glob("*.txt")):
        sp = R.SPEC_DIR / f"{p.name}.json"
        if not sp.exists():
            continue
        anc = [a.get("pt_anchor", "") for a in
               json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
        if len(anc) <= 1 or not all(anc):
            continue
        for base in (R.PT_FONTE, R.PT_STAGING):
            f = base / p.name
            if not f.exists():
                continue
            try:
                if len(split_by_anchors(clean_body(f.read_text(encoding="utf-8")),
                                        anc, label=p.name)) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBRADA {base.name}/{p.name}: {str(exc)[:90]}")
                ruins += 1
    print(f"verificação: {ruins} âncoras quebradas")


if __name__ == "__main__":
    main()
