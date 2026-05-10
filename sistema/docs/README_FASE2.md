# Ururau Neural Engine — Fase 2

## Componentes

| Modulo | Funcao |
|--------|--------|
| `patch_generator.py` | Gera correcoes para SyntaxError (heuristica + LLM local) |
| `sandbox_ml.py` | Valida patch em ambiente isolado antes de aplicar |
| `impact_tracker.py` | Mede metricas 24h antes/depois do patch |
| `rollback_guard.py` | Reverte automaticamente se piorou > 15% |
| `long_term_memory.py` | Memoria semantica de correcoes para reutilizacao |
| `integrador.py` | Orquestra todo o pipeline |

## Fluxo

```
scanner_codigo.py -> detecta SyntaxError
        |
        v
patch_generator.py -> gera diff
        |
        v
sandbox_ml.py -> roda testes contrato
        |
        v
rollback_guard.py -> aplica no real + backup
        |
        v
impact_tracker.py -> mede 24h depois
        |
        v
rollback_guard.py -> reverte se piorou
        |
        v
long_term_memory.py -> armazena resultado
```

## BATs

- `47_REPARO_NEURAL.bat` — Executa ciclo completo de reparo
- `48_FECHAR_PATCHES.bat` — Fecha patches pendentes (rode 1x ao dia)
