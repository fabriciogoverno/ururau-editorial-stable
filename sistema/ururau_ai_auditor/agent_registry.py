# -*- coding: utf-8 -*-
from __future__ import annotations

AGENTES = {
    "redacao": {
        "descricao": "Agente de Redacao: integridade pauta/fonte/materia, IA, fallback e copydesk.",
        "arquivos": [
            "sistema/ururau/editorial/redacao.py",
            "sistema/ururau/editorial/engine.py",
            "sistema/ururau/editorial/copydesk.py",
            "sistema/ururau/editorial/integridade_fonte_v47_26.py",
            "sistema/ururau/editorial/integridade_redacao_v47_25.py",
        ],
        "padroes": ["redacao", "preview", "materia", "fonte", "contaminada", "fallback", "openai", "score", "bloqueante"],
    },
    "fonte": {
        "descricao": "Agente de Fonte: RSS, leitura, extracao e diagnostico de fonte.",
        "arquivos": [
            "sistema/ururau/coleta/fonte_extractor_v104.py",
            "sistema/ururau/coleta/fonte_extractor_v86.py",
            "sistema/ururau/coleta/leitura_fonte.py",
            "sistema/ururau/coleta/rss.py",
        ],
        "padroes": ["fonte", "extracao", "rss", "v104", "v86", "texto", "fallback html", "403", "429"],
    },
    "imagem": {
        "descricao": "Agente de Imagem: busca, fallback, download, crop e validacao.",
        "arquivos": ["sistema/ururau/imaging/busca.py", "sistema/ururau/imaging/processamento.py"],
        "padroes": ["imagem", "foto", "og_image", "json_ld_image", "cooldown", "429", "sem imagem"],
    },
    "cms": {
        "descricao": "Agente de CMS: Playwright, formularios, rascunho, publicar e preflight.",
        "arquivos": ["sistema/ururau/publisher/cms_playwright_v81.py", "sistema/ururau/publisher/form_filler.py"],
        "padroes": ["cms", "playwright", "publicar", "rascunho", "form", "future", "SyntaxError"],
    },
    "monitor": {
        "descricao": "Agente de Monitor: ciclo 24h, parar, reiniciar, duplicidade e coletores lentos.",
        "arquivos": ["sistema/ururau/publisher/monitor.py", "sistema/ururau_monitor.py"],
        "padroes": ["monitor", "ciclo", "parar", "thread", "google news", "kimi", "source hunter", "429"],
    },
    "ui": {
        "descricao": "Agente de UI: painel, fila, F5, selecao, preview e estado visual.",
        "arquivos": ["sistema/ururau/ui/painel.py", "sistema/ururau/ui/queue_v45.py", "sistema/ururau/ui/revisao.py"],
        "padroes": ["painel", "fila", "preview", "f5", "selecion", "interface", "botao"],
    },
    "regressao": {
        "descricao": "Agente de Regressao: compilacao, testes de contrato e risco de patch.",
        "arquivos": ["sistema/ururau_ai_auditor/regression_tests.py", "sistema/tests_contrato"],
        "padroes": ["SyntaxError", "NameError", "AttributeError", "ImportError", "FAIL", "ERROR"],
    },
}


def listar_agentes() -> dict:
    return AGENTES
