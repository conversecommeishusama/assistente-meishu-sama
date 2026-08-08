import sys, json, glob, os
sys.path.insert(0, 'scripts')
from fix_periodicos_work_headers import parse_article, split_file

MANUAL_DIR = 'reports/livros_trabalho/segmentacao_manual'
JP_DIR = 'reports/livros_trabalho/jp'
PT_DIR = 'reports/livros_trabalho/pt'

def get_body(path):
    text = open(path, encoding='utf-8').read()
    _, blocks = split_file(text)
    if len(blocks) != 1:
        return None, len(blocks)
    art = parse_article(blocks[0])
    return art.content, 1

specs = sorted(glob.glob(f'{MANUAL_DIR}/*.txt.json'))
specs = [s for s in specs if 'AUDIT_TRAIL' not in s]

report = {}
for spec_path in specs:
    fn = os.path.basename(spec_path)[:-len('.json')]
    jp_path = os.path.join(JP_DIR, fn)
    pt_path = os.path.join(PT_DIR, fn)
    if not (os.path.isfile(jp_path) and os.path.isfile(pt_path)):
        report[fn] = {'error': 'missing work files'}
        continue
    jp_body, jp_n = get_body(jp_path)
    pt_body, pt_n = get_body(pt_path)
    if jp_n != 1 or pt_n != 1:
        report[fn] = {'error': f'blocos!=1 (jp={jp_n} pt={pt_n})'}
        continue
    spec = json.load(open(spec_path, encoding='utf-8'))
    issues = []
    for i, a in enumerate(spec.get('articles', [])):
        jpa = a.get('jp_anchor','').strip()
        pta = a.get('pt_anchor','').strip()
        jp_count = jp_body.count(jpa) if jpa else 0
        pt_count = pt_body.count(pta) if pta else 0
        if not jpa:
            issues.append((i, 'jp_anchor vazio'))
        elif jp_count == 0:
            issues.append((i, f'JP não encontrado: {jpa[:60]!r}'))
        elif jp_count > 1:
            issues.append((i, f'JP AMBIGUO ({jp_count}x): {jpa[:60]!r}'))
        if not pta:
            issues.append((i, 'pt_anchor vazio'))
        elif pt_count == 0:
            issues.append((i, f'PT não encontrado: {pta[:60]!r}'))
        elif pt_count > 1:
            issues.append((i, f'PT AMBIGUO ({pt_count}x): {pta[:60]!r}'))
    if issues:
        report[fn] = {'issues': issues, 'n_articles': len(spec.get('articles',[]))}

clean = [f for f in [os.path.basename(s)[:-len('.json')] for s in specs] if f not in report]
print('LIMPOS (sem nenhum issue):', len(clean))
print('COM ISSUES:', len(report))
json.dump(report, open('/tmp/claude-0/-var-www-goshinsho/58833262-ff56-4872-bb6a-0356e867779d/scratchpad/anchor_issues.json','w'), ensure_ascii=False, indent=2)
for fn, info in report.items():
    print('===', fn, '===')
    if 'error' in info:
        print('  ERRO:', info['error'])
    else:
        for i, msg in info['issues']:
            print(f'  [{i}]', msg)
