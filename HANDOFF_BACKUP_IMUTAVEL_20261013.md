# Backups IMUTÁVEIS — o que falta (passo do proprietário)

Preparado em 2026-10-13. O que já está feito eu implementei; o que falta
exige **criar uma chave no console do Backblaze B2** (você, ~5 min).

---

## ✅ O que já está pronto (feito por mim)

| Item | Estado |
|---|---|
| Dump do banco off-site | ✅ GDrive **e** Backblaze B2 (2 provedores) |
| Logs de segurança off-site | ✅ diário (04:40) para o GDrive |
| Corpus + índices off-site | ✅ já existia (diário 03:50) |
| Retenção | ✅ 120 dias (dumps) / 90 dias (logs) |

**Por que 2 provedores?** Se um provedor (ou a credencial dele) for
comprometido, a **outra cópia** continua intacta.

---

## ⚠️ O problema que resta: a credencial do backup APAGA

Testei: a credencial do rclone no servidor **consegue excluir** os arquivos
remotos. Ou seja, **um invasor com acesso ao servidor pode apagar os backups**
(inclusive os off-site). Isso é o clássico "ransomware que destrói o backup".

> Também confirmei: o `rclone` **não** cria bucket com *Object Lock* (imutável),
> e o B2 só permite Object Lock em **bucket novo**.

---

## 🔒 Solução 1 (recomendada, grátis): chave B2 "write-only"

Criar uma **application key** do B2 que **só escreve** (não apaga). Assim, mesmo
com o servidor comprometido, os backups **não podem ser deletados** — só
adicionados. É o mais próximo de "imutável" sem custo.

### Passo a passo (console Backblaze B2)

1. Entre em `secure.backblaze.com` → **Application Keys** → **Add a New Application Key**.
2. Preencha:
   - **Name:** `goshinsho-backup-writeonly`
   - **Allow access to Bucket(s):** `goshinsho-backup-2026`
   - **Type of Access:** **Read and Write** ... **NÃO** marque *Allow List All Bucket Names*
   - **Permissões (desmarque as de escrita/leitura ampla):**
     - ✅ `Write Files`
     - ✅ `Read Files` (opcional, para conferência)
     - ❌ **`Delete Files`**  ← **NÃO marcar** (é isso que dá a imutabilidade)
     - ❌ `List Files` (deixe desmarcado se possível)
3. Copie **keyID** e **applicationKey**.
4. Me envie (ou coloque você mesmo) para um **novo remote rclone** `b2lock:`
   (eu te ajudo a configurar sem expor a chave no chat).
5. Eu troco os scripts de backup para usar `b2lock:` e **prune manualmente** pela
   retenção (ou com uma chave separada de "manutenção", usada raríssimas vezes).

> ⚠️ **Limitação honesta:** a chave do servidor **ainda** poderia "sobrescrever"
> um arquivo (se a permissão permitir). A proteção total contra sobrescrita só vem
> com **Object Lock** (Solução 2).

---

## 🛡️ Solução 2 (imutável de verdade): bucket novo com Object Lock

### No console B2
1. **Buckets** → **Create a Bucket**
   - **Name:** `goshinsho-backup-locked`
   - **Files in Bucket are:** **Private**
   - **Object Lock:** ✅ **Enable**
   - **Default Retention:** **Compliance** (ou **Governance**), por ex. **30 dias**
2. Copie o keyID/appKey de uma chave com acesso a esse bucket.
3. Me avise → eu aponto os backups para lá.

Com **Compliance Mode**, nem você nem a Backblaze conseguem apagar antes do prazo
— é o padrão "WORM". (Governance permite a você, admin, remover com a chave certa.)

---

## 🔁 Alternativa via Google Drive (se preferir não usar B2)

O Google Drive mantém **histórico de versões** (~30 dias) e **lixeira** (~30 dias).
Não é imutável, mas dá alguma recuperação. Para reforçar:
- Colocar a pasta `goshinsho-backup-2026` num **Drive Compartilhado** e dar à
  conta do backup o papel de **Contribuidor** (não Gerente) — reduz a capacidade
  de apagar itens que não são dela.

---

## 📋 Resumo do que preciso de você

- [ ] Criar a **chave B2 write-only** (Solução 1, 5 min) **ou** o **bucket com Object Lock** (Solução 2).
- [ ] Me avisar → eu reconfiguro os scripts e testo.

Até lá, **já temos**: 2 provedores, retenção, e logs off-site — que cobrem a
**maioria** dos cenários (perda do servidor, falha de um provedor). Falta só a
proteção contra o cenário "invasor apaga o backup".
