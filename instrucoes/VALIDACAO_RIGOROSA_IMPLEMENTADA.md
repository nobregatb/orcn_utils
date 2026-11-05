# ✅ Validação Rigorosa de Faixas de Frequências - IMPLEMENTADA

## Resumo da Mudança

A validação de faixas de frequências foi alterada para ser **RIGOROSA**:

### ❌ Comportamento Anterior (Permissivo)
```
Requerimento: "Faixa de Frequências Tx (MHz)": "2.4 - 2.5 GHz"
Extrai: [2400.0, 2500.0]

Validação ANTERIOR:
  ✓ Valida 2400 separadamente
  ✓ Valida 2500 separadamente
  ✓ USA APENAS A PRIMEIRA REGRA ENCONTRADA
  → RESULTADO: ✅ PASSA (permissivo demais)
```

### ✅ Comportamento Atual (Rigoroso)
```
Requerimento: "Faixa de Frequências Tx (MHz)": "2.4 - 2.5 GHz"
Extrai: [2400.0, 2500.0]

Validação ATUAL:
  ✓ Verifica se [2400.0, 2500.0] está INTEGRALMENTE contida em UMA ÚNICA regra
  ✓ Se a regra foi encontrada, valida ambiente/tecnologia/potência contra ela
  → RESULTADO: ✅ PASSA se [2400, 2500] ⊂ UMA ÚNICA faixa regulatória
            ❌ FALHA se NENHUMA faixa contém integralmente [2400, 2500]
```

---

## Mudanças Implementadas

### 1. Nova Função: `obter_regra_faixa_integra()`

**Localização:** `core/regras_uso_faixa.py`, linhas ~100-135

```python
def obter_regra_faixa_integra(freq_min: float, freq_max: float, normas=None) -> Optional[dict]:
    """Retorna a regra que contém INTEGRALMENTE a faixa [freq_min, freq_max].
    
    VALIDAÇÃO RIGOROSA: A faixa declarada deve estar completamente contida em uma ÚNICA
    entrada de faixas.json (inclusive as bordas).
    
    Returns:
        dict: A regra que contém integralmente a faixa, ou None se nenhuma regra aplica.
    """
```

**Lógica:**
1. Encontra todas as regras onde `regra["faixa"][0] <= freq_min` E `freq_max <= regra["faixa"][1]`
2. Se normas foram informadas, filtra apenas regras compatíveis
3. Se múltiplas regras cobrem a faixa, retorna a **MENOS RESTRITIVA**
4. Retorna `None` se nenhuma regra cobre integralmente a faixa

**Exemplos:**
```python
# ✅ ENCONTRA REGRA - Faixa integralmente em [2400, 2483.5]
obter_regra_faixa_integra(2400.0, 2483.5, ["ato14448"])
→ Retorna regra com faixa [2400, 2483.5]

# ❌ NÃO ENCONTRA - Faixa cobre GAP entre [2400, 2483.5] e [2500, 2690]
obter_regra_faixa_integra(2400.0, 2500.0, ["ato14448"])
→ Retorna None (a menos que exista regra genérica que cubra)

# ✅ ENCONTRA - Faixa em [960, 100000000] (genérica de resolucao680)
obter_regra_faixa_integra(2400.0, 2500.0, ["resolucao680"])
→ Retorna regra genérica
```

### 2. Modificação: `FrequenciaItem.validar_regras_e_potencias()`

**Localização:** `core/regras_uso_faixa.py`, linhas ~137-207

**Mudança chave:**
```python
# VALIDAÇÃO RIGOROSA: A faixa integralmente deve estar em uma única entrada de faixas.json
if len(frequencias) == 2:
    # Faixa com intervalo: [min, max]
    freq_min, freq_max = frequencias[0], frequencias[1]
    regra_encontrada = obter_regra_faixa_integra(freq_min, freq_max, normas_contexto)
    if regra_encontrada is None:
        raise ValueError(
            f"VIOLAÇÃO CRÍTICA: A faixa de frequências '{fmt_num(freq_min)} - {fmt_num(freq_max)} MHz' "
            f"não está integralmente contemplada em uma única entrada das regras regulatórias."
        )
else:
    # Frequência única - comportamento igual ao anterior
    freq = frequencias[0]
    regra_encontrada = obter_regra_frequencia(freq, normas_contexto)
    if regra_encontrada is None:
        raise ValueError(...)
```

---

## Exemplos de Comportamento

### ✅ Exemplo 1: Faixa Válida (WiFi)
```json
{
  "Faixa de Frequências Tx (MHz)": "2.4 - 2.4835 GHz",
  "Tecnologia": "WiFi",
  "Potência Máxima de Saída (W)": "0.1"
}
```

**Processamento:**
```
1. Parse: [2400.0, 2483.5]
2. obter_regra_faixa_integra(2400.0, 2483.5, ["ato14448"])
   → Encontra regra com faixa [2400, 2483.5] em ato14448
3. Validações cascata (ambiente, tecnologia, potência)
4. ✅ RESULTADO: CONFORME
```

### ✅ Exemplo 2: Frequência Única
```json
{
  "Faixa de Frequências Tx (MHz)": "915 MHz",
  "Potência Máxima de Saída (W)": "1"
}
```

