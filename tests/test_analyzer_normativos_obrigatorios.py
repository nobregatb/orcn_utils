import unittest
from unittest.mock import patch

from core.analyzer import AnalisadorRequerimentos


class NormativosObrigatoriosNaoCitadosRactTest(unittest.TestCase):
    def setUp(self):
        self.analisador = AnalisadorRequerimentos.__new__(AnalisadorRequerimentos)
        self.analisador.normas = [
            {
                "id": "norma_vigente",
                "nome": "Norma vigente",
                "descricao": "Descrição vigente",
                "status": "vigente",
            },
            {
                "id": "norma_revogada",
                "nome": "Norma revogada",
                "descricao": "Descrição revogada",
                "status": "revogada",
            },
            {
                "id": "norma_acessoria",
                "nome": "Norma acessória",
                "descricao": "Descrição acessória",
                "status": "acessorio",
            },
            {
                "id": "ato17865",
                "nome": "Ato nº 17865",
                "descricao": "Requisitos SAR",
                "status": "vigente",
            },
        ]

    def test_compara_somente_com_ract_e_ignora_normas_nao_vigentes(self):
        normas_aplicaveis = {
            "norma_vigente": [],
            "norma_revogada": [],
            "norma_acessoria": [],
        }
        with patch.object(
            self.analisador,
            "_coletar_normas_aplicaveis_requerimento",
            return_value=normas_aplicaveis,
        ):
            normas = self.analisador._coletar_normas_obrigatorias_nao_citadas_ract(
                {},
                {"RACT": set(), "CCT": {"norma_vigente"}},
            )

        self.assertEqual(
            normas,
            [{"nome": "Norma vigente", "descricao": "Descrição vigente"}],
        )

    def test_norma_citada_no_ract_nao_gera_exigencia(self):
        with patch.object(
            self.analisador,
            "_coletar_normas_aplicaveis_requerimento",
            return_value={"norma_vigente": []},
        ):
            normas = self.analisador._coletar_normas_obrigatorias_nao_citadas_ract(
                {},
                {"RACT": {"norma_vigente"}, "CCT": set()},
            )

        self.assertEqual(normas, [])

    def test_exclusao_de_obrigatoriedade_e_aplicada_a_todos_os_documentos(self):
        self.analisador.requisitos = []
        self.analisador.equipamentos = []
        req_dados = {
            "documentos_analisados": [
                {
                    "tipo": "RACT",
                    "dados_extraidos": {
                        "palavras_encontradas_com_normas": {
                            "aplicavel": {
                                "contador": 1,
                                "normas": ["norma_vigente"],
                                "efeito": "aplica",
                            },
                        },
                    },
                },
                {
                    "tipo": "CCT",
                    "dados_extraidos": {
                        "palavras_encontradas_com_normas": {
                            "exclusao": {
                                "contador": 1,
                                "normas": ["norma_vigente"],
                                "efeito": "desobriga",
                            },
                        },
                    },
                },
            ],
        }

        normas = self.analisador._coletar_normas_obrigatorias_nao_citadas_ract(
            req_dados,
            {"RACT": set(), "CCT": set()},
        )

        self.assertEqual(normas, [])

    def test_ato_17865_e_excluido_quando_houver_medicao_ou_desobrigacao(self):
        with patch.object(
            self.analisador,
            "_coletar_normas_aplicaveis_requerimento",
            return_value={"ato17865": []},
        ):
            sem_excecao = self.analisador._coletar_normas_obrigatorias_nao_citadas_ract(
                {},
                {"RACT": set()},
            )
            com_medicao = self.analisador._coletar_normas_obrigatorias_nao_citadas_ract(
                {},
                {"RACT": set()},
                medicao_sar_identificada=True,
            )
            desobrigado_no_cct = self.analisador._coletar_normas_obrigatorias_nao_citadas_ract(
                {},
                {"RACT": set()},
                cct_desobriga_sar=True,
            )

        self.assertEqual(sem_excecao, [{"nome": "Ato nº 17865", "descricao": "Requisitos SAR"}])
        self.assertEqual(com_medicao, [])
        self.assertEqual(desobrigado_no_cct, [])

    def test_formata_exigencia_com_nome_e_descricao(self):
        secao = AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={},
            cct_contem_ipv6=False,
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
            normas_obrigatorias_nao_citadas_ract=[
                {"nome": "Norma A", "descricao": "Descrição A"},
            ],
        )

        self.assertIn(
            "Registrar explicitamente no RACT a avaliação da conformidade, ou a não aplicabilidade,",
            secao,
        )
        self.assertIn('\\item "Norma A" - "Descrição A"', secao)


if __name__ == "__main__":
    unittest.main()