#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testes para validação de e-mail do fabricante no analisador de requerimentos.
"""

import unittest
import json
from pathlib import Path
from core.analyzer import _validar_email_fabricante


class ValidarEmailFabricanteTest(unittest.TestCase):
    """Testes para a validação de e-mail do fabricante."""

    @classmethod
    def setUpClass(cls):
        """Carrega a lista de OCDs do arquivo OCDs.json."""
        ocds_path = Path(__file__).parent.parent / "utils" / "ocds.json"
        try:
            with open(ocds_path, "r", encoding="utf-8") as f:
                cls.ocds_list = json.load(f)
        except Exception:
            cls.ocds_list = []

    def test_email_valido_do_fabricante(self):
        """Testa se um e-mail válido do próprio fabricante não gera exigência."""
        dados = {
            "fabricante": {
                "E-mail": "contato@fabricante.com.br",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertIsNone(resultado, "E-mail válido não deveria gerar exigência")

    def test_email_anatel_tipo1(self):
        """Testa se e-mail ANATEL gera exigência tipo 1 (domínio proibido)."""
        dados = {
            "fabricante": {
                "E-mail": "teste@anatel.gov.br",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertEqual(resultado, (1, "teste@anatel.gov.br"))

    def test_email_ocd_tipo1(self):
        """Testa se e-mail de OCD gera exigência tipo 1 (domínio proibido)."""
        # Encontra um OCD com e-mail cadastrado
        ocd_com_email = next(
            (ocd for ocd in self.ocds_list if ocd.get("email")),
            None
        )
        if ocd_com_email:
            email_teste = f"contato@{ocd_com_email['email']}"
            dados = {
                "fabricante": {
                    "E-mail": email_teste,
                    "CNPJ": "12.345.678/0001-90"
                }
            }
            resultado = _validar_email_fabricante(dados, self.ocds_list)
            self.assertEqual(resultado[0], 1, "Deveria ser tipo 1 (domínio proibido)")
            self.assertEqual(resultado[1], email_teste)

    def test_email_formato_invalido_tipo2(self):
        """Testa se e-mail sem @ gera exigência tipo 2 (formato inválido)."""
        dados = {
            "fabricante": {
                "E-mail": "email_sem_arroba.com",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertEqual(resultado, (2, "email_sem_arroba.com"))

    def test_email_sem_dominio_tipo2(self):
        """Testa se e-mail sem domínio gera exigência tipo 2."""
        dados = {
            "fabricante": {
                "E-mail": "email@",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertEqual(resultado[0], 2, "Deveria ser tipo 2 (formato inválido)")

    def test_email_vazio_sem_exigencia(self):
        """Testa se e-mail vazio não gera exigência."""
        dados = {
            "fabricante": {
                "E-mail": "",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertIsNone(resultado)

    def test_email_ausente_sem_exigencia(self):
        """Testa se ausência de e-mail não gera exigência."""
        dados = {
            "fabricante": {
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertIsNone(resultado)

    def test_fabricante_ausente_sem_exigencia(self):
        """Testa se ausência do bloco fabricante não gera exigência."""
        dados = {}
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertIsNone(resultado)

    def test_dados_nulos_sem_exigencia(self):
        """Testa se dados nulos não geram exigência."""
        resultado = _validar_email_fabricante(None, self.ocds_list)
        self.assertIsNone(resultado)

    def test_email_case_insensitive_anatel(self):
        """Testa se a validação ANATEL é case-insensitive."""
        dados = {
            "fabricante": {
                "E-mail": "teste@ANATEL.GOV.BR",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertEqual(resultado, (1, "teste@ANATEL.GOV.BR"))

    def test_email_com_espacos(self):
        """Testa se e-mail com espaços é processado corretamente."""
        dados = {
            "fabricante": {
                "E-mail": "  contato@fabricante.com.br  ",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertIsNone(resultado, "E-mail com espaços deveria ser válido após strip")

    def test_email_campo_nome_variacao(self):
        """Testa se a função encontra o e-mail com variações de nome do campo."""
        # Teste com "email" (minúscula)
        dados_minuscula = {
            "fabricante": {
                "email": "contato@fabricante.com.br",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados_minuscula, self.ocds_list)
        self.assertIsNone(resultado)

    def test_email_sem_ponto_tipo2(self):
        """Testa se e-mail sem ponto no domínio gera exigência tipo 2."""
        dados = {
            "fabricante": {
                "E-mail": "contato@fabricante",
                "CNPJ": "12.345.678/0001-90"
            }
        }
        resultado = _validar_email_fabricante(dados, self.ocds_list)
        self.assertEqual(resultado[0], 2, "Deveria ser tipo 2 (formato inválido)")


if __name__ == "__main__":
    unittest.main()
