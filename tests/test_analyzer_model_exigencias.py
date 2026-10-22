import unittest

from core.analyzer import AnalisadorRequerimentos


class ConstruirSecaoExigenciasModelosTest(unittest.TestCase):
    def test_exibe_valor_encontrado_no_nome_comercial_invalido(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={
                "modelos": [
                    {"Nome Comercial": "N/A"},
                ],
                "caracteristicas_tecnicas": {
                    "produtos": [
                        {
                            "caracteristicas": [
                                {"SAR (W/Kg) Membro": "0.5"},
                            ],
                        },
                    ],
                },
            },
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
        )

        self.assertIn(
            r'\item Confirmar o nome comercial do(s) modelo(s) como sendo "N/A" '
            "ou corrigir informação cadastrada no sistema.",
            secao,
        )

    def test_exibe_cada_valor_invalido_distinto_uma_unica_vez(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={
                "modelos": [
                    {"Nome Comercial": "N/A"},
                    {"Nome Comercial": "N/A"},
                    {"Nome Comercial": "Não aplicável"},
                ],
            },
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
        )

        self.assertEqual(secao.count("Confirmar o nome comercial"), 2)
        self.assertIn('"Não aplicável"', secao)

    def test_lista_modelos_nao_encontrados_apos_exigencia_padrao(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={
                "caracteristicas_tecnicas": {
                    "produtos": [
                        {
                            "caracteristicas": [
                                {"SAR (W/Kg) Membro": "0.5"},
                            ],
                        },
                    ],
                },
            },
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            modelos_nao_encontrados=["SLC_NB_2", "SLC-NB-1"],
            cct_desobriga_sar=True,
        )

        self.assertIn(
            r"\item Informar nome(s) do(s) modelo(s) conforme CCT. "
            r"(Modelos não encontrados no CCT: SLC\_NB\_2, SLC-NB-1)",
            secao,
        )


if __name__ == "__main__":
    unittest.main()
