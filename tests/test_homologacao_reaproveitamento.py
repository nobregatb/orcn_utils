import json
import os
import tempfile
import unittest
from typing import cast
from unittest.mock import patch

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from core.const import CHROME_PATH
from core.homologacao_reaproveitamento import (
    GerenciadorReaproveitamentoHomologacao,
    abrir_alteracao_homologacao,
    atualizar_numero_homologacao_json,
    confirmar_alteracao_homologacao,
    localizar_link_requerimento_na_tabela,
    preencher_numero_homologacao,
    preencher_numero_requerimento_filtro,
    processar_reaproveitamento_homologacao_apos_download,
)


@unittest.skipUnless(os.path.exists(CHROME_PATH), "Chrome não disponível")
class PreencherNumeroRequerimentoFiltroTest(unittest.TestCase):
    def setUp(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
        )
        self.page = self.browser.new_page()

    def tearDown(self):
        self.browser.close()
        self.playwright.stop()

    def test_prefere_rotulo_visivel_e_preserva_zero_inicial(self):
        self.page.set_content(
            """
            <input type="hidden" name="NumeroRequerimento" value="valor antigo">
            <label for="req">Número do Requerimento</label>
            <input id="req" type="text">
            """
        )

        preencher_numero_requerimento_filtro(self.page, "09794/26")

        self.assertEqual(self.page.locator("#req").input_value(), "09794/26")
        self.assertEqual(
            self.page.locator('input[type="hidden"]').input_value(),
            "valor antigo",
        )

    def test_digita_tecla_a_tecla_em_campo_mascarado(self):
        self.page.set_content(
            """
            <input id="req" type="text" placeholder="Informe o Número do Requerimento">
            <script>
              const campo = document.querySelector("#req");
              campo.addEventListener("input", event => {
                if (event.data && event.data.length > 1) {
                  campo.value = "_____/_0";
                }
              });
            </script>
            """
        )

        preencher_numero_requerimento_filtro(self.page, "09794/26")

        self.assertEqual(self.page.locator("#req").input_value(), "09794/26")

    def test_preenche_numero_de_homologacao_mascarado_tecla_a_tecla(self):
        self.page.set_content(
            """
            <input id="homologacao" type="text" placeholder="Número de Homologação">
            <script>
              const campo = document.querySelector("#homologacao");
              campo.addEventListener("input", event => {
                if (event.data && event.data.length > 1) {
                  campo.value = "_____-__-____1";
                }
              });
            </script>
            """
        )

        preencher_numero_homologacao(self.page, "10137-24-11209")

        self.assertEqual(
            self.page.locator("#homologacao").input_value(),
            "10137-24-11209",
        )

    @patch("core.homologacao_reaproveitamento.TEMPO_ABERTURA_HOMOLOGACAO_MS", 3000)
    def test_aguarda_abertura_do_formulario_sem_repetir_clique(self):
        self.page.set_content(
            """
            <input type="button" value="Alterar Número de Homologação"
                   onclick="window.cliques++; setTimeout(() => {
                     document.querySelector('#formulario').hidden = false;
                   }, 500)">
            <fieldset id="formulario" hidden>
              <legend>Altera Numero de Homologação</legend>
              <input placeholder="Número de Homologação">
            </fieldset>
            <script>window.cliques = 0;</script>
            """
        )

        abrir_alteracao_homologacao(self.page)

        self.assertEqual(self.page.evaluate("window.cliques"), 1)
        self.assertTrue(
            self.page.get_by_placeholder("Número de Homologação").is_visible()
        )

    @patch("core.homologacao_reaproveitamento.TEMPO_ABERTURA_HOMOLOGACAO_MS", 300)
    def test_falha_se_formulario_nao_abrir(self):
        self.page.set_content(
            """
            <input type="button" value="Alterar Número de Homologação"
                   onclick="window.cliques++">
            <fieldset hidden>
              <legend>Altera Numero de Homologação</legend>
              <input placeholder="Número de Homologação">
            </fieldset>
            <script>window.cliques = 0;</script>
            """
        )

        with self.assertRaisesRegex(TimeoutError, "não abriu após"):
            abrir_alteracao_homologacao(self.page)

        self.assertEqual(self.page.evaluate("window.cliques"), 1)
        self.assertFalse(
            self.page.get_by_placeholder("Número de Homologação").is_visible()
        )

    def test_confirma_no_formulario_mesmo_com_outros_botoes(self):
        self.page.set_content(
            """
            <input type="button" value="Confirma" hidden>
            <button onclick="window.outros++">Confirma</button>
            <fieldset>
              <legend>Altera Numero de Homologação</legend>
              <input placeholder="Número de Homologação">
              <input type="button" value="Confirma" onclick="
                window.confirmacoes++;
                document.querySelector('#resultado').textContent =
                  'Número de homologação alterado com sucesso.';
              ">
            </fieldset>
            <div id="resultado"></div>
            <script>window.outros = 0; window.confirmacoes = 0;</script>
            """
        )

        confirmar_alteracao_homologacao(self.page)

        self.assertEqual(self.page.evaluate("window.outros"), 0)
        self.assertEqual(self.page.evaluate("window.confirmacoes"), 1)

    @patch("core.homologacao_reaproveitamento.CERTIFICA_TIMEOUT_PAGINA", 300)
    def test_confirmacao_sem_mensagem_de_sucesso_falha(self):
        self.page.set_content(
            """
            <fieldset>
              <legend>Altera Numero de Homologação</legend>
              <input type="button" value="Confirma" onclick="window.cliques++">
            </fieldset>
            <script>window.cliques = 0;</script>
            """
        )

        with self.assertRaises(PlaywrightTimeoutError):
            confirmar_alteracao_homologacao(self.page)
        self.assertEqual(self.page.evaluate("window.cliques"), 1)

    def test_aguarda_campo_ser_renderizado_apos_abrir_filtro(self):
        self.page.set_content(
            """
            <div id="filtro"></div>
            <script>
              setTimeout(() => {
                const campo = document.createElement("input");
                campo.id = "req";
                campo.placeholder = "Informe o Número do Requerimento";
                document.querySelector("#filtro").appendChild(campo);
              }, 500);
            </script>
            """
        )

        preencher_numero_requerimento_filtro(self.page, "09715/26")

        self.assertEqual(self.page.locator("#req").input_value(), "09715/26")

    def test_nao_escolhe_arbitrariamente_entre_campos_rotulados_duplicados(self):
        self.page.set_content(
            """
            <label for="req-1">Número do Requerimento</label>
            <input id="req-1" type="text">
            <label for="req-2">Número do Requerimento</label>
            <input id="req-2" type="text">
            """
        )

        with self.assertRaisesRegex(RuntimeError, "Mais de um campo visível"):
            preencher_numero_requerimento_filtro(self.page, "09794/26")

    def test_localiza_campo_visivel_por_id_quando_rotulo_nao_esta_associado(self):
        self.page.set_content(
            """
            <span>Número do Requerimento</span>
            <input id="wtInputNumeroRequerimento" type="text">
            """
        )

        preencher_numero_requerimento_filtro(self.page, "09794/26")

        self.assertEqual(
            self.page.locator("#wtInputNumeroRequerimento").input_value(),
            "09794/26",
        )

    def test_localiza_requerimento_na_tabela_correta_e_por_texto_exato(self):
        self.page.set_content(
            """
            <table style="display: none">
              <tr><td><a href="/hidden">09715/26</a></td></tr>
            </table>
            <table>
              <thead><tr><th>N° do Requerimento</th><th>Status</th></tr></thead>
              <tbody>
                <tr><td><a href="/09715/26">09715/26</a></td><td>Em análise</td></tr>
                <tr><td><a href="/09715/260">09715/260</a></td><td>Em análise</td></tr>
              </tbody>
            </table>
            """
        )

        link = localizar_link_requerimento_na_tabela(self.page, "09715/26")

        if link is None:
            self.fail("O link do requerimento não foi localizado.")
        self.assertEqual(link.get_attribute("href"), "/09715/26")


