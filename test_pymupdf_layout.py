#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para validar a extração de tabelas com análise de layout aprimorada.

Este script demonstra as melhorias implementadas no PyMuPDF para análise de layout.
"""

import sys
from pathlib import Path
import pymupdf as fitz

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.caracteristicas_cct import extrair_tabelas_pdf


def testar_extracacao_tabelas(pdf_path: str) -> bool:
    """
    Testa a extração de tabelas de um PDF.
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        
    Returns:
        True se a extração foi bem-sucedida, False caso contrário
    """
    try:
        print(f"\n📄 Testando extração de tabelas: {pdf_path}")
        print("-" * 60)
        
        caminho = Path(pdf_path)
        if not caminho.exists():
            print(f"❌ Arquivo não encontrado: {pdf_path}")
            return False
        
        # Extrai as tabelas
        tabelas = extrair_tabelas_pdf(caminho)
        
        print(f"✓ Total de tabelas encontradas: {len(tabelas)}")
        
        # Análise das tabelas
        for i, tabela in enumerate(tabelas):
            if tabela:
                linhas = len(tabela)
                colunas = len(tabela[0]) if tabela else 0
                print(f"  Tabela {i+1}: {linhas}×{colunas} células")
                
                # Mostra as primeiras células
                if linhas > 0 and colunas > 0:
                    print(f"    Primeira linha: {tabela[0][:min(3, colunas)]}")
        
        print(f"✓ Extração concluída com sucesso!")
        print("-" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Erro na extração: {e}")
        import traceback
        traceback.print_exc()
        return False


def diagnosticar_pymupdf():
    """Exibe informações de diagnóstico do PyMuPDF instalado."""
    print("\n" + "=" * 60)
    print("🔧 DIAGNÓSTICO DO PYMUPDF")
    print("=" * 60)
    
    print(f"Versão PyMuPDF: {fitz.version}")
    print(f"Capacidades: find_tables={hasattr(fitz.Page, 'find_tables')}")
    
    # Tenta importar pymupdf_layout
    try:
        import pymupdf.layout
        print("Disponibilidade: ✅ pymupdf.layout disponível (PyMuPDF 2.x)")
        print("Status: UPGRADE RECOMENDADO - Descomente pymupdf.layout.activate()")
    except ImportError:
        print("Disponibilidade: ⚠️ pymupdf.layout não disponível (PyMuPDF 1.x)")
        print("Status: COMPATÍVEL - Use find_tables() nativo")
    
    print("\n📖 Para mais informações, consulte: PYMUPDF_LAYOUT_UPGRADE.md")
    print("=" * 60 + "\n")


def main():
    """Executa os testes."""
    diagnosticar_pymupdf()
    
    # Procura por PDFs na estrutura de requerimentos
    requerimentos_dir = Path(__file__).parent / "C:/Users/tbnobrega/OneDrive - ANATEL/Anatel/_ORCN/req_inbox"
    
    if requerimentos_dir.exists():
        pdfs = list(requerimentos_dir.glob("**/*.pdf"))
        
        if pdfs:
            print(f"\n📂 Encontrados {len(pdfs)} arquivos PDF na pasta de requerimentos")
            print("   Testando os 3 primeiros arquivos...")
            
            for pdf_path in pdfs[:3]:
                testar_extracacao_tabelas(str(pdf_path))
        else:
            print("\n⚠️ Nenhum arquivo PDF encontrado na pasta de requerimentos")
    else:
        print("\n⚠️ Pasta de requerimentos não encontrada")
        print("   Para testar, execute: python -m tests.test_analyzer_document_selection")
    
    print("\n✅ Testes de diagnóstico concluídos!")
    print("\n💡 Próximas etapas:")
    print("   1. Quando tiver acesso ao PyPI completo, execute: pip install pymupdf==2.1")
    print("   2. Descomente os blocos de pymupdf.layout.activate() nos arquivos")
    print("   3. Execute novamente este script para validar a melhoria")


if __name__ == "__main__":
    main()
