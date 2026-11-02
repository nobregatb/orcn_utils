import unittest
from datetime import date, timedelta

from core.downloader_certifica import (
    _data_emissao_cct_ate_hoje,
    tabela_por_cabecalho,
)
from core.analyzer import AnalisadorRequerimentos


class DataEmissaoCctAteHojeTest(unittest.TestCase):
    def test_permite_data_passada_ou_igual_a_hoje(self):
        hoje = date.today()
        ontem = hoje - timedelta(days=1)

        self.assertTrue(_data_emissao_cct_ate_hoje(ontem.strftime("%d/%m/%Y")))
        self.assertTrue(_data_emissao_cct_ate_hoje(hoje.strftime("%d/%m/%Y")))

    def test_nao_permite_data_futura(self):
        amanha = date.today() + timedelta(days=1)

        self.assertFalse(_data_emissao_cct_ate_hoje(amanha.strftime("%d/%m/%Y")))

    def test_aceita_data_iso_e_nao_permite_valor_invalido(self):
        hoje_iso = date.today().isoformat()

        self.assertTrue(_data_emissao_cct_ate_hoje(hoje_iso))
        self.assertFalse(_data_emissao_cct_ate_hoje("data inválida"))


class TabelaPorCabecalhoTest(unittest.TestCase):
    def test_preserva_linhas_repetidas_em_tabelas_com_o_mesmo_cabecalho(self):
        cabecalho = ["Faixa", "Potência"]
        linha = ["5725;5850", "0,9711"]
        aba = {
            "tabelas": [
                [cabecalho, linha],
                [cabecalho, linha],
            ],
        }

        registros = tabela_por_cabecalho(aba, "Faixa")

        self.assertEqual(registros, [
            {"Faixa": "5725;5850", "Potência": "0,9711"},
            {"Faixa": "5725;5850", "Potência": "0,9711"},
        ])
        repetidas = AnalisadorRequerimentos._extrair_linhas_caracteristicas_repetidas(
            {
                "caracteristicas_tecnicas": {
                    "produtos": [
                        {"caracteristicas": registros},
                    ],
                },
            }
        )

        self.assertEqual(repetidas, [(2, "[5725;5850][0,9711]")])

    def test_ignora_linhas_vazias_e_preserva_tabelas_sem_correspondencia(self):
        aba = {
            "tabelas": [
                [["Outro"], ["conteúdo"]],
                [["Faixa", "Potência"], ["", ""]],
                [["Faixa", "Potência"], ["5725;5850", "0,9711"]],
            ],
        }

        registros = tabela_por_cabecalho(aba, "Faixa")

        self.assertEqual(registros, [
            {"Faixa": "5725;5850", "Potência": "0,9711"},
        ])


if __name__ == "__main__":
    unittest.main()
