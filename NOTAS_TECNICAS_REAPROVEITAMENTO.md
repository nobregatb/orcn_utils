# 👨‍💻 Notas Técnicas: Implementação de Reaproveitamento de Homologação

## Estrutura do Código

### Arquivo Principal: `core/homologacao_reaproveitamento.py`

```python
class GerenciadorReaproveitamentoHomologacao:
    """Gerencia a automação de reaproveitamento de números de homologação."""
    
    PADRAO_HOMOLOGACAO = r"\b([A-Z0-9]{5}-[A-Z0-9]{2}-[A-Z0-9]{5})\b"
    
    @staticmethod
    def extrair_num_req_do_json(caminho_json: str) -> Optional[str]
    
    @staticmethod
    def extrair_cod_homologacao_do_json(caminho_json: str) -> Optional[str]
    
    @staticmethod
    def num_req_corresponde_cod_homologacao(num_req: str, cod_homologacao: str) -> bool
    
    @staticmethod
    def listar_arquivos_reaproveitamento(pasta_requerimento: str) -> List[str]
    
    @staticmethod
    def extrair_numeros_homologacao_de_arquivo(caminho_pdf: str) -> List[str]
    
    @staticmethod
    def buscar_novo_numero_homologacao(pasta_requerimento: str, cod_homologacao_atual: str) -> Optional[str]
    
    @staticmethod
    def alterar_numero_homologacao_no_certifica(page: Page, num_req: str, novo_numero_homologacao: str) -> bool


def processar_reaproveitamento_homologacao_apos_download(
    pasta_requerimento: str,
    caminho_json_requerimento: str,
    page: Page
) -> bool
```

## Fluxo de Dados

```
JSON do Requerimento
    ↓
Extrai: num_req (25/06969), cod_homologacao (ABCDE-FG-HIJLM)
    ↓
Verifica Correspondência (25/06 ↔ ABCDE-FG)?
    ├─ NÃO → Retorna False
    └─ SIM
        ↓
    Lista Arquivos "[Reaproveitamento...]"
        ├─ Nenhum → Retorna False
        └─ Encontrados
            ↓
        Extrai Números (XXXXX-XX-XXXXX)
        Tenta PyMuPDF → Fallback OCR
            ↓
        Valida Quantidade
        ├─ 0 → Retorna False
        ├─ >1 → Log erro, Retorna False
        └─ 1
            ↓
        Altera no Certifica (5.1 até 5.8)
            ↓
        Retorna True (sucesso) ou False (erro)
```

## Tratamento de PDF

### Extração Preferencial: PyMuPDF
```python
pdf = fitz.open(caminho_pdf)
texto = ""
for pagina in pdf:
    texto += pagina.get_text()
pdf.close()
```

### Fallback: OCR (Tesseract)
```python
texto = extract_pdf_content_from_ocr(Path(caminho_pdf))
```

**Decisão**: Tenta PyMuPDF primeiro (mais rápido). Se falhar ou retornar vazio, usa OCR.

## Seletores Playwright

### Busca de Elementos
Usa múltiplas estratégias para localizar elementos (case-insensitive e flexible):

```python
# Exemplo: Localizar campo "Número do Requerimento"
page.locator(
    "input[name*='Numero'][name*='Requerimento'], "
    "input[name*='numero'][name*='requerimento'], "
    "input[placeholder*='Requerimento'], "
    "textarea[name*='Numero'][name*='Requerimento']"
).first
```

**Estratégia**:
1. Localizadores baseados em atributos `name` (maiúsculas e minúsculas)
2. Localizadores baseados em `placeholder`
3. Diferentes tipos de elementos (`input`, `textarea`, `button`)
4. Uso de `.first` para garantir o primeiro resultado

## Padrão Regex

```regex
\b([A-Z0-9]{5}-[A-Z0-9]{2}-[A-Z0-9]{5})\b
```

**Componentes**:
- `\b`: Limite de palavra (início)
- `([A-Z0-9]{5})`: Exatamente 5 caracteres alfanuméricos
- `-`: Hífen literal
- `([A-Z0-9]{2})`: Exatamente 2 caracteres alfanuméricos
- `-`: Hífen literal
- `([A-Z0-9]{5})`: Exatamente 5 caracteres alfanuméricos
- `\b`: Limite de palavra (fim)

**Exemplos Válidos**:
- `ABCDE-FG-HIJLM`
- `12345-AB-67890`
- `AbCdE-Fg-HiJlM` (minúsculas também, convertidas para maiúsculas)

**Exemplos Inválidos**:
- `ABCDE-FGH-IJKLM` (segundo segmento com 3 caracteres)
- `ABCDE/FG/HIJLM` (barras em vez de hífens)
- `ABCDE-F-HIJLM` (segundo segmento com 1 caractere)

## Correspondência num_req ↔ cod_homologacao

```python
def num_req_corresponde_cod_homologacao(num_req: str, cod_homologacao: str) -> bool:
    # Exemplo:
    # num_req = "ABCDE/FG" → normalizado para "ABCDE-FG"
    # cod_homologacao = "ABCDE-FG-HIJLM" → primeiros 8 caracteres = "ABCDE-FG"
    # Resultado: True
```

