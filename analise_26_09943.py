#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.insert(0, 'C:\\Users\\tbnobrega\\Desktop\\orcn_utils')

# Limpar cache
for key in list(sys.modules.keys()):
    if 'validador' in key:
        del sys.modules[key]

from core.validador_normativos import validar_citacoes_normativos, _extrair_normativos_do_texto

# Carregar o texto do RACT
with open(r'C:\Users\TBNOBR~1\AppData\Local\Temp\ract_26_09943.txt', 'r', encoding='utf-8') as f:
    texto_ract = f.read()

# Executar validação
exigencias, detalhes = validar_citacoes_normativos(texto_ract)

print('=== VALIDAÇÃO DO RACT 26.09943 ===\n')
print(f'Total de exigências de normativos: {len(exigencias)}\n')

if exigencias:
    for i, exig in enumerate(exigencias, 1):
        print(f'Exigência {i}:')
        print(f'  {exig}')
        print()

# Mostrar detalhes
print('\n=== NORMATIVOS COM PROBLEMAS ===')
for norma_id, numero, nome in detalhes:
    print(f'\nID: {norma_id}')
    print(f'Normativo: {nome}')
    print(f'Descrição: Citação inadequada neste documento')

# Extrair e mostrar as localizações
print('\n\n=== LOCALIZAÇÕES NO DOCUMENTO ===')

normativos_encontrados = _extrair_normativos_do_texto(texto_ract)
print(f'Total de citações de normativos encontradas: {len(normativos_encontrados)}\n')

# Mapear números para IDs
mapa_id = {
    '1120': 'ato1120',
    '14448': 'ato14448',
    '17087': 'ato17087',
    '4083': 'ato4083',
    '680': 'resolucao680',
}

# Para cada normativo problemático, encontrar as localizações
for norma_id, numero, nome in detalhes:
    print(f'\n{nome}:')
    
    # Procurar por citações deste normativo
    citacoes = [n for n in normativos_encontrados if n[1] == numero]
    
    if citacoes:
        for tipo, num, texto_completo, posicao in citacoes:
            num_linha = texto_ract[:posicao].count('\n') + 1
            inicio = max(0, posicao - 80)
            fim = min(len(texto_ract), posicao + 150)
            contexto = texto_ract[inicio:fim].replace('\n', ' ').strip()
            
            print(f'  • Linha ~{num_linha}: "{texto_completo}"')
            print(f'    Contexto: ...{contexto}...')
    else:
        print(f'  • Nenhuma citação encontrada')
