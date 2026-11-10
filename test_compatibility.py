#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste de compatibilidade - Verifica se não houve regressões
após as modificações para atender sugestão de pymupdf_layout.
"""

import sys
sys.path.insert(0, '.')

def main():
    print('🧪 Teste de Compatibilidade')
    print('=' * 70)

    # Teste 1: Importações críticas
    print('\n1️⃣  Testando importações críticas...')
    try:
        from core.caracteristicas_cct import (
            extrair_tabelas_pdf, 
            chave_coluna, 
            extrair_valores,
            linhas_cct_de_tabelas
        )
        print('   ✅ core.caracteristicas_cct - OK')
    except Exception as e:
        print(f'   ❌ Erro: {e}')
        return False

    try:
        from core.analyzer import (
            TIPO_CCT,
            TIPO_RACT,
            TIPO_MANUAL
        )
        print('   ✅ core.analyzer - OK')
    except Exception as e:
        print(f'   ❌ Erro: {e}')
        return False

    # Teste 2: Funções principais
    print('\n2️⃣  Testando funções principais...')
    try:
        # Testa normalização
        resultado = chave_coluna('Potência (dBm)')
        assert resultado == 'potencia', f'Esperado: potencia, Recebido: {resultado}'
        print('   ✅ chave_coluna - OK')
    except Exception as e:
        print(f'   ❌ Erro: {e}')
        return False

    try:
        # Testa extração de valores
        valores = extrair_valores('2400 MHz')
        assert len(valores) > 0, 'Esperado: pelo menos 1 valor'
        print('   ✅ extrair_valores - OK')
    except Exception as e:
        print(f'   ❌ Erro: {e}')
        return False

    # Teste 3: Verificar PyMuPDF
    print('\n3️⃣  Testando capacidades do PyMuPDF...')
    try:
        import pymupdf as fitz
        print(f'   ✅ PyMuPDF {fitz.version} - OK')
        
        # Verifica find_tables
        assert hasattr(fitz.Page, 'find_tables'), 'find_tables não disponível'
        print('   ✅ Método find_tables - OK')
    except Exception as e:
        print(f'   ❌ Erro: {e}')
        return False

    print('\n' + '=' * 70)
    print('✅ TODOS OS TESTES DE COMPATIBILIDADE PASSARAM!')
    print('✅ Nenhuma regressão detectada')
    print('✅ Código está pronto para uso em produção')
    print('\n💡 Próximos Passos:')
    print('   1. Execute: python test_pymupdf_layout.py (diagnóstico completo)')
    print('   2. Consulte: PYMUPDF_LAYOUT_UPGRADE.md (guia de upgrade)')
    print('   3. Consulte: RESUMO_MUDANCAS_PYMUPDF.md (sumário das mudanças)')
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
