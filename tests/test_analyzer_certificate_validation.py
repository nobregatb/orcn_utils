import unittest

from core.analyzer import (
    AnalisadorRequerimentos,
    _validar_campos_certificado,
)


class ValidarCamposCertificadoTest(unittest.TestCase):
    def test_valida_numero_literal_e_datas_em_formatos_diferentes(self):
        dados_requerimento = {
            "certificado": {
                "Número do Certificado": "ABC 123",
                "Data de Emissão do CCT": "11/10/2026",
                "Data de Validade do Certificado": "11/10/2027",
            },
        }

        campos_nao_encontrados = _validar_campos_certificado(
            dados_requerimento,
            "Certificado ABC 123, emitido em 11 de outubro de 2026, "
            "válido até 11/10/2027.",
        )

        self.assertEqual(campos_nao_encontrados, [])

    def test_ignora_espacos_no_numero_mantendo_maiusculas_e_minusculas(self):
        dados_requerimento = {
            "certificado": {
                "Número do Certificado": "ABC 123",
            },
        }

        campos_nao_encontrados = _validar_campos_certificado(
            dados_requerimento,
            "Certificado A B C\t1\n2 3",
        )

        self.assertEqual(campos_nao_encontrados, [])

    def test_numero_continua_sensivel_a_maiusculas_e_minusculas(self):
        dados_requerimento = {
            "certificado": {
                "Número do Certificado": "ABC 123",
            },
        }

        campos_nao_encontrados = _validar_campos_certificado(
            dados_requerimento,
            "Certificado abc 123",
        )

        self.assertEqual(campos_nao_encontrados, ["Número do Certificado"])

    def test_identifica_datas_e_campos_nao_encontrados(self):
        dados_requerimento = {
            "certificado": {
                "Número do Certificado": "CERT-456",
                "Data de Emissão do CCT": "31/02/2026",
                "Data de Validade do Certificado": "11/10/2027",
            },
        }

        campos_nao_encontrados = _validar_campos_certificado(
            dados_requerimento,
            "CERT-456, emitido em 11 de outubro de 2026.",
        )

        self.assertEqual(
            campos_nao_encontrados,
            [
                "Data de Emissão do CCT",
                "Data de Validade do Certificado",
            ],
        )

    def test_campos_nao_encontrados_geram_exigencia_por_campo(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={},
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            campos_certificado_nao_encontrados=[
                "Número do Certificado",
                "Data de Emissão do CCT",
            ],
        )

        self.assertIn(
            r"\item O campo Número do Certificado do JSON do requerimento "
            "não foi encontrado no CCT.",
            secao,
        )
        self.assertIn(
            r"\item O campo Data de Emissão do CCT do JSON do requerimento "
            "não foi encontrado no CCT.",
            secao,
        )


if __name__ == "__main__":
    unittest.main()
