import sys,re,json
sys.path.insert(0,'/var/www/goshinsho'); sys.path.insert(0,'/var/www/goshinsho/scripts')
from pathlib import Path
from apply_manual_livros_segmentacao import split_by_anchors
from build_clean_large_indexes import clean_body
from openai import OpenAI
o='19501120-世界救世教早わかり.txt'
spec=json.loads(Path(f'reports/livros_trabalho/segmentacao_manual/{o}.json').read_text())
pt=split_by_anchors(clean_body(Path(f'livros_publicacao_pt_revisado/{o}').read_text()),
                    [a['pt_anchor'] for a in spec['articles']],label=o)[4]
jp=split_by_anchors(clean_body(Path(f'reports/livros_trabalho/jp/{o}').read_text()),
                    [a['jp_anchor'] for a in spec['articles']],label=o)[4]
k=[l.split('=',1)[1].strip().strip('"').strip("'") for l in Path('.env').read_text().splitlines()
   if l.startswith('DEEPSEEK_API_KEY')][0]
cli=OpenAI(api_key=k, base_url='https://api.deepseek.com')
S="""Compare a tradução portuguesa com o original japonês e liste o que estiver errado.
Uma linha por erro:
ERRO | <trecho português exato> | <trecho corrigido> | <o que está errado>
Se estiver tudo certo: NADA"""
print(f'PT {len(pt)} car. | JP {len(jp)} car.', flush=True)
for teto in (65536, 32768):
    try:
        r=cli.chat.completions.create(model='deepseek-v4-flash',max_tokens=teto,
          messages=[{'role':'system','content':S},
                    {'role':'user','content':f"=== JAPONÊS ===\n{jp}\n\n=== PORTUGUÊS ===\n{pt}"}])
        u=r.usage; d=getattr(u,'completion_tokens_details',None)
        c=r.choices[0].message.content or ''
        print(f'  teto {teto}: saída {u.completion_tokens} (raciocínio {getattr(d,"reasoning_tokens",0)}) '
              f'| finish={r.choices[0].finish_reason} | resposta {len(c)} car.', flush=True)
        for ln in c.splitlines()[:6]:
            if ln.strip(): print(f'     {ln[:150]}', flush=True)
        if c.strip(): break
    except Exception as e:
        print(f'  teto {teto}: ERRO {repr(e)[:150]}', flush=True)
