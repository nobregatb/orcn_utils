import unittest
import json
import os
from datetime import date, timedelta
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from core.downloader_certifica import (
    _data_emissao_cct_ate_hoje,
    extrair_dados_requerimento_certifica,
    tabela_por_cabecalho,
)
from core.const import (
    CERTIFICA_ABA_ESPECIFICACOES, CERTIFICA_ABA_PRODUTO,
    CERTIFICA_JS_LER_ABA, CHROME_PATH,
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
    @unittest.skipUnless(os.path.exists(CHROME_PATH), "Chrome não disponível")
    def test_extracao_da_aba_preserva_produto_principal_e_subproduto_no_json(self):
        """A captura no navegador separa tabelas de produtos e preserva linhas repetidas."""
        html = """
        <div id="wttab_EspecTecnica_block_wtContent">
          <table><tr><td>Frequência Fundamental (MHz)</td><td>Potência</td></tr>
            <tr><td>433</td><td>5</td></tr><tr><td>433</td><td>5</td></tr></table>
          <div class="ListRecords"><div>Subproduto</div><div>
            <table><tr><td>Faixa</td></tr><tr><td>2400</td></tr></table>
          </div></div>
        </div>
        """
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=CHROME_PATH, headless=True)
            page = browser.new_page()
            page.set_content(html)
            aba_especificacoes = page.evaluate(CERTIFICA_JS_LER_ABA, CERTIFICA_ABA_ESPECIFICACOES)
            browser.close()

        aba_vazia = {"pares": [], "tabelas": [], "registros": [], "subprodutos": []}
        abas = {
            CERTIFICA_ABA_PRODUTO: {**aba_vazia, "pares": [["Produto", "Dispositivo de Operação Periódica"]]},
            CERTIFICA_ABA_ESPECIFICACOES: aba_especificacoes,
        }
        with patch("core.downloader_certifica.ler_aba_certifica", side_effect=lambda page, sufixo: abas.get(sufixo, aba_vazia)):
            dados = json.loads(json.dumps(extrair_dados_requerimento_certifica(None)))

        produtos = dados["caracteristicas_tecnicas"]["produtos"]
        self.assertEqual(produtos[0]["caracteristicas"], [
            {"Frequência Fundamental (MHz)": "433", "Potência": "5"},
            {"Frequência Fundamental (MHz)": "433", "Potência": "5"},
        ])
        self.assertEqual(produtos[1], {"nome": "Subproduto", "caracteristicas": [["Faixa"], ["2400"]]})

    def test_extrai_caracteristicas_sem_cabecalho_de_frequencia(self):
        """Características de equipamentos com outras colunas devem ser preservadas."""
        aba_vazia = {"pares": [], "tabelas": [], "registros": [], "subprodutos": []}
        abas = {
            CERTIFICA_ABA_PRODUTO: {**aba_vazia, "pares": [["Produto", "Dispositivo de Operação Periódica"]]},
            CERTIFICA_ABA_ESPECIFICACOES: {
                **aba_vazia,
                "tabelas": [[['Tempo de Transmissão', 'Unidade'], ['5', 's']]],
            },
        }
        with patch("core.downloader_certifica.ler_aba_certifica", side_effect=lambda page, sufixo: abas.get(sufixo, aba_vazia)):
            dados = extrair_dados_requerimento_certifica(None)

        self.assertEqual(dados["caracteristicas_tecnicas"]["produtos"][0]["caracteristicas"], [
            {"Tempo de Transmissão": "5", "Unidade": "s"},
        ])

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
