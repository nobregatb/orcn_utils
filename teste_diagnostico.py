"""
Teste diagnóstico para entender o problema com Ato 4083
"""
from core.validador_normativos import validar_citacoes_normativos

# Simulando o texto que tem Ato 4083 múltiplas vezes
texto = """
Conforme determinado por meio do Ato nº 4083, de 31 de julho de 2020, nos itens 6.6.6.2 V e 6.6.8.1 VII.
Este equipamento segue o Ato 4083.
De acordo com Ato nº 4083 de 2020.
O Ato 4083 estabelece...
Sob o Ato 4083, de 31 de julho de 2020.
"""

exigencias, detalhes = validar_citacoes_normativos(texto)

print("Resultado da validação:")
print(f"Número de exigências: {len(exigencias)}")
print(f"Número de detalhes: {len(detalhes)}")
print()
print("Exigências encontradas:")
for i, ex in enumerate(exigencias, 1):
    print(f"{i}. {ex[:80]}...")
print()
print("Detalhes:")
for num, nome in detalhes:
    print(f"  - {num}: {nome}")
