import unittest
from unittest.mock import patch

from core.analyzer import AnalisadorRequerimentos


class ConstruirSecaoExigenciasSarTest(unittest.TestCase):
    def construir_secao(self, dados_requerimento):
        return AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento=dados_requerimento,
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
        )

    def test_valor_sar_em_string_decimal_brasileira_nao_gera_exigencia(self):
        dados_requerimento = {
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"SAR (W/Kg) Membro": "0,776"},
                        ],
                    },
                ],
            },
        }

        secao = self.construir_secao(dados_requerimento)

        self.assertNotIn("Registrar a avaliação da conformidade", secao)


    def test_campos_sar_sem_medicao_geram_exigencia(self):
        dados_requerimento = {
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"SAR (W/Kg) Membro": "-"},
                        ],
                    },
                ],
            },
        }

        secao = self.construir_secao(dados_requerimento)

        self.assertIn("Registrar a avaliação da conformidade", secao)

    def test_identifica_medicao_eirp_nas_caracteristicas_tecnicas(self):
        dados_requerimento = {
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"Potência de Pico E.I.R.P. (dBm)": ""},
                            {"Potência Média E.I.R.P. (mW)": "1,25"},
                        ],
                    },
                ],
            },
        }

        self.assertTrue(AnalisadorRequerimentos._contem_medicao_eirp(dados_requerimento))

    def test_identifica_eirp_sem_diferenciar_maiusculas_e_aceita_numero_json(self):
        dados_requerimento = {
            "Potência Média eIrP (W)": 0.5,
        }

        self.assertTrue(AnalisadorRequerimentos._contem_medicao_eirp(dados_requerimento))

    def test_nao_identifica_medicao_eirp_vazia_ou_nao_numerica(self):
        dados_requerimento = {
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"Potência Média E.I.R.P. (dBm)": ""},
                            {"Potência Média E.I.R.P. (mW)": "-"},
                            {"Potência de Pico E.I.R.P. (dBm)": "indisponível"},
                            {"Potência Máxima (W)": "10"},
                        ],
                    },
                ],
            },
        }

        self.assertFalse(AnalisadorRequerimentos._contem_medicao_eirp(dados_requerimento))

    def test_exige_preenchimento_dos_campos_eirp_quando_nao_ha_medicao(self):
        dados_requerimento = {
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"Potência Média E.I.R.P. (dBm)": ""},
                            {"Potência Média E.I.R.P. (mW)": "-"},
                        ],
                    },
                ],
            },
        }

        campos_sem_medicao = AnalisadorRequerimentos._obter_campos_eirp_sem_medicao(
            dados_requerimento
        )
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento=dados_requerimento,
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
            campos_eirp_sem_medicao=campos_sem_medicao,
        )

        self.assertIn(
            "Não foram preenchidos os valores de Potência Média E.I.R.P. (dBm), "
            "como informados no CCT",
            secao,
        )
        self.assertIn(
            "Não foram preenchidos os valores de Potência Média E.I.R.P. (mW), "
            "como informados no CCT",
            secao,
        )

    def test_nao_exige_preenchimento_eirp_quando_ha_algum_valor_numerico(self):
        dados_requerimento = {
            "Potência Média E.I.R.P. (dBm)": "",
            "Potência Média E.I.R.P. (mW)": "1,25",
        }

        self.assertEqual(
            AnalisadorRequerimentos._obter_campos_eirp_sem_medicao(
                dados_requerimento
            ),
            [],
        )

    def test_medicao_sar_marca_ato_17865_azul_em_ract_e_cct(self):
        dados_requerimento = {
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"SAR (W/Kg) Membro": "0,776"},
                        ],
                    },
                ],
            },
        }
        analisador = AnalisadorRequerimentos.__new__(AnalisadorRequerimentos)
        analisador.normas = [
            {
                "id": "ato17865",
                "nome": "Ato nº 17865, de 30 de dezembro de 2023",
                "url": "",
                "status": "vigente",
            },
        ]

        tabela = analisador._gerar_tabela_normativos_latex(
            normas_aplicaveis_por_tipo={},
            normas_verificadas_por_tipo={"RACT": set(), "CCT": set()},
            equipamentos_rotulos={},
            medicao_sar_identificada=AnalisadorRequerimentos._contem_medicao_sar(
                dados_requerimento
            ),
        )

        self.assertIn("Ato nº 17865, de 30 de dezembro de 2023", tabela)
        self.assertIn(r"\textcolor{blue}{RACT}", tabela)
        self.assertIn(r"\textcolor{blue}{CCT}", tabela)
        self.assertNotIn(r"\textcolor{red}{RACT}", tabela)
        self.assertNotIn(r"\textcolor{red}{CCT}", tabela)


class ValidarCaracteristicasTecnicasTest(unittest.TestCase):
    def setUp(self):
        self.analisador = object.__new__(AnalisadorRequerimentos)

    def test_aceita_frequencia_fundamental_como_faixa_de_transmissao(self):
        with patch("core.analyzer.HomologacaoProduto.model_validate") as validar:
            resultado = self.analisador._validar_registros_frequencia(
                [{"Frequência Fundamental (MHz)": "314,98"}], set()
            )

        self.assertEqual(resultado[0]["valida"], "sim")
        frequencia_validada = validar.call_args.args[0]["frequencias"][0]
        self.assertEqual(
            frequencia_validada["Faixa de Frequências Tx (MHz)"], "314,98"
        )

    def test_ignora_caracteristica_sem_campo_de_frequencia(self):
        with patch("core.analyzer.HomologacaoProduto.model_validate") as validar:
            resultado = self.analisador._validar_registros_frequencia(
                [{"Tempo de Transmissão": "5", "Unidade": "s"}], set()
            )

        self.assertEqual(resultado, [])
        validar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
