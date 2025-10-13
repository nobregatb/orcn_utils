#!/usr/bin/env python3
"""
Teste rápido do sistema de análise ORCN
Verifica se todos os componentes estão funcionais
"""

import sys
from pathlib import Path
import json

def testar_imports():
    """Testa se todos os imports necessários funcionam."""
    print("🔍 Testando imports...")
    
    try:
        from core.analyzer import AnalisadorRequerimentos
        print("✅ core.analyzer - OK")
    except ImportError as e:
        print(f"❌ core.analyzer - ERRO: {e}")
        return False
    
    try:
        from core.log_print import log_info, log_erro
        print("✅ core.log_print - OK")
    except ImportError as e:
        print(f"❌ core.log_print - ERRO: {e}")
        return False
    
    try:
        from core.menu import exibir_menu
        print("✅ core.menu - OK")
    except ImportError as e:
        print(f"❌ core.menu - ERRO: {e}")
        return False
    
    return True

def testar_configuracao():
    """Testa se os arquivos de configuração existem."""
    print("\n🔍 Testando arquivos de configuração...")
    
    arquivos_config = [
        "utils/regras.json",
        "utils/equipamentos.json", 
        "utils/requisitos.json",
        "utils/normas.json",
        "utils/ocds.json"
    ]
    
    todos_ok = True
    for arquivo in arquivos_config:
        if Path(arquivo).exists():
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    json.load(f)
                print(f"✅ {arquivo} - OK")
            except json.JSONDecodeError:
                print(f"⚠️ {arquivo} - JSON inválido")
                todos_ok = False
        else:
            print(f"❌ {arquivo} - Não encontrado")
            todos_ok = False
    
    return todos_ok

def testar_instanciacao():
    """Testa se a classe principal pode ser instanciada."""
    print("\n🔍 Testando instanciação do analisador...")
    
    try:
        from core.analyzer import AnalisadorRequerimentos
        analisador = AnalisadorRequerimentos()
        print("✅ AnalisadorRequerimentos instanciado com sucesso")
        
        # Testar métodos básicos
        requerimentos = analisador._listar_requerimentos()
        print(f"✅ Método _listar_requerimentos funcionando - {len(requerimentos)} requerimentos encontrados")
        
        return True
    except Exception as e:
        print(f"❌ Erro na instanciação: {e}")
        return False

def testar_estrutura_pastas():
    """Testa se a estrutura de pastas está adequada."""
    print("\n🔍 Testando estrutura de pastas...")
    
    pastas_esperadas = [
        "core",
        "utils", 
        "instrucoes"
    ]
    
    pastas_opcionais = [
        "downloads",
        "resultados_analise"
    ]
    
    for pasta in pastas_esperadas:
        if Path(pasta).exists():
            print(f"✅ {pasta}/ - OK")
        else:
            print(f"❌ {pasta}/ - Não encontrada")
            return False
    
    for pasta in pastas_opcionais:
        if Path(pasta).exists():
            print(f"✅ {pasta}/ - OK")
        else:
            print(f"ℹ️ {pasta}/ - Será criada quando necessário")
    
    return True

def main():
    """Executa todos os testes."""
    print("="*60)
    print("🧪 TESTE DO SISTEMA DE ANÁLISE ORCN")
    print("="*60)
    
    testes = [
        ("Imports", testar_imports),
        ("Configuração", testar_configuracao), 
        ("Estrutura de Pastas", testar_estrutura_pastas),
        ("Instanciação", testar_instanciacao)
    ]
    
    resultados = {}
    
    for nome_teste, funcao_teste in testes:
        print(f"\n📋 Executando teste: {nome_teste}")
        print("-" * 40)
        resultado = funcao_teste()
        resultados[nome_teste] = resultado
    
    # Sumário final
    print("\n" + "="*60)
    print("📊 SUMÁRIO DOS TESTES")
    print("="*60)
    
    todos_passaram = True
    for nome, resultado in resultados.items():
        status = "✅ PASSOU" if resultado else "❌ FALHOU"
        print(f"{nome:20} - {status}")
        if not resultado:
            todos_passaram = False
    
    print("-" * 60)
    if todos_passaram:
        print("🎉 Todos os testes passaram! Sistema pronto para uso.")
        print("\n💡 Próximos passos:")
        print("1. Execute 'python main.py' para usar o sistema")
        print("2. Execute 'python demo.py' para ver demonstrações")
        print("3. Consulte 'README_ANALYZER.md' para documentação completa")
    else:
        print("❌ Alguns testes falharam. Revise os erros acima.")
        print("\n🔧 Ações recomendadas:")
        print("1. Verifique se todos os arquivos estão presentes")
        print("2. Valide os arquivos JSON de configuração")
        print("3. Certifique-se de que as dependências estão instaladas")
    
    return 0 if todos_passaram else 1

if __name__ == "__main__":
    sys.exit(main())