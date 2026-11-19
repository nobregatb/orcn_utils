# 🚀 Guia de Uso: Automação de Reaproveitamento de Homologação

## Visão Geral

A automação de reaproveitamento de homologação funciona **automaticamente** durante o fluxo de download do Certifica, sem necessidade de ação manual do usuário.

## Quando É Acionada?

A automação é acionada **automaticamente** após o download dos anexos de um requerimento, seguindo esta sequência:

```
Download → Ajuste de Abas → Download de Anexos → ✅ AUTOMAÇÃO ACIONADA ← Gerar PDF Resumo
```

## Como Funciona?

A automação executa os seguintes passos de forma automática:

### 1️⃣ Verificação Inicial
- Lê o JSON do requerimento (ficheiro gerado automaticamente)
- Extrai `num_req` (ex: `25/06969`) e `cod_homologacao` (ex: `ABCDE-FG-HIJLM`)
- Verifica se correspondem (ex: `25/06` = `ABCDE-FG` ?)
- **Se NÃO correspondem**: Para aqui, nenhuma ação necessária

### 2️⃣ Busca de Arquivos
- Se correspondência **SIM**, busca arquivos nomeados com **"Reaproveitamento de Número de Homologação SCH"**
- **Se nenhum encontrado**: Para aqui, nenhuma ação necessária

### 3️⃣ Extração de Números
- Extrai números no formato `XXXXX-XX-XXXXX` dos arquivos encontrados
- Usa extração de texto (PyMuPDF) ou OCR (Tesseract) automaticamente
- Remove o número de homologação atual da lista (apenas novos números são considerados)

### 4️⃣ Validação
- **Nenhum número encontrado**: Para aqui, nada a fazer
- **Múltiplos números encontrados**: 🚨 Registra erro e para (esperava-se apenas um)
- **Exatamente um número**: ✅ Prossegue com alteração automática

### 5️⃣ Alteração no Certifica
Se encontrou exatamente um número:

1. Navega para "Caixa Geral" do Certifica
2. Abre o painel de "Filtrar"
3. Preenche "Número do Requerimento" com o valor extraído do JSON
4. Clica em "Pesquisar"
5. Localiza e clica no requerimento na tabela resultante
6. Aciona "Alterar Número de Homologação" na aba Fabricante
7. Preenche o campo com o novo número encontrado
8. Clica em "Confirma" para salvar a alteração

Tudo isso acontece **automaticamente** sem qualquer intervenção do usuário!

## Logs Informativos

Durante a execução, você verá logs como:

```
🔍 Verificando necessidade de reaproveitamento de homologação...
📋 Nº Requerimento: 25/06969
📋 Código Homologação: ABCDE-FG-HIJLM
✅ Nº Requerimento corresponde ao código de homologação. Continuando...
📄 Encontrado(s) 1 arquivo(s) de reaproveitamento.
  - [Reaproveitamento de Número de Homologação SCH][2024.12.19 15h30m45s][arquivo - Reaproveitamento].pdf: ['XXXXX-YY-ZZZZZ']
✅ Encontrado 1 novo número de homologação: XXXXX-YY-ZZZZZ

🚀 Alterando número de homologação no Certifica...
   De: ABCDE-FG-HIJLM
   Para: XXXXX-YY-ZZZZZ

5.1 Navegando para Caixa Geral...
✅ Caixa Geral aberta
5.2 Clicando em 'Filtrar'...
✅ Painel de filtro aberto
5.3 Preenchendo campo 'Número do Requerimento' com '25/06969'...
✅ Campo preenchido com '25/06969'
5.4 Clicando em 'Pesquisar'...
✅ Pesquisa executada
5.5-5.6 Procurando link do requerimento '25/06969' na tabela...
✅ Requerimento '25/06969' aberto
5.7 Localizando botão 'Alterar Número de Homologação' na aba Fabricante...
✅ Botão clicado, campo de alteração aberto
5.8 Preenchendo campo com novo número: XXXXX-YY-ZZZZZ...
✅ Campo preenchido com XXXXX-YY-ZZZZZ
✅ Número de homologação alterado com sucesso!
✅ Reaproveitamento de homologação processado com SUCESSO!
```