**Lógica**:
1. Remove espaços de ambas as strings
2. Substitui `/` por `-` em num_req
3. Converte ambas para maiúsculas
4. Compara se num_req_normalizado == primeiros N caracteres de cod_homologacao
5. Onde N = comprimento de num_req_normalizado

## Integração com downloader_certifica.py

**Local de Chamada**:
```python
def processar_requerimento_certifica(page, requerimento, somente_anexos=False):
    # ... código anterior ...
    baixados, falhas = baixar_anexos_certifica(page, pasta)
    
    # ✅ AQUI: Automação de Reaproveitamento
    if not somente_anexos:
        caminho_json = os.path.join(pasta, f"{os.path.basename(pasta)[1:]}.json")
        processar_reaproveitamento_homologacao_apos_download(pasta, caminho_json, page)
    
    # ... código posterior (gerar PDF) ...
```

**Momento Estratégico**:
- ✅ Depois de: Baixar anexos (precisa dos arquivos de reaproveitamento)
- ✅ Antes de: Gerar PDF (a alteração é feita antes de salvar o resumo)
- ✅ Apenas quando: `not somente_anexos` (fluxo completo, não parcial)

## Logging e Debugging

### Estratégia de Log
```python
log_info("🔍 Verificando necessidade de reaproveitamento...")  # Início
log_info("📋 Nº Requerimento: {num_req}")                      # Dados extraídos
log_info("📄 Encontrado(s) X arquivo(s)...")                   # Busca
log_info("  - {arquivo}: {numeros}")                           # Detalhes
log_info("5.1 Navegando para Caixa Geral...")                  # Passos
log_info("✅ Caixa Geral aberta")                              # Confirmações
log_erro("Falha ao alterar número...")                         # Erros
```

### Símbolos Utilizados
- 🔍 Verificação/busca
- 📋 Dados/informações
- 📄 Arquivos
- 🔄 Processamento em andamento
- ✅ Sucesso/confirmação
- ❌ Erro crítico
- ℹ️ Informação/nenhuma ação
- ⚠️ Aviso
- 🚀 Início de operação

## Tratamento de Erros

### Try-Except Estratégico

```python
# Nível 1: Wrapper geral
try:
    # Lógica principal
except Exception as e:
    log_erro(f"Erro geral: {e}")
    return False

# Nível 2: Operações críticas
try:
    campo.wait_for(state="visible", timeout=CERTIFICA_TIMEOUT_PAGINA)
except Exception as e:
    log_erro(f"Elemento não encontrado: {e}")
    # Continua com estratégia alternativa ou retorna erro
```

### Timeouts
- `CERTIFICA_TIMEOUT_PAGINA = 3000000` (3000 segundos)
- `page.wait_for_timeout(1000)` (delays pequenos entre passos)
- `page.wait_for_load_state()` (aguarda navegação completa)

## Validação e Testes

### Testes Realizados
1. ✅ Sintaxe Python (py_compile)
2. ✅ Importação de módulos
3. ✅ Correspondência num_req ↔ cod_homologacao
4. ✅ Padrão regex de números
5. ✅ Integração com downloader_certifica.py

### Cenários para Teste Manual
1. PDF com texto válido (PyMuPDF)
2. PDF digitalizado (OCR necessário)
3. Nenhum arquivo de reaproveitamento
4. Um arquivo de reaproveitamento com um número
5. Um arquivo com múltiplos números
6. Múltiplos arquivos com números

## Conformidade com Projeto

✅ **Orientações Gerenciais**:
- Todos os imports no início
- Sem código não utilizado
- Código comentado
- Uso de log_info (não print)
- DRY (classe reutilizável)
- Mantém funcionalidades existentes

✅ **Padrões do Projeto**:
- Uso de `@staticmethod` para funções reutilizáveis
- Tipos hintados com Optional, List, str
- Docstrings detalhadas
- Tratamento de erro robusto

## Possíveis Extensões Futuras

1. **Cache de PDFs processados**: Evitar re-processar o mesmo PDF
2. **Webhook/Notificação**: Alertar quando alteração é feita
3. **Validação pós-alteração**: Confirmar que número foi alterado de verdade
4. **Suporte a múltiplos números**: Se necessário permitir múltiplos (com interface)
5. **API REST**: Permitir acionamento via API externa
6. **Dashboard**: Histórico de alterações realizadas
7. **Suporte a diferentes formatos**: Excel, Word, etc (além de PDF)

## Referências de Código

### Funções Externas Utilizadas
- `carregar_json_com_fallback()` (core/utils.py): Lê JSON com tratamento de erro
- `extract_pdf_content_from_ocr()` (core/utils.py): OCR com Tesseract
- `log_info()`, `log_erro()` (core/log_print.py): Logging padronizado
- `pymupdf as fitz`: Extração de PDF
- `playwright.sync_api.Page`: Automação do navegador

### Constantes Utilizadas
- `CERTIFICA_TIPO_ANEXO_REAPROVEITAMENTO`: Tipo de arquivo a buscar
- `CERTIFICA_TIMEOUT_PAGINA`: Timeout padrão em milissegundos
