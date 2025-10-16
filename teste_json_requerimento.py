# Teste dos novos métodos de análise de requerimento JSON
from pathlib import Path
from core.analyzer import CCTAnalyzerIntegrado

def main():
    print("=== Testando Novos Métodos ===")
    
    # Criar instância do analyzer
    utils_dir = Path("utils")
    analyzer = CCTAnalyzerIntegrado(utils_dir)
    
    # Verificar se os métodos existem
    print(f"Método _processar_dados_requerimento_json existe: {hasattr(analyzer, '_processar_dados_requerimento_json')}")
    print(f"Método _atualizar_ocds_json existe: {hasattr(analyzer, '_atualizar_ocds_json')}")
    
    # Testar atualização manual do ocds.json
    dados_ocd_teste = {
        "Nome": "Teste OCD Atualizado",
        "CNPJ": "04.192.889/0001-07",
        "Data do Certificado": "17/10/2025"
    }
    
    try:
        if hasattr(analyzer, '_atualizar_ocds_json'):
            analyzer._atualizar_ocds_json(dados_ocd_teste)
            print("✅ Método executado com sucesso!")
        else:
            print("❌ Método não encontrado")
    except Exception as e:
        print(f"❌ Erro na execução: {e}")

if __name__ == "__main__":
    main()