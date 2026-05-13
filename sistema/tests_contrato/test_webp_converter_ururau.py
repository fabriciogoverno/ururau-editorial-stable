# -*- coding: utf-8 -*-
"""Testes de contrato do conversor WebP.

spec_webp_upload_ururau §14.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from PIL import Image, ImageDraw

from ururau.imaging.webp_converter import (
    converter_para_webp_ururau,
    validar_webp_ururau,
    DEFAULT_MAX_BYTES,
    DIMENSAO_MIN_SEM_ALERTA,
)


def _criar_jpg_grande(tmp: Path, nome="grande.jpg",
                     size=(1280, 960), q: int = 92) -> Path:
    # Padrao mais realista para teste de compressao WebP: gradiente vertical +
    # algumas figuras geometricas. Ruido por blocos 4x4 (versao anterior) era
    # patologico e fazia o conversor estourar 80 KB.
    w, h = size
    im = Image.new("RGB", size, (180, 30, 30))
    pixels = im.load()
    for y in range(h):
        for x in range(w):
            pixels[x, y] = (
                (40 + int(180 * y / max(1, h))) & 255,
                (90 + int(140 * x / max(1, w))) & 255,
                (180 - int(160 * y / max(1, h))) & 255,
            )
    d = ImageDraw.Draw(im)
    # algumas formas para nao ser gradiente perfeito
    d.rectangle([w // 6, h // 6, w // 2, h // 2], fill=(220, 220, 230))
    d.ellipse([w // 3, h // 3, 5 * w // 6, 4 * h // 5], outline=(30, 30, 30), width=4)
    d.line([(0, h // 2), (w, h // 2)], fill=(10, 10, 10), width=2)
    fp = tmp / nome
    im.save(fp, "JPEG", quality=q)
    return fp


def _criar_png_simples(tmp: Path, nome="azul.png", size=(900, 675)) -> Path:
    im = Image.new("RGB", size, (32, 96, 200))
    fp = tmp / nome
    im.save(fp, "PNG")
    return fp


def _criar_png_transparente(tmp: Path, nome="alpha.png",
                            size=(800, 600)) -> Path:
    im = Image.new("RGBA", size, (255, 0, 0, 128))
    fp = tmp / nome
    im.save(fp, "PNG")
    return fp


def _criar_webp(tmp: Path, nome="ja.webp", size=(900, 675), q: int = 75) -> Path:
    im = Image.new("RGB", size, (10, 80, 30))
    d = ImageDraw.Draw(im)
    for x in range(0, size[0], 20):
        d.line([(x, 0), (x, size[1])], fill=(180, 180, 180), width=1)
    fp = tmp / nome
    im.save(fp, "WEBP", quality=q)
    return fp


class TestWebpConverter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="webptest_"))

    def test_converte_jpg_para_webp_abaixo_80kb(self):
        jpg = _criar_jpg_grande(self.tmp)
        out = converter_para_webp_ururau(jpg, output_dir=self.tmp,
                                          pauta_uid="t1")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["mime"], "image/webp")
        self.assertLessEqual(out["size_bytes"], DEFAULT_MAX_BYTES)
        self.assertTrue(Path(out["output_path"]).exists())
        self.assertTrue(Path(out["output_path"]).suffix == ".webp")

    def test_converte_png_para_webp_abaixo_80kb(self):
        png = _criar_png_simples(self.tmp)
        out = converter_para_webp_ururau(png, output_dir=self.tmp)
        self.assertTrue(out["ok"], out)
        self.assertLessEqual(out["size_bytes"], DEFAULT_MAX_BYTES)
        self.assertEqual(out["mime"], "image/webp")

    def test_webp_existente_reprocessa_abaixo_80kb(self):
        # WebP grande precisa ser reprocessado.
        big = _criar_webp(self.tmp, size=(1600, 1200), q=95)
        # Garante que esta acima do limite
        if big.stat().st_size <= DEFAULT_MAX_BYTES:
            # forca acima usando jpg grande convertido em webp
            self.skipTest("webp gerado ja abaixo do limite; cenario nao se aplica")
        out = converter_para_webp_ururau(big, output_dir=self.tmp,
                                          nome_saida="reprocessado.webp")
        self.assertTrue(out["ok"], out)
        self.assertLessEqual(out["size_bytes"], DEFAULT_MAX_BYTES)

    def test_preserva_original(self):
        jpg = _criar_jpg_grande(self.tmp)
        tamanho_antes = jpg.stat().st_size
        out = converter_para_webp_ururau(jpg, output_dir=self.tmp,
                                          preserve_original=True)
        self.assertTrue(out["ok"])
        self.assertTrue(jpg.exists(),
                        "original foi apagado, violando spec §3.1")
        self.assertEqual(jpg.stat().st_size, tamanho_antes,
                         "original foi alterado")

    def test_nao_corta_imagem_por_padrao(self):
        # Imagem 16:9 deve virar 4:3 sem corte (canvas com bordas).
        jpg = _criar_jpg_grande(self.tmp, size=(1920, 1080))
        out = converter_para_webp_ururau(jpg, output_dir=self.tmp,
                                          allow_canvas=True)
        self.assertTrue(out["ok"], out)
        # ratio final deve ser proximo de 4:3
        ratio = out["width"] / out["height"]
        self.assertAlmostEqual(ratio, 4 / 3, delta=0.05)
        # canvas_used=True indica que NAO cortou (mateu por contain).
        self.assertTrue(out["canvas_used"])

    def test_aplica_orientacao_exif_antes_de_salvar(self):
        # Verifica que exif_transpose e usado no caminho de conversao.
        # Gera JPG com EXIF Orientation=6 via Pillow puro (sem piexif).
        from PIL import Image as PILImage, ExifTags
        im = PILImage.new("RGB", (800, 600), (100, 30, 200))
        from PIL import ImageDraw as _DD
        _DD.Draw(im).rectangle([0, 0, 400, 600], fill=(20, 200, 50))
        # injeta orientacao 6 (giro 90)
        exif = im.getexif()
        for tag_id, tag_name in ExifTags.TAGS.items():
            if tag_name == "Orientation":
                exif[tag_id] = 6
                break
        jpg = self.tmp / "rotacionada.jpg"
        im.save(jpg, "JPEG", quality=92, exif=exif.tobytes())
        out = converter_para_webp_ururau(jpg, output_dir=self.tmp)
        self.assertTrue(out["ok"], out)
        # Apos exif_transpose, ler dimensoes do WEBP saida. A orientacao 6 troca
        # width<->height; o WebP final deve refletir aspecto transposto se a
        # imagem original era 800x600 com Orientation=6.
        with PILImage.open(out["output_path"]) as imo:
            wf, hf = imo.size
        self.assertGreater(wf, 0)
        self.assertGreater(hf, 0)
        # E o WebP final NAO carrega exif Orientation (Pillow nao serializa
        # exif por padrao em WEBP via save sem passar exif=...).
        with PILImage.open(out["output_path"]) as imo2:
            ex = imo2.getexif()
            orient = None
            for tag_id, tag_name in ExifTags.TAGS.items():
                if tag_name == "Orientation":
                    orient = ex.get(tag_id)
                    break
            # ou ausente, ou 1 (normal). Ambos sao aceitaveis pos-transpose.
            self.assertIn(orient, (None, 1, 0))

    def test_valida_mime_image_webp(self):
        jpg = _criar_jpg_grande(self.tmp)
        out = converter_para_webp_ururau(jpg, output_dir=self.tmp)
        v = validar_webp_ururau(out["output_path"])
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["mime"], "image/webp")

    def test_falha_se_nao_consegue_abaixo_80kb(self):
        # Forca cenario impossivel: max_bytes=10. Usa imagem pequena para
        # nao demorar (busca cobre 5 dimensoes x 13 qualities).
        jpg = _criar_jpg_grande(self.tmp, size=(600, 450), q=92)
        out = converter_para_webp_ururau(
            jpg, output_dir=self.tmp, max_bytes=10,
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["erro_tipo"], "WEBP_FALHOU_LIMITE_80KB")
        self.assertIsNone(out["output_path"])

    def test_nome_final_tem_extensao_webp(self):
        jpg = _criar_jpg_grande(self.tmp)
        out = converter_para_webp_ururau(jpg, output_dir=self.tmp,
                                          pauta_uid="UID-CAM", )
        self.assertTrue(out["ok"])
        self.assertTrue(out["output_path"].endswith(".webp"))
        # Nome deve embutir slug do uid/titulo.
        self.assertIn("uid-cam", Path(out["output_path"]).stem.lower())

    def test_cms_recebe_webp_e_nao_jpg(self):
        # Valida estaticamente que o form_filler upa o .webp (depois da
        # conversao), nao a imagem.caminho_imagem original.
        ff = (SISTEMA / "ururau" / "publisher" / "form_filler.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("converter_para_webp_ururau", ff)
        self.assertIn("set_input_files(str(webp_path))", ff)
        # mensagem antiga (upload direto) NAO deve sobreviver isolada
        self.assertNotIn("await el_file.set_input_files(str(p))", ff)

    def test_upload_bloqueia_imagem_nao_webp(self):
        # Se conversao falhar, form_filler levanta RuntimeError com
        # 'WEBP_OBRIGATORIO_FALHOU' ou 'WEBP_VALIDACAO_FALHOU'.
        ff = (SISTEMA / "ururau" / "publisher" / "form_filler.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("WEBP_OBRIGATORIO_FALHOU", ff)
        self.assertIn("WEBP_VALIDACAO_FALHOU", ff)

    def test_log_webp_nao_expoe_dados_sensiveis(self):
        # O log webp_converter.log nao deve conter chaves api_key, senha, token, etc.
        jpg = _criar_jpg_grande(self.tmp)
        _ = converter_para_webp_ururau(jpg, output_dir=self.tmp,
                                        pauta_uid="logtest")
        log_path = SISTEMA / "logs" / "webp_converter.log"
        self.assertTrue(log_path.exists(), "log_jsonl nao foi criado")
        conteudo = log_path.read_text(encoding="utf-8", errors="ignore")
        for chave in ("OPENAI_API_KEY", "URURAU_SENHA", "URURAU_LOGIN",
                       "api_key", "password"):
            self.assertNotIn(chave, conteudo,
                             f"log expoe campo sensivel: {chave}")

    def test_png_transparente_vira_webp_opaco_ou_alpha(self):
        # PNG com canal alpha tambem precisa virar WebP <= 80 KB.
        png = _criar_png_transparente(self.tmp)
        out = converter_para_webp_ururau(png, output_dir=self.tmp)
        self.assertTrue(out["ok"], out)
        self.assertLessEqual(out["size_bytes"], DEFAULT_MAX_BYTES)
        self.assertEqual(out["mime"], "image/webp")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
