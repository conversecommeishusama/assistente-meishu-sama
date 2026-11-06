# 📊 Relatório — Alternativas ao ElevenLabs p/ voz clonada nível kikivoice
**Data:** 09/09/2026 · **Contexto:** geração de áudio da voz do Meishu-Sama (83 textos orais, ~16.262 trechos, corpus ≈ **7,36M caracteres** / 7,62 MB UTF-8)

---

## TL;DR (resumo executivo)

**Sim, existem alternativas acessíveis.** A melhor descoberta é a **Fish Audio**:
- **API grátis** (`s2.1-pro-free`) com o modelo TOPO de linha (S2.1 Pro), 83 idiomas
 (inclui português), clonagem de voz incluída — **US$ 0**.
- Modelo open-source (S2 Pro) que roda no SEU pod GPU (24GB VRAM — o RunPod RTX
 3090 24GB serve) — sem custo por caractere, só a GPU (~US$ 0,50/h).

**Ressalvas importantes:**
1. O free tier da Fish Audio era promocional (blog citava "até 31/ago/2026" com
 extensões). **É preciso confirmar se ainda vigora em set/2026** — criar conta e
 testar 1 chamada. O preço pago é US$ 15/M bytes (~US$ 110 p/ nosso corpus
 completo — ainda 10× mais barato que ElevenLabs).
2. O open-source S2 Pro tem **licença research/não-comercial** (uso comercial exige
 licença da Fish). Para uso devocional/educacional sem fins lucrativos, é
 aceitável — mas é decisão sua confirmar o enquadramento.
3. O S2 exige **24GB VRAM** → o pod RTX 3090 24GB que você já usa serve.

---

## 📋 Comparação das APIs (custo p/ TODO o corpus de 7,36M chars)

| Provedor | Modelo | Preço | Custo corpus ~7,36M chars | Clonagem | PT-BR | Notas |
|---|---|---|---|---|---|---|
| **Fish Audio** | `s2.1-pro-free` | **US$ 0** (se ainda ativo) | **~US$ 0** | ✅ instantânea/persistente | ✅ (83 línguas) | Mesmo modelo do pago; sem SLA; fair use |
| **Fish Audio** | `s2.1-pro` (pago) | US$ 15/M bytes | **~US$ 110** | ✅ | ✅ | ~10× mais barato que ElevenLabs |
| **MiniMax** | `speech-2.8-turbo` | US$ 60/M chars | ~US$ 442 | ✅ ($1,5/voz) | ✅ (40 línguas, inclui PT) | Qualidade muito alta (2ª melhor) |
| **MiniMax** | `speech-2.8-hd` | US$ 100/M chars | ~US$ 736 | ✅ | ✅ | Máxima qualidade |
| **Cartesia** | Sonic | por crédito/minuto | **~US$ 5-50/mês** (assíncrono) | ✅ | ? (verificar) | Modelo #1 em baixa latência; plano Pro US$ 5/mês dá ~133 min |
| **ElevenLabs** | v3 | US$ 990/mês (Business) | **US$ 830-1.100** | ✅ | ✅ | **Descartado** (caro) |
| **Kikivoice** | — | grátis (manual) | inviável (sem API) | ✅ | ✅ | **Já temos a amostra** |

**Cálculo real (medido no corpus):** 7.363.584 chars ≈ 7,62 MB UTF-8.
- Fish pago (por byte): 7,62 × $15 = **~$114**
- MiniMax turbo (por char): 7,36 × $60 = **~$442**
- MiniMax hd: 7,36 × $100 = **~$736**
- ElevenLabs: **~$830-1.100** (referência do que estamos evitando)

---

## 🏆 RECOMENDAÇÃO #1 — Fish Audio (API)

**Por que é a melhor resposta à sua pergunta:**
- É o que mais se aproxima do **modelo open-source nível kikivoice COM API**.
- O **mesmo** modelo topo de linha da Fish (S2.1 Pro) está **grátis via API** para
 desenvolvimento/pequenos negócios (US$ 0), com clonagem de voz por upload de
 amostra (igual ao que você faria no kikivoice, mas automatizado).
- 83 idiomas, incluindo **português** — ideal para o texto PT clonar a voz do
 Meishu-Sama.
- Benchmark (Seed-TTS Eval): **melhor WER** entre todos (incluindo MiniMax,
 Seed-TTS) e **melhor similaridade de voz (SIM)** na maioria das línguas.

**Como funciona a clonagem (simples):**
```bash
# 1. Cria o modelo de voz a partir da amostra (a kikivoice que você já tem!)
curl -X POST https://api.fish.audio/model \
 -H "Authorization: Bearer $FISH_API_KEY" \
 -F type=tts -F title="Meishu-Sama" -F train_mode=fast \
 -F voices=@amostra_meishu_kikivoice.wav
# → retorna um voice_id

# 2. Gera cada trecho com a voz clonada
curl -X POST https://api.fish.audio/v1/tts \
 -H "Authorization: Bearer $FISH_API_KEY" \
 -H "model: s2.1-pro-free" \
 -d '{"text": "Isto é de Sotatsu...", "reference_id": "<voice_id>"}'
```
- Suporta **clonagem instantânea** (envia a amostra inline a cada chamada) ou
 **persistente** (cria 1 voice_id e reutiliza — ideal p/ nosso caso).
