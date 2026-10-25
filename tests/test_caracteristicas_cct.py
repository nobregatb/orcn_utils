import unittest

from core.caracteristicas_cct import linhas_cct_de_tabelas, validar_caracteristicas_no_cct

CABECALHO = ["Faixa", "Potência Máxima (W)", "Tecnologias", "Tipo de Modulação", "Designação de Emissões"]
# Linha do CCT: col2 com dois valores, col3 e col4 com três valores, col5 com dois.
LINHA_CCT = ["2400", "0,1\n0,2", "A\nB\nC", "X\nY\nZ", "E1\nE2"]


def reg(faixa, potencia, tecnologia, modulacao, emissao):
    return {
        "Faixa": faixa,
        "Potência Máxima (W)": potencia,
        "Tecnologias": tecnologia,
        "Tipo de Modulação": modulacao,
        "Designação de Emissões": emissao,
    }


def validar(registros, tabela=None):
    tabela = tabela or [LINHA_CCT]
    return validar_caracteristicas_no_cct(
        [("Produto", registros)], linhas_cct_de_tabelas([[CABECALHO] + tabela])
    )


class ValidacaoCaracteristicasCCTTest(unittest.TestCase):
    def test_hipotese_1_valores_de_uma_celula_separados_em_linhas(self):
        self.assertEqual(validar([
            reg("2400", "0,1", "A B C", "X Y Z", "E1 E2"),
            reg("2400", "0,2", "A B C", "X Y Z", "E1 E2"),
        ]), [])

    def test_hipotese_2_produto_cartesiano_em_uma_coluna(self):
        self.assertEqual(validar([
            reg("2400", "0,1 0,2", "A", "X Y Z", "E1 E2"),
            reg("2400", "0,1 0,2", "B", "X Y Z", "E1 E2"),
            reg("2400", "0,1 0,2", "C", "X Y Z", "E1 E2"),
        ]), [])

    def test_hipotese_3_produto_cartesiano_em_duas_colunas(self):
        registros = [
            reg("2400", "0,1 0,2", tecnologia, "X Y Z", emissao)
            for emissao in ("E1", "E2")
            for tecnologia in ("A", "B", "C")
        ]
        self.assertEqual(validar(registros), [])

    def test_hipotese_4_valor_ausente_na_ultima_coluna(self):
        pendencias = validar([
            reg("2400", "0,1 0,2", "A B C", "X Y Z", "E1 E9"),
            reg("2400", "0,1 0,2", "A B C", "X Y Z", "E1 E2"),
        ])
        self.assertEqual(len(pendencias), 1)
        self.assertEqual(pendencias[0]["faltantes"], [("Designação de Emissões", "E9")])

    def test_hipotese_5_valor_ausente_na_primeira_coluna(self):
        pendencias = validar([
            reg("9999", "0,1 0,2", "A B C", "X Y Z", "E1 E2"),
            reg("2400", "0,1 0,2", "A B C", "X Y Z", "E1 E2"),
        ])
        self.assertEqual(len(pendencias), 1)
        self.assertEqual(pendencias[0]["faltantes"], [("Faixa", "9999")])

    def test_n_upla_nao_mistura_valores_de_linhas_diferentes_do_cct(self):
        tabela = [["2400", "0,1", "A", "X", "-"], ["5150", "0,2", "B", "Y", "-"]]
        pendencias = validar([reg("2400", "0,2", "A", "X", "-")], tabela)
        self.assertEqual(len(pendencias), 1)

    def test_celula_mesclada_e_formatos_diferentes_sao_aceitos(self):
        tabela = [["2400 – 2483,5", "0,014", "Sequência Direta\nBluetooth LE", "BPSK\n16-QAM", "-"],
                  [None, "0,013", "OFDM\n802.11g", "BPSK\n16 QAM", "-"]]
        self.assertEqual(validar([
            reg("2400;2483,5", "0,014", "SEQÜÊNCIA DIRETA", "BPSK", "-"),
            reg("2400;2483,5", "0,013", "OFDM", "BPSK 16-QAM", "-"),
        ], tabela), [])

    def test_dicionario_de_equivalencias_ignora_caixa_e_acentos(self):
        tabela = [["2400", "0,1", "Sequência Direta\nOFDM", "X", "-"]]
        self.assertEqual(validar([
            reg("2400", "0,1", "DSSS", "X", "-"),
            reg("2400", "0,1", "OFDMA", "X", "-"),
            reg("2400", "0,1", "SEQUENCIA direta", "X", "-"),
        ], tabela), [])

    def test_valor_existente_em_outra_linha_e_sinalizado(self):
        tabela = [["2400", "0,1", "DSSS", "X", "-"], ["2400", "0,2", "OFDM", "X", "-"]]
        pendencias = validar([reg("2400", "0,1", "OFDM", "X", "-")], tabela)
        self.assertEqual(pendencias[0]["faltantes"], pendencias[0]["em_outra_linha"])

    def test_termo_fora_do_dicionario_continua_ausente(self):
        pendencias = validar([reg("2400", "0,1", "FHSS", "X", "-")], [["2400", "0,1", "DSSS", "X", "-"]])
        self.assertEqual(pendencias[0]["faltantes"], [("Tecnologias", "FHSS")])


if __name__ == "__main__":
    unittest.main()
