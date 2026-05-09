# Relatório V43 Premium — revisão final de layout leve

## Objetivo
Aplicar uma revisão real no painel V43 Premium com foco em fluidez, menos duplicação visual e menor carga de interface.

## Alterações aplicadas

1. A barra lateral esquerda foi removida do layout V43 Premium.
   - Não há navegação lateral fixa.
   - Não há área ocupando espaço à esquerda da fila.
   - A tela principal prioriza Fila de Pautas e Detalhe da Pauta.

2. Os botões principais ficam na parte superior.
   - Coletar
   - Redigir
   - Copydesk
   - Preview
   - Publicar
   - Descartar
   - Exportar
   - Monitor OFF/ON
   - Console

3. A coluna “Análise e Ações” foi removida.
   - Sem origem da fonte duplicada.
   - Sem ações rápidas duplicadas.
   - Qualidade IA e Risco ficam em uma faixa compacta no topo.

4. A origem da fonte foi movida para a aba Info.
   - Nome da fonte
   - Tipo
   - Confiabilidade
   - Domínio
   - URL original

5. O console abre apenas quando o botão Console é clicado.
   - Ele abre na parte inferior.
   - O tamanho é menor que antes.
   - O modo normal do painel continua leve.

6. RODAR_TUDO.bat fica visível.
   - Serve para instalação, validação e diagnóstico.
   - Não fica oculto.
   - Mantém pause no fim para o usuário ler erros.

7. INICIAR.bat fica oculto.
   - Serve para uso normal sem janela preta.
   - Abre via VBS/pythonw quando disponível.

8. Organização de arquivos.
   - Arquivos BAT ficam na raiz.
   - Ícone ICO também fica na raiz para futuro atalho.
   - Documentação, validadores e reparos seguem em pastas.
   - Configurações legadas essenciais foram preservadas na raiz de sistema para não quebrar carregadores antigos.

## Observação técnica
Alguns arquivos JSON e TXT permanecem diretamente em `sistema/` porque o motor legado ainda lê esses nomes por caminhos fixos, como `fontes_rss.json`, `fontes_especiais_v129.json`, `termos_watchlist_v98.json` e `fontes_xml_sitemap_vfinal.txt`. Movê-los sem reescrever todos os carregadores quebraria coleta, configuração e diagnóstico. Eles foram mantidos por segurança operacional.

## Validação
- `patch_v43_premium.py` compilado sem erro.
- BATs revisados sem caracteres de controle quebrados.
- Pycache removido antes do empacotamento.
- ZIP gerado novamente com o mesmo nome V43 Premium.
