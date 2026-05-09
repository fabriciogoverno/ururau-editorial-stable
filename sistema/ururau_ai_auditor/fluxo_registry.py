# -*- coding: utf-8 -*-
from __future__ import annotations

FLUXOS_CRITICOS = {
    "fila": {
        "descricao": "Fila de pautas, selecao, ordem cronologica e F5",
        "arquivos": ["sistema/ururau/ui/painel.py", "sistema/ururau/ui/queue_v45.py"],
    },
    "fonte": {
        "descricao": "Extracao textual e integridade fonte/pauta",
        "arquivos": [
            "sistema/ururau/coleta/fonte_extractor_v104.py",
            "sistema/ururau/coleta/fonte_extractor_v86.py",
            "sistema/ururau/editorial/integridade_fonte_v47_26.py",
            "sistema/ururau/editorial/integridade_redacao_v47_25.py",
        ],
    },
    "imagem": {
        "descricao": "Busca, fallback e processamento de imagem",
        "arquivos": ["sistema/ururau/imaging/busca.py", "sistema/ururau/imaging/processamento.py"],
    },
    "redacao": {
        "descricao": "Geracao de materia, IA, fallback e copydesk",
        "arquivos": [
            "sistema/ururau/editorial/redacao.py",
            "sistema/ururau/editorial/engine.py",
            "sistema/ururau/editorial/copydesk.py",
        ],
    },
    "preview": {
        "descricao": "Preview, edicao manual e bloqueio de materia contaminada",
        "arquivos": ["sistema/ururau/ui/painel.py", "sistema/ururau/ui/revisao.py"],
    },
    "cms": {
        "descricao": "Envio ao CMS, rascunho, publicacao e imagem obrigatoria",
        "arquivos": ["sistema/ururau/publisher/cms_playwright_v81.py", "sistema/ururau/publisher/form_filler.py"],
    },
    "monitor": {
        "descricao": "Monitor 24h, ciclo continuo, rascunho/direto e parar/reiniciar",
        "arquivos": ["sistema/ururau/publisher/monitor.py", "sistema/ururau_monitor.py"],
    },
}


def listar_fluxos() -> dict:
    return FLUXOS_CRITICOS
