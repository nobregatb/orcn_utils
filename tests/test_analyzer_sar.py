import unittest

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


if __name__ == "__main__":
    unittest.main()
