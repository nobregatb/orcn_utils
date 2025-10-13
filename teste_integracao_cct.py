#!/usr/bin/env python3
"""
Teste específico da integração CCTAnalyzer com o sistema de análise ORCN
Verifica se a análise de CCT está funcionando corretamente
"""

import sys
from pathlib import Path
import traceback

def testar_integracao_cct():
    """Testa se a integração do CCTAnalyzer está funcionando."""
    print("🔍 Testando integração CCTAnalyzer...")
    
    try:
        # Importar o analisador
        from core.analyzer import AnalisadorRequerimentos
        
        # Criar instância
        analisador = AnalisadorRequerimentos()
        print("✅ AnalisadorRequerimentos instanciado com sucesso")
        
        # Tentar importar CCTAnalyzerIntegrado
        try:
            from core.analyzer import CCTAnalyzerIntegrado
            from pathlib import Path
            print("✅ Módulo CCTAnalyzerIntegrado importado com sucesso")
            
            # Instanciar CCTAnalyzerIntegrado
            utils_dir = Path("utils")
            cct_analyzer = CCTAnalyzerIntegrado(utils_dir)
            print("✅ CCTAnalyzerIntegrado instanciado com sucesso")
            
            # Testar métodos básicos
            ocd_patterns = cct_analyzer._get_ocd_patterns()
            print(f"✅ Padrões OCD carregados: {len(ocd_patterns)} OCDs configurados")
            
            # Listar OCDs suportados
            print(f"📋 OCDs suportados: {', '.join(ocd_patterns.keys())}")
            
            return True
            
        except ImportError as e:
            print(f"❌ Erro ao importar CCTAnalyzerIntegrado: {e}")
            return False
        except Exception as e:
            print(f"❌ Erro ao instanciar CCTAnalyzerIntegrado: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao importar AnalisadorRequerimentos: {e}")
        return False

def criar_cct_exemplo():
    """Cria um arquivo CCT de exemplo para teste."""
    print("\n🔧 Criando arquivo CCT de exemplo...")
    
    # Criar pasta de exemplo
    pasta_exemplo = Path("downloads/REQ_TESTE_CCT")
    pasta_exemplo.mkdir(parents=True, exist_ok=True)
    
    # Criar um arquivo PDF de exemplo (vazio, apenas para estrutura)
    arquivo_cct = pasta_exemplo / "REQ_TESTE_CCT_Certificado de Conformidade Técnica - CCT.pdf"
    
    if not arquivo_cct.exists():
        # Criar arquivo vazio (em produção seria um PDF real)
        arquivo_cct.write_text("# Arquivo CCT de exemplo\n# Este seria um PDF real em produção\n")
        print(f"✅ Arquivo CCT de exemplo criado: {arquivo_cct}")
    else:
        print(f"ℹ️ Arquivo CCT já existe: {arquivo_cct}")
    
    return arquivo_cct

def testar_analise_cct_simulada():
    """Testa a análise de CCT com dados simulados."""
    print("\n🧪 Testando análise de CCT simulada...")
    
    try:
        from core.analyzer import AnalisadorRequerimentos
        
        analisador = AnalisadorRequerimentos()
        
        # Criar resultado simulado para teste
        resultado_teste = {
            "nome_arquivo": "teste_cct.pdf",
            "tipo": "CCT",
            "caminho": "downloads/teste/teste_cct.pdf",
            "timestamp": "2024-10-12T10:00:00",
            "status": "INCONCLUSIVO",
            "conformidades": [],
            "nao_conformidades": [],
            "observacoes": []
        }
        
        # Criar caminho simulado
        caminho_simulado = Path("downloads/teste/teste_cct.pdf")
        
        # Verificar se o método existe e pode ser chamado
        if hasattr(analisador, '_analisar_cct'):
            print("✅ Método _analisar_cct encontrado")
            
            # Nota: não executamos o método real porque precisa de um PDF válido
            print("ℹ️ Método testado estruturalmente (execução requer PDF real)")
            return True
        else:
            print("❌ Método _analisar_cct não encontrado")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de análise: {e}")
        traceback.print_exc()
        return False

def testar_configuracoes():
    """Testa se as configurações necessárias estão presentes."""
    print("\n📋 Testando configurações necessárias...")
    
    arquivos_config = [
        "utils/regras.json",
        "utils/equipamentos.json",
        "utils/requisitos.json", 
        "utils/normas.json",
        "utils/ocds.json"
    ]
    
    todos_presentes = True
    
    for arquivo in arquivos_config:
        if Path(arquivo).exists():
            print(f"✅ {arquivo}")
        else:
            print(f"❌ {arquivo} - FALTANDO")
            todos_presentes = False
    
    return todos_presentes

def main():
    """Função principal do teste."""
    print("="*70)
    print("🧪 TESTE DE INTEGRAÇÃO CCTAnalyzer")  
    print("="*70)
    
    testes = []
    
    # Teste 1: Configurações
    print("\n📋 Teste 1: Configurações")
    testes.append(("Configurações", testar_configuracoes()))
    
    # Teste 2: Integração
    print("\n🔗 Teste 2: Integração de Módulos")
    testes.append(("Integração", testar_integracao_cct()))
    
    # Teste 3: Análise estrutural
    print("\n⚙️ Teste 3: Estrutura de Análise")
    testes.append(("Estrutura", testar_analise_cct_simulada()))
    
    # Sumário
    print("\n" + "="*70)
    print("📊 RESULTADO DOS TESTES")
    print("="*70)
    
    testes_passaram = 0
    for nome, passou in testes:
        status = "✅ PASSOU" if passou else "❌ FALHOU"
        print(f"{nome:20} - {status}")
        if passou:
            testes_passaram += 1
    
    print("-" * 70)
    
    if testes_passaram == len(testes):
        print("🎉 Todos os testes passaram!")
        print("\n💡 Próximos passos:")
        print("1. Teste com um arquivo CCT real usando 'python main.py'")
        print("2. Verifique os logs durante a análise")
        print("3. Examine o relatório gerado")
    else:
        print(f"⚠️ {testes_passaram}/{len(testes)} testes passaram")
        print("\n🔧 Ações recomendadas:")
        print("1. Verifique se tbn_troller.py está no diretório correto")
        print("2. Certifique-se de que os arquivos JSON estão presentes")
        print("3. Verifique as dependências (PyMuPDF, etc.)")
    
    return testes_passaram == len(testes)

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)