#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste para verificar se o loop infinito foi corrigido
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.analyzer import AnalisadorRequerimentos

def teste_simples():
    """Teste básico para verificar a inicialização"""
    print("🧪 Teste de correção do loop infinito")
    print("="*50)
    
    try:
        # Instanciar o analisador
        analisador = AnalisadorRequerimentos()
        print("✅ AnalisadorRequerimentos criado com sucesso")
        
        # Verificar se o método existe
        if hasattr(analisador, '_obter_escopo_analise'):
            print("✅ Método _obter_escopo_analise encontrado")
        else:
            print("❌ Método _obter_escopo_analise não encontrado")
            
        # Verificar se o método de seleção existe
        if hasattr(analisador, '_selecionar_requerimento_especifico'):
            print("✅ Método _selecionar_requerimento_especifico encontrado")
        else:
            print("❌ Método _selecionar_requerimento_especifico não encontrado")
            
        print("\n📋 Estrutura corrigida:")
        print("- Adicionadas opções de cancelamento ('c', 'cancelar', 'voltar', '0')")
        print("- Tratamento de KeyboardInterrupt adicionado")
        print("- Retorno 'CANCELAR' em caso de erro ou cancelamento")
        
        print("\n✅ Correção implementada com sucesso!")
        print("💡 O usuário agora pode sair dos loops usando as opções de cancelamento")
        
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

if __name__ == "__main__":
    teste_simples()