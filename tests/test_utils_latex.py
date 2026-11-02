import unittest

from core.utils import escapar_latex


class EscaparLatexTest(unittest.TestCase):
    def test_escapa_simbolo_produto(self):
        self.assertEqual(escapar_latex("∏"), r"\ensuremath{\prod}")

    def test_escapa_simbolo_produto_junto_a_caracteres_especiais(self):
        self.assertEqual(escapar_latex("∏_x"), r"\ensuremath{\prod}\_x")


if __name__ == "__main__":
    unittest.main()
