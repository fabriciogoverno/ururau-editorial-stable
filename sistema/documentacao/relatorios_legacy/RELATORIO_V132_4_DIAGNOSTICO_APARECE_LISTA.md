# v132.4 - Diagnóstico aplica e aparece em Fontes/Links

Correções:

1. O botão **Diagnosticar, aplicar e testar** mantém o fluxo completo: diagnóstico completo, geração de perfil operacional, teste, aplicação com backup e relatório visual.
2. Depois de aplicar com sucesso, a aba **Fontes / Links** é recarregada imediatamente, incluindo RSS, XML/Sitemap, Especiais e Regionais.
3. O perfil salvo em `perfis_fontes_v131.json` também é sincronizado na aba visual correta.
4. `tribunanf.com.br` passou a ser reconhecido como fonte regional, entrando em **Fontes / Links > Regionais** quando aplicado.
5. A versão já inclui **Tribuna NF** em Regionais por padrão.
6. URLs coladas duplicadas, como `https://site/https://site/`, são normalizadas antes do diagnóstico.

O objetivo é eliminar a situação em que a ferramenta dizia que aplicou, mas o link não aparecia visualmente nas listas de configuração.
