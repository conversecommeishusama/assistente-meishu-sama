"""Verifica semanticamente TODA mudança feita hoje, sem amostragem.

Determinação do usuário (2026-08-08): *"verifique todo o trabalho realizado
hoje de forma semântica, tudo o que foi feito sem exceção, depois de
dimensionar corretamente o problema vamos ver o que fazer."* E, em seguida:
*"e sem fazer por amostragem, fazer tudo sem exceção."*

Lê os 1.292 trechos do inventário -- cada um com o texto antes, o texto
depois e o japonês do artigo -- e julga se a alteração é correta.

Pré-requisito: scripts/inventario_mudancas_hoje.py

Uso:
    python3 scripts/verifica_mudancas_hoje.py
    python3 scripts/verifica_mudancas_hoje.py --resumo
"""

from __future__ import annotations

import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from goshinsho.services import agentic_search as ag  # noqa: E402

ENTRADA = RAIZ / "reports/varredura_padronizacao/INVENTARIO_HOJE.json"
DESTINO = RAIZ / "reports/varredura_padronizacao/VERIFICACAO_HOJE.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 8

SYSTEM = """Você audita alterações feitas hoje na tradução portuguesa do acervo de Meishu-Sama.

Recebe, de um mesmo trecho: o texto ANTES da alteração, o texto DEPOIS, e o JAPONÊS do artigo a que o trecho pertence.

Sua tarefa é dizer se a alteração está correta à luz do japonês.

As alterações previstas hoje foram estas, todas decididas pelo usuário:
  地上天国 -> "Paraíso Terrestre" (antes "Paraíso na Terra"); em citação de periódico o nome antigo foi preservado de propósito
  浄化作用 -> "processo de purificação", podendo alternar com "ação purificadora" para evitar repetição próxima
  野菜 -> "hortaliças" ("legumes" se o texto enumera só não-folhas, "verduras" se só folhas); NUNCA "vegetais"
  御屏風観音様 -> "Byōbu Kannon", sem artigo, com "(Kannon do biombo)" só na 1ª menção do arquivo
  祝詞 -> "norito"          支部 -> "filial"        大光明如来 -> "Daikōmyō Nyorai"
  悪霊 -> "espíritos malignos"   中教会 -> "Igreja Média"   大先生 -> "Grão-Mestre"
  真善美 -> "a Verdade, o Bem e o Belo"   五六七の世 -> "Mundo de Miroku"
  報恩感謝 -> "retribuição em gratidão"   凝結 -> "solidificação"
  肺結核 -> "tuberculose pulmonar"   解毒作用 -> "processo de desintoxicação"

ATENÇÃO — um script defeituoso trocou termos no arquivo inteiro quando só um artigo justificava. Procure ativamente por isso:
  - "norito" onde o japonês traz 祈り, 祈願 ou お祈り (deveria ser "oração"/"prece")
  - "Daikōmyō Nyorai" onde o japonês traz só 光明如来 sem o 大 (deveria ser "Komyo-Nyorai" — são DUAS imagens diferentes)
  - "filial" onde o japonês não traz 支部
  - "espíritos malignos" onde o japonês traz 邪神 (que é "Divindades malignas", termo distinto)
  - qualquer troca que o japonês daquele artigo não sustente

Verifique também gramática: concordância de gênero e número que a troca possa ter quebrado, e artigo ou preposição que tenha sobrado ou faltado.

FORMATO — responda só isto:

VEREDITO: <CORRETO|ERRADO|INCERTO>
PROBLEMA: <se ERRADO, o que está errado, em uma frase; senão "-">
CORRECAO: <se ERRADO, o trecho exato a substituir e o texto correto, no formato: "trecho atual" => "trecho corrigido"; senão "-">

Se houver mais de um problema no mesmo trecho, liste uma linha CORRECAO por problema. Nunca proponha trecho que não esteja no texto DEPOIS."""


def julga(item: dict) -> dict:
    pedido = (
        f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n\n"
        f"=== ANTES ===\n{item['antes']}\n\n"
        f"=== DEPOIS (estado atual) ===\n{item['depois']}\n\n"
        f"=== JAPONÊS DO ARTIGO ===\n{item['jp'][:3000]}")
    texto, tokens, tent = "", 0, 0
    while not texto.strip() and tent < 3:
        tent += 1
        extra = "\n\nIMPORTANTE: responda DIRETAMENTE no formato." if tent > 1 else ""
        r = ag._client().chat.completions.create(
            model=MODELO, max_tokens=12000,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido + extra}])
        u = r.usage
        tokens += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
        texto = r.choices[0].message.content or ""
    ver = re.search(r"VEREDITO:\s*(\w+)", texto)
    prob = re.search(r"PROBLEMA:\s*(.+)", texto)
    cors = re.findall(r"CORRECAO:\s*(.+)", texto)
    return {
        "obra": item["obra"], "artigo": item["artigo"],
        "veredito": ver.group(1).upper() if ver else "SEM_PARSE",
        "problema": prob.group(1).strip() if prob else "",
        "correcoes": [c.strip() for c in cors if c.strip() and c.strip() != "-"],
        "tokens": tokens, "bruto": texto,
    }


def resumo() -> None:
    d = json.loads(DESTINO.read_text(encoding="utf-8"))
    c = Counter(r.get("veredito", "ERRO") for r in d)
    print(f"{len(d)} trechos verificados")
    for k, v in c.most_common():
        print(f"  {k:<14} {v}")
    err = [r for r in d if r.get("veredito") == "ERRADO"]
    por_obra = Counter(r["obra"] for r in err)
    print(f"\n{len(err)} trechos com erro, em {len(por_obra)} obras")
    for obra, n in por_obra.most_common(12):
        print(f"  {n:>4}  {obra[:56]}")


def main() -> None:
    if "--resumo" in sys.argv:
        resumo()
        return
    itens = json.loads(ENTRADA.read_text(encoding="utf-8"))
    feitos = []
    if DESTINO.exists():
        feitos = json.loads(DESTINO.read_text(encoding="utf-8"))
        vistos = {(r["obra"], r["artigo"]) for r in feitos}
        itens = [i for i in itens if (i["obra"], i["artigo"]) not in vistos]
        print(f"retomando: {len(feitos)} já feitos, {len(itens)} restantes", flush=True)
    print(f"{len(itens)} trechos a verificar\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "veredito": "ERRO_API", "problema": repr(exc)[:140], "correcoes": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            if n[0] % 10 == 0 or r["veredito"] == "ERRADO":
                print(f"[{n[0]:>4}/{len(itens)}] {r['obra'][:28]:<30} art{r['artigo']:<4} "
                      f"{r['veredito']}", flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    tk = sum(r.get("tokens", 0) for r in feitos)
    print(f"\n{len(feitos)} verificados | {tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.3f}")
    resumo()


if __name__ == "__main__":
    main()
