-- Migração do Fórum Goshinsho (piloto)
-- Cria as tabelas de fóruns de discussão + mensagens com moderação.
-- Padrão seguido: uuid id com default gen_random_uuid(), timestamptz,
-- chaves estrangeiras para usuarios (auth.users.id).

-- Tópicos de discussão do fórum
CREATE TABLE IF NOT EXISTS public.forum_topicos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo text NOT NULL,
    descricao text,
    autor_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    autor_nome text,                     -- apelido/nome de exibição (privacidade: e-mail nunca exposto)
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'aberto'  -- aberto | fechado | arquivado
);

-- 2026-08-24: coluna autor_nome adicionada retroativamente (migração)
ALTER TABLE public.forum_topicos ADD COLUMN IF NOT EXISTS autor_nome text;

CREATE INDEX IF NOT EXISTS idx_forum_topicos_created_at ON public.forum_topicos (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_topicos_status ON public.forum_topicos (status);

-- Mensagens dentro de um tópico (inclui as respostas da IA, papel='assistente')
CREATE TABLE IF NOT EXISTS public.forum_mensagens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topico_id uuid NOT NULL REFERENCES public.forum_topicos(id) ON DELETE CASCADE,
    autor_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,  -- NULL = postagem da IA
    autor_nome text,                     -- apelido/nome de exibição
    papel text NOT NULL DEFAULT 'usuario',  -- usuario | assistente (IA)
    conteudo text NOT NULL,
    -- Moderação: status da moderação automática
    status text NOT NULL DEFAULT 'pendente',  -- aprovada | em_revisao | reprovada
    motivo text,                              -- motivo quando reprovada/em_revisao
    moderado_em timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 2026-08-24: coluna autor_nome adicionada retroativamente (migração)
ALTER TABLE public.forum_mensagens ADD COLUMN IF NOT EXISTS autor_nome text;

CREATE INDEX IF NOT EXISTS idx_forum_mensagens_topico ON public.forum_mensagens (topico_id, created_at);
CREATE INDEX IF NOT EXISTS idx_forum_mensagens_status ON public.forum_mensagens (status);
CREATE INDEX IF NOT EXISTS idx_forum_mensagens_autor ON public.forum_mensagens (autor_id);