- `enhance_audio_quality=true` (default) limpa ruído da amostra automaticamente.

**Pontos de atenção:**
- Free tier: sem SLA/latência garantida, e **pode não estar mais ativo** (promo
 terminava 31/ago, com histórico de extensões). Confirmar criando conta.
- Uso comercial do free: restrito acima de US$ 1M ARR (não é nosso caso).
- Se o free cair, o pago (~$110 p/ tudo) ainda é 10× mais barato que ElevenLabs.

---

## 🏆 RECOMENDAÇÃO #2 — Fish Audio S2 (open-source, no SEU pod GPU)

**A opção mais barata a longo prazo** (custo = só a GPU que você já aluga):
- Modelo **S2 Pro (4B params)** open-source — mesmo modelo da API, roda local.
- Requisito: **24GB VRAM** → o RunPod RTX 3090 24GB que você já usa **serve**.
- Suporta clonagem rápida com 10-30s de amostra, 80+ línguas (PT incluso).
- Custo: só o pod (~US$ 0,50/h). Os ~16 mil trechos a ~2-5s cada na GPU =
 **~US$ 3-8** de GPU (vs ~US$ 830 do ElevenLabs).
- Docker/instalação prontos (speech.fish.audio/install).

**Ponto de atenção — LICENÇA:**
- Licença **"Fish Audio Research License"**: uso **research e não-comercial** grátis;
 uso **comercial exige licença** separada da Fish.
- Para seu projeto (textos devocionais do Meishu-Sama, sem fins lucrativos
 aparentes), enquadra-se como **não-comercial** → aceitável. MAS é uma decisão
 que **você deve confirmar** (o site/app tem doações? receita?).

---

## 📋 Outras candidatas avaliadas (por que ficaram de fora)

| Modelo/API | Licença | PT-BR | Clonagem | Veredito |
|---|---|---|---|---|
| **MiniMax Speech 2.8** | API paga | ✅ (40 línguas) | ✅ | Excelente qualidade, mas $442+ p/ volume — 4× o Fish pago |
| **Cartesia Sonic** | API | ? | ✅ | Bom p/ tempo real; plano $5/mês dá pouco p/ 16k trechos |
| **Kokoro-82M** | Apache 2.0 (comercial OK) | ❌ (não pt) | ❌ (só vozes fixas) | Não serve (sem clonagem por referência) |
| **F5-TTS** | código MIT, **modelo CC-BY-NC** | ~ | ✅ | Modelo não-comercial; qualidade inferior ao S2 |
| **IndexTTS-2/2.5** | própria (não-comercial?) | ❌ (2.5: zh/en/ja/es/ar) | ✅ | Sem português no 2.5 |
| **Spark-TTS** | CC-BY-NC-SA | ❌ (zh/en) | ✅ | Não-comercial + sem PT |
| **ChatTTS** | AGPL + CC-BY-NC | ❌ (zh/en) | limitada | Não serve |
| **PlayHT** | API | — | — | Site não carregou p/ preços |

**Nota:** quase todos os modelos open-source de clonagem de alta qualidade são
**não-comerciais** (CC-BY-NC) — é o padrão da indústria hoje. O único Apache-2.0
comercial (Kokoro) não faz clonagem por referência. Isso reforça que, para
**clonar a voz do Meishu-Sama por referência**, as opções realistas são:
**Fish Audio** (API grátis/barata OU open-source não-comercial) e **MiniMax**
(API paga).

---

## 🎯 Plano de ação sugerido (para amanhã)

1. **Testar a Fish Audio grátis** (5 min):
 - Criar conta em fish.audio → gerar API key.
 - Rodar 1 script: clonar a voz com a `amostra_meishu_kikivoice.wav` e gerar o
 MESMO trecho de teste ("É o espírito de alguém que morreu em um acidente de
 avião...") para comparar lado a lado com o XTTS atual.
 - Isso responde: (a) o free ainda vigora? (b) a qualidade é nível kikivoice?
2. **Se a qualidade agradar**, decidir a via:
 - **Via A (API grátis/paga):** integrar Fish Audio no `tts_service.py` como
 provedor da voz meishu (substituindo/ao lado do XTTS). Custo ~$0-110 p/ tudo.
 - **Via B (open-source no pod):** subir o S2 no RunPod (24GB), gerar os 16k
 trechos por ~$3-8 de GPU. Custo mínimo, mas licença não-comercial (confirmar
 enquadramento).
3. **Comparar com o XTTS atual** (que já tem ~88% do corpus gerado) para decidir
 se vale regenerar tudo.

---

## 📎 Links úteis
- Fish API pricing: https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits
- Fish voice cloning: https://docs.fish.audio/features/voice-cloning
- Fish open-source S2: https://github.com/fishaudio/fish-speech
- Fish S2 instalação: https://speech.fish.audio/install/
- MiniMax pricing: https://platform.minimax.io/docs/guides/pricing-paygo
- Cartesia: https://www.cartesia.ai/pricing

*Gerado automaticamente em 09/09/2026 — revisar preços nos links oficiais antes de decidir.*