**Processamento:**
```
1. Parse: [915.0]
2. len(frequencias) == 1 → usa obter_regra_frequencia()
3. Valida contra a regra encontrada
4. ✅ RESULTADO: CONFORME
```

### ❌ Exemplo 3: Faixa que Cobre GAP (Rejeitada se Nenhuma Regra)
```json
{
  "Faixa de Frequências Tx (MHz)": "2.45 - 2.5 GHz"
}
```

**Processamento:**
```
1. Parse: [2450.0, 2500.0]
2. obter_regra_faixa_integra(2450.0, 2500.0, ["ato14448"])
   → Não encontra regra específica de ato14448
   → CAN encontra regra genérica [960, 100000000] de resolucao680
3. Como não há regra de ato14448 que cubra:
   ❌ RESULTADO: NÃO CONFORME (depende do contexto normativo)
```

---

## Casos de Teste Cobertos

| # | Caso | Entrada | Resultado | Motivo |
|---|------|---------|-----------|--------|
| 1 | ✅ Freq única válida | "2.4 GHz" | CONFORME | Frequência em faixa |
| 2 | ✅ Faixa integralmente válida | "2.4 - 2.4835 GHz" | CONFORME | [2400, 2483.5] ⊂ regra |
| 3 | ⚠️ Faixa em regra genérica | "2.45 - 2.5 GHz" | CONFORME* | Capa por [960, 100M] |
| 4 | ✅ Potência OK | "915 MHz, 0.1W" | CONFORME | Dentro limite |
| 5 | ❌ Potência excedida | "915 MHz, 50W" | NÃO CONFORME | 46.99 dBm > 30 dBm |
| 6 | ❌ Freq fora de faixa | "10 GHz" | NÃO CONFORME | Nenhuma regra |

*Depende de qual norma é primária no contexto

---

## Ficheiro Modificado

**`core/regras_uso_faixa.py`**
- Adicionada função `obter_regra_faixa_integra()` (~35 linhas)
- Modificado validador `FrequenciaItem.validar_regras_e_potencias()` (~70 linhas)
  - Nova lógica: Se 2 frequências (intervalo), usa `obter_regra_faixa_integra()`
  - Se 1 frequência (ponto), usa `obter_regra_frequencia()` (comportamento anterior)
- Resto do código inalterado

---

## Impacto

### ✅ Benefícios
1. **Conformidade Regulatória**: Garante que faixas declaradas estão em regras específicas
2. **Precisão**: Detecta quando uma faixa atravessa múltiplas regras
3. **Rastreabilidade**: Cada faixa é mapeada a uma regra específica
4. **Flexibilidade**: Ainda aceita regras genéricas se forem as primárias

### ⚠️ Considerações
1. **Faixas Genéricas**: Regras muito amplas (ex: [960, 100M]) podem mascarar problemas
2. **Bordas Inclusivas**: Os limites são inclusivos (`<=` e `>=`)
3. **Contexto de Normas**: O filtro de normas é aplicado APÓS buscar faixas integras
4. **Compatibilidade**: Compatível com dados históricos se bem estruturados

---

## Script de Teste

Um script de teste completo foi criado em:
```
test_validacao_rigorosa.py
```

**Execução:**
```bash
python test_validacao_rigorosa.py
```

**Cobertura:**
- 10 testes cobrindo todos os cenários principais
- Validação de frequências únicas e intervalos
- Testes de potência
- Testes de contexto normativo
- Testes da nova função `obter_regra_faixa_integra()`

---

## Referência de Código

### Código Antigo (Permissivo)
```python
# Validar cada frequência separadamente
regras_encontradas = [
    obter_regra_frequencia(freq, normas_contexto) for freq in frequencias
]
for freq, regra in zip(frequencias, regras_encontradas):
    if regra is None:
        raise ValueError(...)

# USA APENAS A PRIMEIRA REGRA
regra_encontrada = regras_encontradas[0]
```

### Código Novo (Rigoroso)
```python
# Para intervalos: verificar integridade
if len(frequencias) == 2:
    freq_min, freq_max = frequencias[0], frequencias[1]
    regra_encontrada = obter_regra_faixa_integra(
        freq_min, freq_max, normas_contexto
    )
    if regra_encontrada is None:
        raise ValueError(
            f"A faixa '{freq_min} - {freq_max} MHz' "
            f"não está integralmente contemplada..."
        )
else:
    # Para frequência única: comportamento igual
    regra_encontrada = obter_regra_frequencia(freq, normas_contexto)
    if regra_encontrada is None:
        raise ValueError(...)
```

---

## Próximos Passos (Opcionais)

1. **Refinamento de Regras**: Se houver faixas genéricas indesejadas, considere:
   - Dividir faixas genéricas em regras mais específicas
   - Adicionar marcador de "fallback" para distinguir regras genéricas

2. **Documentação**: Atualizar documentação de homologação para referenciar a nova validação

3. **Testes Integrados**: Integrar script de teste no CI/CD

4. **Feedback**: Coletar feedback de usuários sobre faixas específicas que devem ser rejeitadas

---

## Conclusão

A validação **RIGOROSA** agora garante que toda faixa declarada no requerimento [X, Y] 
está **INTEGRALMENTE** contida em uma **ÚNICA** entrada de `faixas.json`, fornecendo
maior conformidade regulatória e rastreabilidade.
