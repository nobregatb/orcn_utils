import unittest

from core.analyzer import (
    AnalisadorRequerimentos,
    _validar_campos_certificado,
    _validar_campos_cadastrais,
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

    def test_data_nao_encontrada_gera_nova_exigencia(self):
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
            r'\item Informar "Data de Emissão do CCT" conforme CCT.',
            secao,
        )
        self.assertIn(
            r"\item O Número do Certificado (CCT) informado no Certifica "
            "não corresponde ao número que consta no CCT anexo ao "
            "requerimento. Favor verificar e realizar os ajustes devidos.",
            secao,
        )

    def test_duas_datas_nao_encontradas_geram_exigencia_unica(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={},
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            campos_certificado_nao_encontrados=[
                "Data de Emissão do CCT",
                "Data de Validade do Certificado",
            ],
        )

        self.assertIn(
            r'\item Informar "Data de Emissão do CCT" e '
            r'"Data de Validade do Certificado" conforme CCT.',
            secao,
        )
        self.assertEqual(secao.count(r"\item Informar "), 1)

    def test_identifica_blocos_com_campos_informados_ausentes_do_cct(self):
        dados_requerimento = {
            "fabricante": {
                "Razão Social": "Fabricante Alfa",
                "UNIDADES FABRIS": ["Unidade Sul", "Unidade Norte"],
                "CNPJ": "12.345.678/0001-90",
            },
            "solicitante": {
                "CPF/CPNJ Solicitante": "123.456.789-00",
                "Nome/Razão Social": "Solicitante Alfa",
            },
            "lab": {"Nome": "Laboratório Alfa"},
        }

        campos_nao_encontrados = _validar_campos_cadastrais(
            dados_requerimento,
            "Fabricante Alfa Unidade Sul 12.345.678/0001-90 "
            "123.456.789-00 Solicitante Alfa Laboratório Alfa",
        )

        self.assertEqual(
            campos_nao_encontrados,
            {"fabricante": ["UNIDADES FABRIS"]},
        )

    def test_valida_cnpj_do_fabricante_sem_validar_razao_social_ou_lab(self):
        dados_requerimento = {
            "fabricante": {
                "Razão Social": "Razão Social ausente do CCT",
                "UNIDADES FABRIS": "",
                "CNPJ": "12.345.678/0001-90",
            },
            "lab": {"Nome": "Laboratório ausente do CCT"},
        }

        campos_nao_encontrados = _validar_campos_cadastrais(
            dados_requerimento,
            "",
        )

        self.assertEqual(
            campos_nao_encontrados,
            {"fabricante": ["CNPJ"]},
        )

    def test_ignora_campos_vazios_e_compara_valores_literalmente(self):
        dados_requerimento = {
            "fabricante": {
                "Razão Social": "Fabricante Alfa",
                "UNIDADES FABRIS": "",
                "CNPJ": None,
            },
            "solicitante": {
                "CPF/CPNJ Solicitante": "ABC-123",
                "Nome/Razão Social": "",
            },
            "lab": {"Nome": "Laboratório Alfa"},
        }

        campos_nao_encontrados = _validar_campos_cadastrais(
            dados_requerimento,
            "fabricante alfa abc-123 Laboratório Alfa",
        )

        self.assertEqual(
            campos_nao_encontrados,
            {
                "solicitante": ["CPF/CPNJ Solicitante"],
            },
        )

    def test_monta_bullets_cadastrais_para_os_blocos_ausentes(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={},
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
            campos_cadastrais_nao_encontrados={
                "fabricante": ["UNIDADES FABRIS"],
                "solicitante": ["CPF/CPNJ Solicitante"],
            },
        )

        self.assertIn(
            r'\item "UNIDADES FABRIS" do Fabricante '
            "informado(s) no Certifica não consta(m) no CCT - favor verificar/corrigir, "
            "nos termos do item 6.6.8.1. do Ato nº 4083, de 31 de julho de 2020.",
            secao,
        )
        self.assertIn(
            r'\item "CPF/CPNJ Solicitante" do Solicitante '
            "informado(s) no Certifica não consta(m) no CCT - favor verificar/corrigir, "
            "nos termos do item 6.6.8.1. do Ato nº 4083, de 31 de julho de 2020.",
            secao,
        )
        self.assertNotIn('"Razão Social"', secao)
        self.assertNotIn('"CNPJ"', secao)
        self.assertNotIn('"Nome/Razão Social"', secao)
        self.assertNotIn('"Nome" do Laboratório', secao)


if __name__ == "__main__":
    unittest.main()
