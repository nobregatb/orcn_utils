import unittest

from core.analyzer import AnalisadorRequerimentos, _cct_exige_declaracao_ipv6


class CctExigeDeclaracaoIpv6Test(unittest.TestCase):
    def construir_secao_exigencias(self, texto_cct):
        return AnalisadorRequerimentos._construir_secao_exigencias(
            dados_requerimento={},
            cct_contem_ipv6=_cct_exige_declaracao_ipv6(texto_cct),
            cct_contem_produto_nao_acabado=False,
            cct_contem_palavra_vinculado=False,
            caracteristicas_nao_conformes=[],
            cct_desobriga_sar=True,
        )

    def test_frases_de_excecao_nao_geram_exigencia(self):
        textos = [
            "Não suporta IPv6.",
            "NÃO IMPLEMENTA IPV6!",
            "IPv6 não aplicável.",
            "N a o  s u p o r t a  I P V 6.",
        ]

        for texto in textos:
            with self.subTest(texto=texto):
                self.assertFalse(_cct_exige_declaracao_ipv6(texto))

    def test_mencao_sem_excecao_gera_exigencia(self):
        self.assertTrue(_cct_exige_declaracao_ipv6("Suporta IPv6."))

    def test_frase_de_excecao_nao_adiciona_exigencia(self):
        secao = self.construir_secao_exigencias("Não suporta IPv6.")

        self.assertNotIn("Que o produto Implementa protocolo IPv6;", secao)

    def test_mencao_sem_excecao_adiciona_exigencia(self):
        secao = self.construir_secao_exigencias("Suporta IPv6.")

        self.assertIn("Que o produto Implementa protocolo IPv6;", secao)

    def test_mencao_em_outra_frase_gera_exigencia(self):
        self.assertTrue(
            _cct_exige_declaracao_ipv6("Não suporta IPv6. Implementa IPv6.")
        )

    def test_outra_mencao_na_mesma_frase_gera_exigencia(self):
        self.assertTrue(
            _cct_exige_declaracao_ipv6("Não suporta IPv6, mas usa IPv6.")
        )

    def test_texto_sem_ipv6_nao_gera_exigencia(self):
        self.assertFalse(_cct_exige_declaracao_ipv6("Produto sem essa menção."))


if __name__ == "__main__":
    unittest.main()