class AtualizarNumeroHomologacaoJsonTest(unittest.TestCase):
    def test_atualiza_codigo_sem_alterar_os_demais_dados(self):
        conteudo = {
            "requerimento": {
                "num_req": "09794/26",
                "cod_homologacao": "09794-26-11209",
            },
            "fabricante": {"Razão Social": "Exemplo"},
        }
        with tempfile.TemporaryDirectory() as diretorio:
            caminho_json = os.path.join(diretorio, "26.09794.json")
            with open(caminho_json, "w", encoding="utf-8") as arquivo:
                json.dump(conteudo, arquivo, ensure_ascii=False)

            self.assertTrue(
                atualizar_numero_homologacao_json(caminho_json, "10137-24-11209")
            )

            with open(caminho_json, "r", encoding="utf-8") as arquivo:
                atualizado = json.load(arquivo)

        self.assertEqual(
            atualizado["requerimento"]["cod_homologacao"],
            "10137-24-11209",
        )
        self.assertEqual(atualizado["requerimento"]["num_req"], "09794/26")
        self.assertEqual(atualizado["fabricante"], conteudo["fabricante"])

    @patch(
        "core.homologacao_reaproveitamento.atualizar_numero_homologacao_json",
        return_value=True,
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "alterar_numero_homologacao_no_certifica",
        return_value=True,
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "buscar_novo_numero_homologacao",
        return_value="10137-24-11209",
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "num_req_corresponde_cod_homologacao",
        return_value=True,
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "extrair_cod_homologacao_do_json",
        return_value="09794-26-11209",
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "extrair_num_req_do_json",
        return_value="09794/26",
    )
    def test_persiste_json_somente_apos_confirmacao_no_certifica(
        self,
        _extrair_num_req,
        _extrair_codigo,
        _corresponde,
        _buscar_numero,
        alterar_no_certifica,
        atualizar_json,
    ):
        resultado = processar_reaproveitamento_homologacao_apos_download(
            "pasta",
            "requerimento.json",
            page=cast(Page, None),
        )

        self.assertTrue(resultado)
        _extrair_num_req.assert_called_once_with("requerimento.json")
        _extrair_codigo.assert_called_once_with("requerimento.json")
        _corresponde.assert_called_once_with("09794/26", "09794-26-11209")
        _buscar_numero.assert_called_once_with("pasta", "09794-26-11209")
        alterar_no_certifica.assert_called_once()
        atualizar_json.assert_called_once_with(
            "requerimento.json",
            "10137-24-11209",
        )

    @patch(
        "core.homologacao_reaproveitamento.atualizar_numero_homologacao_json",
        return_value=True,
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "alterar_numero_homologacao_no_certifica",
        return_value=False,
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "buscar_novo_numero_homologacao",
        return_value="10137-24-11209",
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "num_req_corresponde_cod_homologacao",
        return_value=True,
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "extrair_cod_homologacao_do_json",
        return_value="09794-26-11209",
    )
    @patch.object(
        GerenciadorReaproveitamentoHomologacao,
        "extrair_num_req_do_json",
        return_value="09794/26",
    )
    def test_nao_persiste_json_se_alteracao_no_certifica_falhar(
        self,
        _extrair_num_req,
        _extrair_codigo,
        _corresponde,
        _buscar_numero,
        alterar_no_certifica,
        atualizar_json,
    ):
        resultado = processar_reaproveitamento_homologacao_apos_download(
            "pasta",
            "requerimento.json",
            page=cast(Page, None),
        )

        self.assertFalse(resultado)
        _extrair_num_req.assert_called_once_with("requerimento.json")
        _extrair_codigo.assert_called_once_with("requerimento.json")
        _corresponde.assert_called_once_with("09794/26", "09794-26-11209")
        _buscar_numero.assert_called_once_with("pasta", "09794-26-11209")
        alterar_no_certifica.assert_called_once()
        atualizar_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
