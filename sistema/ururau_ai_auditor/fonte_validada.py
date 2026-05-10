def validar_resultado_fonte(resultado):

    if not isinstance(resultado, dict):
        return {
            "ok": False,
            "erro": "resultado_invalido"
        }

    status = resultado.get("status")
    texto = resultado.get("texto") or ""
    url = resultado.get("url")

    if status in [403, 429]:
        return {
            "ok": False,
            "erro": f"http_{status}",
            "url": url
        }

    if len(texto.strip()) < 120:
        return {
            "ok": False,
            "erro": "texto_curto",
            "url": url
        }

    return {
        "ok": True,
        "url": url,
        "tamanho_texto": len(texto)
    }
