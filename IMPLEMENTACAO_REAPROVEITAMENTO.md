# 📋 Implementação: Automação de Reaproveitamento de Número de Homologação

## Resumo

Implementada automação completa do fluxo de verificação e alteração automática de números de homologação no Certifica, conforme especificado nas orientações gerenciais.

## Arquivos Criados/Modificados

### 1. **Novo Arquivo: `core/homologacao_reaproveitamento.py`**

Módulo dedicado ao gerenciamento de reaproveitamento de números de homologação.

**Classes:**
- `GerenciadorReaproveitamentoHomologacao`: Classe principal com métodos estáticos para gerenciar toda a lógica

**Métodos Principais:**

| Método | Descrição |
|--------|-----------|
| `extrair_num_req_do_json()` | Lê o `num_req` do arquivo JSON do requerimento |
| `extrair_cod_homologacao_do_json()` | Lê o `cod_homologacao` do arquivo JSON |
| `num_req_corresponde_cod_homologacao()` | Verifica correspondência entre num_req e cod_homologacao |
| `listar_arquivos_reaproveitamento()` | Lista arquivos de reaproveitamento na pasta |
| `extrair_numeros_homologacao_de_arquivo()` | Extrai números (XXXXX-XX-XXXXX) usando PyMuPDF ou OCR |
| `buscar_novo_numero_homologacao()` | Busca exatamente um novo número (exclui o atual) |
| `alterar_numero_homologacao_no_certifica()` | Automatiza os passos 5.1-5.8 no Certifica |

**Função Principal:**
- `processar_reaproveitamento_homologacao_apos_download()`: Orquestra todo o fluxo de verificação e alteração

### 2. **Modificado: `core/downloader_certifica.py`**

**Adições:**
- Import da função `processar_reaproveitamento_homologacao_apos_download`
- Integração na função `processar_requerimento_certifica()` após download dos anexos

**Local de Integração:**
```python
# Após baixar_anexos_certifica(), antes de gerar_pdf_resumo_certifica()
processar_reaproveitamento_homologacao_apos_download(pasta, caminho_json, page)
```

### 3. **Modificado: `instrucoes/geral.md`**

Adicionada seção "Automação de Reaproveitamento de Homologação" com documentação detalhada do fluxo implementado.

## Fluxo de Execução

```
processar_requerimento_certifica()
  │
  ├─ Lê dados do requerimento
  ├─ Baixa anexos
  │
  ├─► NOVO: processar_reaproveitamento_homologacao_apos_download()
  │   │
  │   ├─ 1️⃣ Extrai num_req e cod_homologacao do JSON
  │   ├─ 2️⃣ Verifica correspondência (num_req = início de cod_homologacao?)
  │   │  └─ NÃO → Encerra (nenhuma ação necessária)
  │   │  └─ SIM → Continua
  │   ├─ 3️⃣ Lista arquivos de reaproveitamento na pasta
  │   ├─ 4️⃣ Extrai números (XXXXX-XX-XXXXX) com PyMuPDF ou OCR
  │   ├─ 5️⃣ Valida quantidade de números encontrados
  │   │  └─ Zero → Encerra (ℹ️ Nenhum novo número)
  │   │  └─ Um → Altera automaticamente no Certifica ✅
  │   │  └─ >Um → Encerra com erro (❌ Múltiplos encontrados)
  │   │
  │   └─ SE encontrado exatamente um:
  │       ├─ 5.1 Abre "Caixa Geral" do Certifica
  │       ├─ 5.2 Clica em "Filtrar"
  │       ├─ 5.3 Preenche "Número do Requerimento"
  │       ├─ 5.4 Clica "Pesquisar"
  │       ├─ 5.5-5.6 Clica no link do requerimento encontrado
  │       ├─ 5.7 Na aba Fabricante, clica "Alterar Número de Homologação"
  │       └─ 5.8 Preenche campo com novo número e clica "Confirma"
  │
  ├─ Gera PDF do Resumo
  └─ Marca requerimento como concluído/erro
```

## Padrões Utilizados

### Padrão de Número de Homologação
```regex
\b([A-Z0-9]{5}-[A-Z0-9]{2}-[A-Z0-9]{5})\b
```
- 5 caracteres alfanuméricos
- Hífen
- 2 caracteres alfanuméricos  
- Hífen
- 5 caracteres alfanuméricos

Exemplos: `ABCDE-FG-HIJLM`, `12345-AB-67890`

### Correspondência num_req ↔ cod_homologacao
```
num_req:        ABCDE/FG
cod_homologacao: ABCDE-FG-HIJLM
                 └─ Corresponde aos dígitos iniciais
```

## Tratamento de OCR

A extração de números suporta dois modos:

1. **PyMuPDF** (preferencial): Extrai texto diretamente do PDF
2. **OCR (Tesseract)**: Fallback quando o PDF é uma imagem/digitalizado

Implementado em `extrair_numeros_homologacao_de_arquivo()` com tratamento automático de fallback.

## Logging

Todas as operações registram logs informativos:
- 🔍 Verificação iniciada
- 📋 Dados extraídos (num_req, cod_homologacao)
- 📄 Arquivos encontrados
- 💾 Números extraídos
- 🔄 Passos de alteração no Certifica
- ✅ Sucesso
- ❌ Erros com descrição

## Conformidade com Orientações

✅ Todos os imports no cabeçalho  
✅ Sem código não utilizado  
✅ Funções comentadas e documentadas  
✅ Uso de log_info (não print)  
✅ DRY - código reutilizável em classe  
✅ Mantém funcionalidades existentes intactas  
✅ Novo arquivo bem estruturado  
✅ Documentação em geral.md  

## Testes Realizados

- ✅ Verificação de sintaxe Python
- ✅ Teste de importação de módulos
- ✅ Teste de correspondência num_req ↔ cod_homologacao
- ✅ Teste de padrão regex de números de homologação
- ✅ Integração com downloader_certifica.py

## Dependências

- `pymupdf`: Para extração de texto de PDFs (já utilizado no projeto)
- `pytesseract`: Para OCR (já disponível no projeto)
- `playwright`: Para automação do Certifica (já utilizado)

Todas as dependências já estavam presentes no projeto.

## Próximos Passos (se necessário)

1. Testes em ambiente com arquivos PDF reais de reaproveitamento
2. Validação de seletores do Certifica (podem variar conforme versão)
3. Ajuste de timeouts se necessário
4. Monitoria de logs em produção
