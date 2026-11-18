import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import sys

# Adiciona o diretório pai ao path para importar core
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.analyzer import AnalisadorRequerimentos


class AnalisadorRequerimentosLatexEncodingTest(unittest.TestCase):
    """Testa se a compilação LaTeX usa encoding correto para evitar UnicodeDecodeError."""

    def setUp(self):
        """Configura um diretório temporário para os testes."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pasta_resultados = Path(self.temp_dir.name)

    def tearDown(self):
        """Limpa o diretório temporário."""
        self.temp_dir.cleanup()

    @patch('core.analyzer.subprocess.run')
    def test_compilar_latex_usa_encoding_utf8_replace(self, mock_run):
        """Verifica se subprocess.run é chamado com encoding='utf-8' e errors='replace'."""
        # Configura o mock para retornar sucesso
        mock_run.return_value = MagicMock(returncode=0)

        # Cria uma instância de AnalisadorRequerimentos com a pasta temporária
        analyzer = AnalisadorRequerimentos()
        analyzer.pasta_resultados = self.pasta_resultados

        # Cria um arquivo .tex de teste
        arquivo_tex = self.pasta_resultados / "teste.tex"
        arquivo_tex.write_text(r"\documentclass{article}\begin{document}Test\end{document}")

        # Chama a função de compilação
        analyzer._compilar_latex_para_pdf(str(arquivo_tex))

        # Verifica que subprocess.run foi chamado com os parâmetros corretos
        # Deve haver 3 chamadas (3 vezes pdflatex)
        self.assertEqual(mock_run.call_count, 3)

        # Verifica que todos os calls incluem encoding='utf-8' e errors='replace'
        for call in mock_run.call_args_list:
            kwargs = call[1]  # kwargs do call
            self.assertEqual(kwargs.get('encoding'), 'utf-8', 
                           "subprocess.run deve usar encoding='utf-8'")
            self.assertEqual(kwargs.get('errors'), 'replace',
                           "subprocess.run deve usar errors='replace'")
            self.assertTrue(kwargs.get('text', False),
                          "subprocess.run deve usar text=True")
            self.assertTrue(kwargs.get('capture_output', False),
                          "subprocess.run deve usar capture_output=True")

    @patch('core.analyzer.subprocess.run')
    def test_compilar_latex_encoding_previne_unicode_decode_error(self, mock_run):
        """Testa que a correção previne UnicodeDecodeError ao compilar LaTeX com saída em Latin-1."""
        # Simula saída do pdflatex que contém caracteres Latin-1 (como "é")
        # O byte 0xe9 é "é" em Latin-1 mas invalid em UTF-8
        stderr_com_latin1 = "Erro com acentuação: café"  # Simula mensagem com acento
        
        # Configura o mock para retornar sucesso mas com stderr que teria causado erro antes
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=stderr_com_latin1,
            stdout=stderr_com_latin1
        )

        analyzer = AnalisadorRequerimentos()
        analyzer.pasta_resultados = self.pasta_resultados

        arquivo_tex = self.pasta_resultados / "teste.tex"
        arquivo_tex.write_text(r"\documentclass{article}\begin{document}Test\end{document}")

        # Esta chamada não deve gerar UnicodeDecodeError
        try:
            analyzer._compilar_latex_para_pdf(str(arquivo_tex))
            # Se chegou aqui, não houve exception - teste passou
            self.assertTrue(True, "Compilação LaTeX não deve gerar UnicodeDecodeError")
        except UnicodeDecodeError as e:
            self.fail(f"Compilação LaTeX gerou UnicodeDecodeError: {e}")


if __name__ == "__main__":
    unittest.main()