## Cenários Possíveis

### ✅ Sucesso
Quando exatamente um novo número é encontrado e alterado com sucesso no Certifica.
- **Log**: `✅ Reaproveitamento de homologação processado com SUCESSO!`
- **Ação**: Continua o fluxo normalmente (gera PDF)

### ℹ️ Nenhuma Ação Necessária
Quando nenhuma das condições para alteração é atendida:
- Nº Requerimento NÃO corresponde ao código de homologação
- Nenhum arquivo de reaproveitamento encontrado
- Nenhum número alternativo encontrado
- **Log**: `ℹ️ Nenhum novo número de homologação encontrado...`
- **Ação**: Continua o fluxo normalmente (gera PDF)

### ❌ Erro: Múltiplos Números
Quando mais de um número de homologação alternativo é encontrado.
- **Log**: `❌ ERRO: Encontrado(s) X número(s) de homologação diferente(s): ... Nenhum será processado`
- **Ação**: Continua o fluxo, mas registra no log que necessita revisão manual

### ⚠️ Falha Técnica
Quando há um erro durante a alteração no Certifica (timeout, elemento não encontrado, etc.).
- **Log**: `❌ Falha ao alterar número de homologação: ...`
- **Ação**: Registra o erro e continua o fluxo
- **Próximo passo**: O requerimento pode ser revisado manualmente

## Considerações Importantes

### 🔍 Verificação
1. **Sempre verifique o PDF gerado** para confirmar que a alteração foi aplicada
2. **Consulte os logs** em caso de dúvida sobre o que aconteceu
3. **Arquivos de reaproveitamento** devem estar nominados corretamente

### 🛠️ Manutenção
- **OCR**: Se o arquivo PDF for digitalizado, o sistema usa OCR (Tesseract) automaticamente
- **Timeouts**: Se a alteração falhar por timeout, pode estar lento - tente novamente
- **Seletores**: Se a interface do Certifica mudar, os seletores Playwright podem precisar ajuste

### 📋 Rastreamento
- Todos os passos são registrados em log com timestamps
- Os logs ajudam a identificar onde ocorreu um problema
- O JSON do requerimento contém os dados usados pela automação

## Troubleshooting

### "ERRO: Encontrado(s) X número(s) de homologação diferente(s)"

**Causa**: Múltiplos números de homologação foram encontrados nos arquivos de reaproveitamento.

**Solução**: 
1. Verifique manualmente os arquivos PDF de reaproveitamento
2. Determine qual é o número correto
3. Aplique a alteração manualmente no Certifica
4. Ou remova os números extras dos arquivos se forem duplicatas

### "Falha ao alterar número de homologação: TimeoutError"

**Causa**: Timeout esperando elemento aparecer.

**Solução**:
1. Verifique conectividade com o Certifica
2. Tente novamente (às vezes é apenas lentidão)
3. Se persistir, aplique manualmente

### Campo não preenchido corretamente

**Causa**: O locator não encontrou o campo esperado (interface mudou).

**Solução**:
1. Verifique a interface atual do Certifica
2. Informe ao desenvolvedor para ajustar os seletores
3. Aplique manualmente enquanto aguarda correção

## Próximas Melhorias (Futuro)

- [ ] Adicionar suporte a mais formatos de PDF
- [ ] Melhorar robustez dos seletores Playwright
- [ ] Adicionar validação de sucesso pós-alteração
- [ ] Integrar com sistema de notificações
- [ ] Dashboard com histórico de alterações

## Contato

Para problemas, sugestões ou dúvidas:
- Consulte os **logs detalhados** gerados durante a execução
- Revise o arquivo [IMPLEMENTACAO_REAPROVEITAMENTO.md](IMPLEMENTACAO_REAPROVEITAMENTO.md) para detalhes técnicos
- Consulte o arquivo [instrucoes/geral.md](instrucoes/geral.md) para documentação geral
