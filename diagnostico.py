"""
Script para diagnosticar o problema com validação de normativos no requerimento
"""
import sys
import os
from pathlib import Path

# Adicionar ao path
sys.path.insert(0, r"C:\Users\tbnobrega\Desktop\orcn_utils")

from core.validador_normativos import _carregar_normas, _extrair_normativos_do_texto

# Carregar normas
normas = _carregar_normas()

print("=" * 70)
print("DIAGNÓSTICO: Normativos em normas.json")
print("=" * 70)

# Verificar se 4083 está em normas
if '4083' in normas:
    print(f"\n✓ Ato 4083 encontrado em normas.json")
    norma_4083 = normas['4083']
    print(f"  ID: {norma_4083.get('id', 'N/A')}")
    print(f"  Nome: {norma_4083.get('nome', 'N/A')}")
else:
    print(f"\n✗ Ato 4083 NÃO encontrado em normas.json")

# Verificar resoluções 772 e 773
print(f"\n✓ Resoluções 772 e 773:")
for num in ['772', '773']:
    if num in normas:
        norma = normas[num]
        print(f"  Resolução {num}: {norma.get('nome', 'N/A')[:50]}")
    else:
        print(f"  ✗ Resolução {num}: NÃO encontrada")

print(f"\nTotal de normativos em normas.json: {len(normas)}")

# Verificar padrões usados
print("\n" + "=" * 70)
print("TESTE: Extração de normativos do texto de exemplo")
print("=" * 70)

texto_exemplo = """
Ato Nº 3151/2020, Ato Nº 2105/2025, 3GPP TS 51.010-1 V6.5.0 (11-2005), 
ETSI TS 134 121-1 V9.4.0 (2011-03), ETSI TS 134 121-1 V9.1.0 (2010-07), 
3GPP TS 36.521-1 V17.6.1 (2023-07), 3GPP TS 36.523-1, ETSI TS 102 514 e 
RFC 8200, Ato Nº 7971/2023, Ato Nº 1120/2018, Resolução Nº 772, Resolução Nº 773, 
Ato Nº 16539/2023 e Ato Nº 915/2024
"""

normativos = _extrair_normativos_do_texto(texto_exemplo)

print(f"\nNormativos extraídos: {len(normativos)}")
for tipo, numero, texto_completo, posicao in normativos:
    print(f"  - {tipo} {numero}: '{texto_completo}'")

# Filtrar apenas normativos únicos
numeros_unicos = set(numero for _, numero, _, _ in normativos)
print(f"\nNúmeros únicos encontrados: {sorted(numeros_unicos)}")

# Verificar quais estão em normas.json
print(f"\nNormativos encontrados em normas.json:")
for num in sorted(numeros_unicos):
    if num in normas:
        print(f"  ✓ {num}: {normas[num].get('nome', 'N/A')[:50]}")
    else:
        print(f"  ✗ {num}: NÃO em normas.json")
