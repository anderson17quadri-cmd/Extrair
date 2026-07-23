# CLAUDE.md

Guia para o Claude Code trabalhar neste repositório (Extrair / Radar Viral).

## Sobre o projeto

App Flask que coleta vídeos virais do TikTok/Instagram, calcula score de viralidade e exibe num dashboard (`app.py`, `coletor.py`, `score.py`, `db.py`, `templates/`, `static/`).

## Skills instaladas

- **frontend-design** (`.claude/skills/frontend-design/`): skill oficial da Anthropic para design visual distintivo (paleta, tipografia, layout, animação). Use ao criar ou redesenhar telas do dashboard (`templates/`, `static/`) para fugir de "cara de template" — escolhas de cor/tipo intencionais em vez dos defaults genéricos de IA.

## Ferramentas recomendadas para frontend (a configurar conforme necessidade)

Referência de um setup mais completo de design para Claude Code, para instalar quando fizer sentido:

1. **shadcn MCP** — biblioteca de componentes prontos (botão, menu, login) que o Claude usa como base e customiza.
2. **Magic MCP (21st.dev)** — add-ons, animações e um estilo de site coerente ponta a ponta (requer API key do 21st.dev).
3. **frontend-design** (Anthropic) — já instalada neste repo, ver acima.
4. **Web Design Guidelines (Vercel)** — checklist de regras profissionais de design para revisar a UI antes de publicar.
5. **Chrome DevTools MCP** — permite ao Claude abrir o site num navegador real, inspecionar e corrigir problemas visuais sozinho.

Ao usar essas ferramentas, sempre teste o fluxo no navegador antes de considerar a tarefa concluída (não basta o código compilar).
