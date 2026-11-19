"""
Teste de validação com o texto exemplo
"""
import sys
sys.path.insert(0, r"C:\Users\tbnobrega\Desktop\orcn_utils")

from core.validador_normativos import validar_citacoes_normativos, consolidar_exigencias_normativos

texto_exemplo = """
Ato Nº 3151/2020, Ato Nº 2105/2025, 3GPP TS 51.010-1 V6.5.0 (11-2005), 
ETSI TS 134 121-1 V9.4.0 (2011-03), ETSI TS 134 121-1 V9.1.0 (2010-07), 
3GPP TS 36.521-1 V17.6.1 (2023-07), 3GPP TS 36.523-1, ETSI TS 102 514 e 
RFC 8200, Ato Nº 7971/2023, Ato Nº 1120/2018,
Resolução Nº 772, Resolução Nº 773, 
Ato Nº 16539/2023 e Ato Nº 915/2024
"""

print("=" * 70)
print("TESTE: Validação de Normativos")
print("=" * 70)
print(f"\nTexto teste:\n{texto_exemplo}")
print("\n" + "=" * 70)

exigencias, detalhes = validar_citacoes_normativos(texto_exemplo)

print(f"\nExigências geradas: {len(exigencias)}")
for i, ex in enumerate(exigencias, 1):
    print(f"\n{i}. {ex}")

print(f"\n\nDetalhes dos normativos falhados:")
for num, nome in detalhes:
    print(f"  - {num}: {nome}")

if exigencias:
    print(f"\n" + "=" * 70)
    print("CONSOLIDAÇÃO")
    print("=" * 70)
    
    consolidada = consolidar_exigencias_normativos(exigencias)
    print(f"\nExigência consolidada:\n{consolidada}")
