#!/usr/bin/env python3
"""
Demo do Sistema de Análise ORCN
Demonstra as funcionalidades do analisador de requerimentos
"""

from core.analyzer import AnalisadorRequerimentos
from core.log_print import log_info
import os
from pathlib import Path

def criar_estrutura_demo():
    """Cria uma estrutura de exemplo para demonstração."""
    print("🔧 Criando estrutura de demonstração...")
    
    # Criar pasta de downloads com requerimentos de exemplo
    pasta_downloads = Path("downloads")
    pasta_downloads.mkdir(exist_ok=True)
    
    # Criar alguns requerimentos de exemplo
    requerimentos_exemplo = [
        "REQ_2024_001",
        "REQ_2024_002", 
        "REQ_2024_003"
    ]
    
    for req in requerimentos_exemplo:
        pasta_req = pasta_downloads / req
        pasta_req.mkdir(exist_ok=True)
        
        # Criar arquivos PDF de exemplo (vazios, apenas para demonstração)
        arquivos_exemplo = [
            f"{req}_CCT_Certificado.pdf",
            f"{req}_RACT_Relatorio.pdf",
            f"{req}_Manual_Produto.pdf",
            f"{req}_Fotos_Produto.pdf",
            f"{req}_ART_Responsavel.pdf"
        ]
        
        for arquivo in arquivos_exemplo:
            caminho_arquivo = pasta_req / arquivo
            if not caminho_arquivo.exists():
                # Criar arquivo vazio para demonstração
                caminho_arquivo.write_text("# Arquivo PDF de demonstração\n")
    
    print(f"✅ Estrutura criada com {len(requerimentos_exemplo)} requerimentos de exemplo")
    print(f"📁 Pasta: {pasta_downloads.absolute()}")

def main():
    """Função principal da demonstração."""
    print("="*60)
    print("🚀 DEMO - SISTEMA DE ANÁLISE ORCN")
    print("="*60)
    
    # Verificar se existem requerimentos
    pasta_downloads = Path("downloads")
    if not pasta_downloads.exists() or not any(pasta_downloads.iterdir()):
        print("❓ Não foram encontrados requerimentos para análise.")
        resposta = input("Deseja criar uma estrutura de demonstração? (s/n): ").strip().lower()
        if resposta in ['s', 'sim', 'y', 'yes']:
            criar_estrutura_demo()
        else:
            print("❌ Demo cancelado.")
            return
    
    # Executar análise
    print("\n🔍 Iniciando demonstração da análise...")
    analisador = AnalisadorRequerimentos()
    analisador.executar_analise()
    
    print("\n" + "="*60)
    print("✅ Demonstração concluída!")
    print("="*60)
    print("\n📋 Próximos passos:")
    print("1. Verifique a pasta 'resultados_analise' para os relatórios gerados")
    print("2. O arquivo JSON contém dados estruturados da análise")
    print("3. O arquivo LaTeX pode ser compilado para PDF")
    print("4. Para usar em produção, coloque os PDFs reais na pasta 'downloads'")

if __name__ == "__main__":
    main()