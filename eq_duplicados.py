import json
from collections import Counter

def identificar_nomes_duplicados(arquivo_json):
    """
    Identifica nomes duplicados em um arquivo JSON (case-insensitive)

    Args:
        arquivo_json: caminho do arquivo JSON ou string JSON
    """
    
    # Carregar o JSON
    try:
        # Tentar carregar como arquivo
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        # Se não for arquivo, tentar como string JSON
        dados = json.loads(arquivo_json)
    # Extrair nomes em lowercase
    nomes_lower = [item['nome'].lower() for item in dados]

    # Contar ocorrências
    contagem = Counter(nomes_lower)

    # Filtrar apenas os duplicados
    duplicados = {nome: count for nome, count in contagem.items() if count > 1}

    # Exibir resultados
    if duplicados:
        print("=" * 70)
        print("NOMES DUPLICADOS ENCONTRADOS:")
        print("=" * 70)

        for nome, quantidade in duplicados.items():
            print(f"\n📌 Nome: '{nome}'")
            print(f"   Ocorrências: {quantidade}")
            
            # Mostrar os itens originais (com capitalização original)
            print("   Itens encontrados:")
            for idx, item in enumerate(dados, 1):
                if item['nome'].lower() == nome:
                    print(f"   - #{idx}: {item['nome']} (ID: {item['id']}, Categoria: {item['categoria']})")

        print("\n" + "=" * 70)
        print(f"Total de nomes duplicados: {len(duplicados)}")
        print("=" * 70)
    else:
        print("✅ Nenhum nome duplicado encontrado!")
    
    return duplicados


# Exemplo de uso com string JSON
json_string = '''[
  {
    "escopo": "mosaico",
    "id": "EQ093",
    "nome": "Objetivo",
    "categoria": "Cat. 2"
  },
  {
    "escopo": "mosaico",
    "id": "EQ093",
    "nome": "Referências Normativas",
    "categoria": "Cat. 2"
  }
]'''

# Usar com string JSON:
#duplicados = identificar_nomes_duplicados(json_string)

# Usar com arquivo:
duplicados = identificar_nomes_duplicados('utils/equipamentos.json')

