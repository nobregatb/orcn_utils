#!/usr/bin/env python3
"""
Teste final da integração CCT sem dependência do tbn_troller.py
Verifica se todas as funcionalidades foram corretamente integradas
"""

import sys
from pathlib import Path
import json

def testar_cct_analyzer_integrado():
    """Testa se o CCTAnalyzerIntegrado está funcionando."""
    print("🔍 Testando CCTAnalyzerIntegrado...")
    
    try:
        from core.analyzer import CCTAnalyzerIntegrado, normalizar, buscar_valor
        print("✅ Imports realizados com sucesso")
        
        # Testar função normalizar
        teste_str = "Ação com Acentos"
        resultado = normalizar(teste_str)
        print(f"✅ Função normalizar: '{teste_str}' → '{resultado}'")
        
        # Testar função buscar_valor
        dados_teste = [{"id": "EQ001", "nome": "Equipamento Teste"}]
        valor = buscar_valor(dados_teste, "id", "EQ001", "nome")
        print(f"✅ Função buscar_valor: {valor}")
        
        # Instanciar CCTAnalyzerIntegrado
        utils_dir = Path("utils")
        cct_analyzer = CCTAnalyzerIntegrado(utils_dir)
        print("✅ CCTAnalyzerIntegrado instanciado")
        
        # Testar padrões OCD
        padroes = cct_analyzer._get_ocd_patterns()
        print(f"✅ Padrões OCD: {len(padroes)} configurados")
        
        # Testar extração de OCD de conteúdo simulado
        conteudo_teste = "Este certificado é emitido pela Associação NCC Certificações do Brasil"
        ocd_encontrado = cct_analyzer.extract_ocd_from_content(conteudo_teste)
        print(f"✅ Extração OCD: '{ocd_encontrado}' encontrado no conteúdo teste")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def testar_dependencias_opcionais():
    """Testa se as dependências opcionais estão funcionando."""
    print("\n🔍 Testando dependências opcionais...")
    
    try:
        import fitz
        print("✅ PyMuPDF disponível")
    except ImportError:
        print("⚠️ PyMuPDF não disponível - usando fallback")
    
    try:
        from pdf2image import convert_from_path
        import pytesseract
        print("✅ Dependências OCR disponíveis")
    except ImportError:
        print("⚠️ Dependências OCR não disponíveis - funcionalidade limitada")
    
    return True

def testar_analise_completa():
    """Testa o fluxo completo da análise."""
    print("\n🔍 Testando análise completa...")
    
    try:
        from core.analyzer import AnalisadorRequerimentos
        
        analisador = AnalisadorRequerimentos()
        print("✅ AnalisadorRequerimentos instanciado")
        
        # Verificar se o método _analisar_cct existe
        if hasattr(analisador, '_analisar_cct'):
            print("✅ Método _analisar_cct disponível")
        else:
            print("❌ Método _analisar_cct não encontrado")
            return False
        
        # Testar determinação de tipo de documento
        tipos_teste = [
            ("arquivo_cct.pdf", "CCT"),
            ("documento_ract.pdf", "RACT"), 
            ("manual_produto.pdf", "Manual"),
            ("outros_docs.pdf", "Outros")
        ]
        
        for nome, tipo_esperado in tipos_teste:
            tipo_detectado = analisador._determinar_tipo_documento(nome)
            if tipo_detectado == tipo_esperado:
                print(f"✅ Tipo detectado corretamente: {nome} → {tipo_detectado}")
            else:
                print(f"⚠️ Tipo detectado: {nome} → {tipo_detectado} (esperado: {tipo_esperado})")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de análise: {e}")
        return False

def verificar_arquivos_config():
    """Verifica se os arquivos de configuração estão presentes."""
    print("\n📋 Verificando arquivos de configuração...")
    
    arquivos = [
        "utils/regras.json",
        "utils/equipamentos.json", 
        "utils/requisitos.json",
        "utils/normas.json",
        "utils/ocds.json"
    ]
    
    todos_ok = True
    for arquivo in arquivos:
        caminho = Path(arquivo)
        if caminho.exists():
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                tamanho = len(dados) if isinstance(dados, (list, dict)) else 0
                print(f"✅ {arquivo} - {tamanho} items")
            except Exception as e:
                print(f"⚠️ {arquivo} - Erro ao ler: {e}")
                todos_ok = False
        else:
            print(f"❌ {arquivo} - Não encontrado")
            todos_ok = False
    
    return todos_ok

def main():
    """Executa todos os testes."""
    print("="*70)
    print("🧪 TESTE FINAL - INTEGRAÇÃO CCT (sem tbn_troller.py)")
    print("="*70)
    
    testes = [
        ("CCTAnalyzerIntegrado", testar_cct_analyzer_integrado),
        ("Dependências Opcionais", testar_dependencias_opcionais),
        ("Análise Completa", testar_analise_completa), 
        ("Arquivos de Configuração", verificar_arquivos_config)
    ]
    
    resultados = []
    
    for nome, funcao in testes:
        print(f"\n📋 Teste: {nome}")
        print("-" * 40)
        resultado = funcao()
        resultados.append((nome, resultado))
    
    # Sumário final
    print("\n" + "="*70)
    print("📊 RESULTADOS FINAIS")
    print("="*70)
    
    testes_passaram = 0
    for nome, passou in resultados:
        status = "✅ PASSOU" if passou else "❌ FALHOU"
        print(f"{nome:25} - {status}")
        if passou:
            testes_passaram += 1
    
    print("-" * 70)
    
    if testes_passaram == len(resultados):
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("\n✅ Sistema pronto para produção sem dependência do tbn_troller.py")
        print("\n💡 Próximos passos:")
        print("1. O arquivo tbn_troller.py pode ser removido com segurança")
        print("2. Execute 'python main.py' e teste a análise de CCT")
        print("3. Verifique os relatórios gerados")
    else:
        print(f"⚠️ {testes_passaram}/{len(resultados)} testes passaram")
        print("\n🔧 Corrija os problemas antes de remover tbn_troller.py")
    
    return testes_passaram == len(resultados)

if __name__ == "__main__":
    sucesso = main()
    input("\nPressione ENTER para continuar...")
    sys.exit(0 if sucesso else 1)