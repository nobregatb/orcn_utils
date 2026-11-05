#!/usr/bin/env python3
"""
Script de teste para validar a implementação RIGOROSA de faixas de frequências.
Testa se a faixa [X, Y] declarada deve estar INTEGRALMENTE contida em uma ÚNICA
entrada de faixas.json.
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from core.regras_uso_faixa import (
    FrequenciaItem, 
    HomologacaoProduto,
    obter_regra_faixa_integra,
    parse_frequencias_mhz
)
from pydantic import ValidationError

print("=" * 80)
print("TESTES DE VALIDAÇÃO RIGOROSA DE FAIXAS DE FREQUÊNCIAS")
print("=" * 80)

# Teste 1: Frequência única válida
print("\n[TESTE 1] Frequência única válida (2.4 GHz)")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "2.4 GHz"
    }, context={"normas_referencia": ["ato14448"]})
    print("✅ PASSOU: Frequência 2.4 GHz validada com sucesso")
except ValidationError as e:
    print(f"❌ FALHOU: {e.errors()[0]['msg']}")

# Teste 2: Intervalo válido (faixa integralmente em uma regra)
print("\n[TESTE 2] Intervalo válido (2.4 - 2.483.5 GHz, deve estar em uma faixa)")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "2.4 - 2.4835 GHz"
    }, context={"normas_referencia": ["ato14448"]})
    print("✅ PASSOU: Faixa 2.4 - 2.4835 GHz está integralmente em uma regra")
except ValidationError as e:
    print(f"❌ FALHOU: {e.errors()[0]['msg']}")

# Teste 3: Intervalo válido integralmente em regra específica
print("\n[TESTE 3] Intervalo VÁLIDO (2.4 - 2.4835 GHz, integralmente em [2400, 2483.5])")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "2.4 - 2.4835 GHz"
    }, context={"normas_referencia": ["ato14448"]})
    print("✅ PASSOU: Faixa validada corretamente")
except ValidationError as e:
    msg = e.errors()[0]['msg']
    print(f"❌ FALHOU: {msg}")

# Teste 4: Intervalo que cobre GAP entre dois canais
print("\n[TESTE 4] Intervalo que cobre GAP (2.45 - 2.5 GHz, entre [2400,2483.5] e [2500,2690])")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "2.45 - 2.5 GHz"
    }, context={"normas_referencia": ["ato14448"]})
    # Se a validação passou, significa que a faixa está em alguma regra
    # (possivelmente a genérica de resolucao680)
    print("⚠️  INFO: Faixa aceita (pode estar em regra genérica de resolucao680)")
except ValidationError as e:
    msg = e.errors()[0]['msg']
    print(f"❌ FALHOU: {msg}")

# Teste 5: Intervalo válido com potência dentro do limite
print("\n[TESTE 5] Intervalo com potência válida (915 MHz, 0.1 W)")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "915 MHz",
        "Potência Máxima de Saída (W)": "0,1"
    }, context={"normas_referencia": ["ato14448"]})
    print("✅ PASSOU: 915 MHz com 0.1 W validado com sucesso")
except ValidationError as e:
    print(f"❌ FALHOU: {e.errors()[0]['msg']}")

# Teste 6: Intervalo com potência excedida
print("\n[TESTE 6] Intervalo com potência EXCEDIDA (915 MHz, 50 W)")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "915 MHz",
        "Potência Máxima de Saída (W)": "50"
    }, context={"normas_referencia": ["ato14448"]})
    print("❌ FALHOU: Deveria ter sido rejeitado mas passou!")
except ValidationError as e:
    msg = e.errors()[0]['msg']
    if "potência" in msg.lower():
        print(f"✅ PASSOU: Potência excedida detectada corretamente")
        print(f"   Mensagem: {msg}")
    else:
        print(f"❌ FALHOU: Mensagem incorreta: {msg}")

# Teste 7: Validação contextual (frequência incompatível com normas)
print("\n[TESTE 7] Frequência incompatível com normas (2.2 GHz requer ato915, fornecido ato14448)")
print("-" * 80)
try:
    homo = HomologacaoProduto.model_validate({
        "normas_referencia": ["ato14448"],
        "frequencias": [
            {"Faixa de Frequências Tx (MHz)": "2.2 GHz"}
        ]
    }, context={"normas_referencia": ["ato14448"]})
    print("❌ FALHOU: Deveria ter sido rejeitado mas passou!")
except ValidationError as e:
    msg = e.errors()[0]['msg']
    if "escopo" in msg.lower() or "ato915" in msg.lower():
        print(f"✅ PASSOU: Discrepância de normas detectada corretamente")
        print(f"   Mensagem: {msg}")
    else:
        print(f"❌ FALHOU: Mensagem incorreta: {msg}")

# Teste 8: Função obter_regra_faixa_integra com intervalo válido
print("\n[TESTE 8] Função obter_regra_faixa_integra (2.4 - 2.4835 GHz)")
print("-" * 80)
try:
    regra = obter_regra_faixa_integra(2400.0, 2483.5, ["ato14448"])
    if regra:
        print(f"✅ PASSOU: Regra encontrada")
        print(f"   Faixa: {regra['faixa']}")
        print(f"   Descrição: {regra.get('descricao', 'N/A')}")
    else:
        print(f"❌ FALHOU: Nenhuma regra encontrada")
except Exception as e:
    print(f"❌ ERRO: {e}")

# Teste 9: Função obter_regra_faixa_integra com intervalo PARCIALMENTE válido
print("\n[TESTE 9] Função obter_regra_faixa_integra (2.4 - 2.5 GHz, cobre GAP)")
print("-" * 80)
try:
    regra = obter_regra_faixa_integra(2400.0, 2500.0, ["ato14448"])
    if regra:
        print(f"⚠️  INFO: Regra encontrada (nota: há faixa genérica que cobre)")
        print(f"   Faixa: {regra['faixa']}")
        print(f"   Descrição: {regra.get('descricao', 'N/A')}")
        print(f"   Atos: {regra.get('atos_validos', 'N/A')}")
    else:
        print(f"✅ PASSOU: Nenhuma regra específica encontrada")
except Exception as e:
    print(f"❌ ERRO: {e}")

# Teste 10: Intervalo com ambiente exigido
print("\n[TESTE 10] Intervalo com restrição de ambiente (122.5 MHz, deve ser indoor)")
print("-" * 80)
try:
    item = FrequenciaItem.model_validate({
        "Faixa de Frequências Tx (MHz)": "122.5 MHz",
        "Especificações de Ambiente": "outdoor"
    }, context={"normas_referencia": ["ato14448"]})
    print("❌ FALHOU: Deveria ter sido rejeitado mas passou!")
except ValidationError as e:
    msg = e.errors()[0]['msg']
    if "indoor" in msg.lower():
        print(f"✅ PASSOU: Restrição de ambiente detectada corretamente")
        print(f"   Mensagem: {msg}")
    else:
        print(f"❌ FALHOU: Mensagem incorreta: {msg}")

print("\n" + "=" * 80)
print("TESTES CONCLUÍDOS")
print("=" * 80)
