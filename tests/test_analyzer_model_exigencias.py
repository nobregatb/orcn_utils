import unittest

from core.analyzer import AnalisadorRequerimentos


class ConstruirSecaoExigenciasModelosTest(unittest.TestCase):
    def construir_secao(self, dados_requerimento):
        return AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento=dados_requerimento,
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
        )

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

    def test_exige_remocao_de_linhas_repetidas_e_omite_celulas_vazias(self):
        secao = self.construir_secao({
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"a": "a;b", "b": "c", "c": "", "d": "-", "e": "f"},
                            {"a": "a;b", "b": "c", "c": "", "d": "-", "e": "f"},
                            {"a": "única", "b": "linha"},
                        ],
                    },
                ],
            },
        })

        self.assertIn(
            r"\item Remover todas as cópias das linhas na tabela de "
            "características técnicas que estiverem repetidas. Como exemplo:",
            secao,
        )
        self.assertIn(r"\item (x2) [a;b][c][f]", secao)

    def test_compara_celulas_vazias_e_hifen_sem_exibi_las(self):
        secao = self.construir_secao({
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"a": "repetida", "b": "", "c": "-"},
                            {"a": "repetida", "b": "", "c": "-"},
                            {"a": "repetida", "b": "-", "c": ""},
                        ],
                    },
                ],
            },
        })

        self.assertEqual(secao.count(r"\item (x2) [repetida]"), 1)
        self.assertNotIn("[-]", secao)
        self.assertNotIn("[]", secao)

    def test_ignora_espacos_na_comparacao_mantendo_valor_original_na_exibicao(self):
        secao = self.construir_secao({
            "caracteristicas_tecnicas": {
                "produtos": [
                    {
                        "caracteristicas": [
                            {"a": "faixa  100 ; 200", "b": "modulação QPSK"},
                            {"a": "faixa 100;200", "b": "modulação QPSK"},
                        ],
                    },
                ],
            },
        })

        self.assertIn(r"\item (x2) [faixa  100 ; 200][modulação QPSK]", secao)

    def test_nao_agrupa_linhas_iguais_de_produtos_diferentes(self):
        linha = {"a": "valor"}
        secao = self.construir_secao({
            "caracteristicas_tecnicas": {
                "produtos": [
                    {"caracteristicas": [linha]},
                    {"caracteristicas": [linha]},
                ],
            },
        })

        self.assertNotIn("Remover todas as cópias", secao)

    def test_detecta_linhas_repetidas_no_formato_legado(self):
        secao = self.construir_secao({
            "frequencias": [
                {"Banda": "2,4 GHz"},
                {"Banda": "2,4 GHz"},
            ],
        })

        self.assertIn(r"\item (x2) [2,4 GHz]", secao)


if __name__ == "__main__":
    unittest.main()
