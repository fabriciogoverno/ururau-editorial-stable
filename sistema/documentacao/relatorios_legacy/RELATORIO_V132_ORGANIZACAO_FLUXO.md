# URURAU v132 — Organização de Config, Autoadequação e Fluxo Preview/CopyDesk

## Objetivo
Consolidar a área de configurações, simplificar o Diagnóstico de Fonte e tornar o botão Atualizar/F5 útil sem reiniciar o sistema.

## Alterações principais

1. **Config > Fontes / Links**
   - RSS, XML/Sitemap, Especiais e Regionais ficam dentro de uma única aba, separados por subtítulos internos.
   - Termos, Parâmetros, Credenciais, Diagnóstico de Coleta e Diagnóstico de Fonte ficam em abas próprias.

2. **Diagnóstico de Fonte simplificado**
   - Removidos os botões separados de diagnóstico rápido, diagnóstico completo e aplicar.
   - Criado fluxo único: **Diagnosticar, aplicar e testar**.
   - O fluxo executa diagnóstico completo, gera perfil operacional, aplica com backup, testa e informa se a fonte será usada na próxima coleta.
   - Exportar TXT foi mantido.

3. **Atualizar F5 útil**
   - F5 agora recarrega settings, limpa caches leves da UI, recarrega configurações visíveis e recarrega a fila.
   - Serve para aplicar novas fontes/termos sem reiniciar.

4. **Preview → CopyDesk**
   - O Preview ganhou botão **CopyDesk IA**.
   - Ele salva o texto atual do preview, injeta a fonte original disponível e abre o CopyDesk usando os dois elementos: texto gerado e texto-fonte.

5. **CopyDesk sem quebra artificial por parágrafo**
   - O corpo da matéria passa a ser revisado como um campo único, preservando parágrafos dentro do texto.
   - Evita revisar parágrafo por parágrafo como itens separados.

6. **Botão Imagem**
   - Removido da toolbar principal.
   - A busca externa automática por imagem fica desativada para evitar uso indevido de imagem com direitos autorais sem validação.

7. **Console externo**
   - O `INICIAR.bat` da raiz passa a iniciar o sistema sem manter uma janela CMD/PowerShell aberta.
   - O console interno do painel continua disponível pelo botão **Console**, mas não abre por padrão.

8. **Raiz do pacote limpa**
   - Na raiz ficam apenas os arquivos BAT de execução e a pasta `sistema`.
   - Ícones e documentos foram movidos para pastas internas.

## Observação técnica
A reorganização foi feita por patch de UI para preservar os motores de coleta, banco, publicação, Monitor, Campos 24 Horas, NF Notícias, AutoFontes v131 e adaptadores existentes.
