# Ururau v105 — Fonte persistente, texto primeiro e Bing News opcional

## Correção principal

A fila de pautas agora não depende mais de clique manual para tentar carregar o texto completo da fonte. Toda pauta que entra na fila é automaticamente colocada em uma fila de hidratação textual em segundo plano.

Ao clicar em uma pauta, a aba **Fonte** é selecionada automaticamente e aquela pauta ganha prioridade na fila de hidratação.

## Regras novas

- Texto da fonte tem prioridade sobre imagem.
- Imagem só aparece como etapa secundária; o carregamento da aba Fonte não fica esperando foto.
- Fonte com menos de `URURAU_V105_MIN_CHARS_FONTE_OK` caracteres úteis não é considerada válida.
- O fallback antigo não retorna mais `sucesso=True` com 0, 90, 127, 181, 500 ou 600 caracteres.
- O sistema evita múltiplas buscas simultâneas para a mesma pauta.
- Domínios que retornam HTTP 429 entram em cooldown por `URURAU_V105_COOLDOWN_429_SEG`.
- Redigir é bloqueado se a fonte textual não estiver suficiente.

## Bing News Search API

O ZIP `bing-docs-main.zip` ajuda como fonte de especificação para descoberta legal/paga de notícias. Foi criada integração opcional com Bing News Search API v7, desligada por padrão.

Ative com:

```env
URURAU_V105_USAR_BING_NEWS=1
BING_NEWS_API_KEY=sua_chave
```

O coletor usa `sortBy=Date`, `freshness=Day`, `mkt=pt-BR`, `safeSearch=Moderate` e `originalImg=true`.
