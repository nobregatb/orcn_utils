import unittest
from datetime import datetime

from core.analyzer import (
    TIPO_CCT,
    TIPO_RACT,
    _chave_selecao_documento,
    _extrair_datas_documento,
)


class ExtrairDatasDocumentoTest(unittest.TestCase):
    def test_extrai_datas_numericas_e_por_extenso_em_portugues(self):
        datas = _extrair_datas_documento(
            "31/12/2025 e 11 de setembro de 2026; 02 de março de 2024"
        )

        self.assertEqual(
            datas,
            [
                datetime(2025, 12, 31),
                datetime(2026, 9, 11),
                datetime(2024, 3, 2),
            ],
        )

    def test_ignora_datas_invalidas_e_usa_a_data_mais_recente(self):
        datas = _extrair_datas_documento(
            "31/02/2025, 11 de mês de 2026 e 31/12/2025"
        )

        self.assertEqual(max(datas), datetime(2025, 12, 31))


class ChaveSelecaoDocumentoTest(unittest.TestCase):
    def test_data_do_conteudo_prevalece_sobre_data_do_nome_em_cct_e_ract(self):
        data_conteudo_antiga = datetime(2025, 12, 31)
        data_conteudo_recente = datetime(2026, 9, 11)
        data_nome_mais_recente = datetime(2026, 10, 1)

        for tipo_documento in (TIPO_CCT, TIPO_RACT):
            with self.subTest(tipo_documento=tipo_documento):
                chave_antiga = _chave_selecao_documento(
                    tipo_documento, data_conteudo_antiga, data_nome_mais_recente
                )
                chave_recente = _chave_selecao_documento(
                    tipo_documento, data_conteudo_recente, datetime(2025, 1, 1)
                )

                self.assertGreater(chave_recente, chave_antiga)

    def test_data_do_nome_desempata_datas_iguais_no_conteudo(self):
        data_conteudo = datetime(2026, 9, 11)

        chave_antiga = _chave_selecao_documento(
            TIPO_CCT, data_conteudo, datetime(2025, 1, 1)
        )
        chave_recente = _chave_selecao_documento(
            TIPO_CCT, data_conteudo, datetime(2026, 1, 1)
        )

        self.assertGreater(chave_recente, chave_antiga)


if __name__ == "__main__":
    unittest.main()
