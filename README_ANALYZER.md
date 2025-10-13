# Sistema de Análise ORCN - Guia de Uso

## 📋 Visão Geral

O sistema foi completamente reestruturado para implementar a análise automatizada de requerimentos conforme especificado no `geral.md`. Agora oferece:

- ✅ Análise individual ou em lote de requerimentos
- ✅ Interface interativa para seleção de escopo
- ✅ Geração automática de relatórios em LaTeX/PDF
- ✅ Saída estruturada em JSON
- ✅ Análise especializada por tipo de documento

## 🚀 Como Usar

### Execução Principal
```bash
python main.py
```
Escolha a opção "A" para análise de requerimentos.

### Demo Interativo
```bash
python demo.py
```
Oferece escolha entre sistema legado e novo sistema.

### Demo Apenas do Novo Sistema
```bash
python demo_analyzer.py
```
Demonstração focada apenas no novo sistema de análise.

## 📁 Estrutura Esperada

O sistema espera a seguinte estrutura de pastas:

```
orcn_utils/
├── downloads/              # Pasta principal dos requerimentos
│   ├── REQ_2024_001/      # Pasta de um requerimento
│   │   ├── documento_CCT.pdf
│   │   ├── documento_RACT.pdf
│   │   ├── manual_produto.pdf
│   │   └── outros_docs.pdf
│   ├── REQ_2024_002/      # Outro requerimento
│   └── ...
├── resultados_analise/     # Pasta de saída (criada automaticamente)
│   ├── resultados_analise_YYYYMMDD_HHMMSS.json
│   ├── relatorio_analise_YYYYMMDD_HHMMSS.tex
│   └── relatorio_analise_YYYYMMDD_HHMMSS.pdf
└── utils/                  # Arquivos de configuração
    ├── regras.json
    ├── equipamentos.json
    ├── requisitos.json
    ├── normas.json
    └── ocds.json
```

## 🔍 Processo de Análise

### 1. Seleção de Escopo
Ao executar a análise, o sistema pergunta:
- **Opção 1**: Analisar um requerimento específico
- **Opção 2**: Analisar todos os requerimentos (*)
- **Opção 3**: Cancelar

### 2. Análise de Documentos
Para cada requerimento, o sistema:
- Identifica todos os PDFs na pasta
- Classifica cada documento por tipo (CCT, RACT, Manual, etc.)
- Aplica regras específicas de análise por tipo
- Gera status de conformidade

### 3. Geração de Relatórios
Após a análise:
- **JSON**: Dados estruturados para processamento posterior
- **LaTeX**: Relatório formatado para compilação
- **PDF**: Relatório final (se LaTeX estiver instalado)

## 📊 Status de Análise

O sistema classifica cada documento com um dos seguintes status:

| Status | Descrição | Ação Recomendada |
|--------|-----------|------------------|
| ✅ **CONFORME** | Documento atende todos os requisitos | Nenhuma |
| ⚠️ **NÃO CONFORME** | Documento apresenta irregularidades | Revisar manualmente |
| ❓ **INCONCLUSIVO** | Análise requer revisão manual | Analisar manualmente |
| ❌ **ERRO** | Falha no processamento | Verificar arquivo |

## 🔧 Configuração

### Arquivos de Configuração
Os arquivos JSON em `utils/` controlam as regras de análise:
- `regras.json`: Regras de validação
- `equipamentos.json`: Catálogo de equipamentos
- `requisitos.json`: Mapeamento equipamento-norma
- `normas.json`: Especificações técnicas
- `ocds.json`: Códigos de classificação

### Dependências para PDF
Para gerar relatórios PDF, instale uma distribuição LaTeX:
- **Windows**: MiKTeX ou TeX Live
- **Linux**: `sudo apt install texlive-full`
- **macOS**: MacTeX

## 🎯 Exemplos de Uso

### Análise de Requerimento Específico
1. Execute `python main.py`
2. Escolha "A" (Análise)
3. Escolha "1" (Requerimento específico)
4. Selecione o requerimento desejado
5. Aguarde a análise e geração do relatório

### Análise em Lote
1. Execute `python main.py`
2. Escolha "A" (Análise)
3. Escolha "2" (Todos os requerimentos)
4. Aguarde o processamento completo

## � Solução de Problemas

### Erro: "Nenhum requerimento encontrado"
- Verifique se a pasta `downloads/` existe
- Certifique-se de que há subpastas com nomes de requerimentos
- Verifique se há arquivos PDF nas subpastas

### Erro: "pdflatex não encontrado"
- Instale uma distribuição LaTeX completa
- Verifique se `pdflatex` está no PATH do sistema
- O relatório LaTeX (.tex) ainda será gerado

### Erro de Configuração
- Verifique se os arquivos JSON em `utils/` são válidos
- Use um validador JSON online para verificar sintaxe
- Consulte os logs para detalhes específicos

### Dependências Opcionais para CCT
- **PyMuPDF**: Para extração de texto de PDFs (`pip install pymupdf`)
- **OCR Fallback**: Para PDFs digitalizados (`pip install pdf2image pytesseract`)
- **Tesseract**: Instalar binário do Tesseract OCR para OCR completo

### Erro: "CCTAnalyzer não disponível" 
- ✅ **RESOLVIDO**: O sistema agora usa `CCTAnalyzerIntegrado` sem dependências externas
- Não é mais necessário o arquivo `tbn_troller.py`

## 📝 Logs

O sistema gera logs detalhados através do módulo `core.log_print`:
- Informações de progresso
- Erros de processamento
- Detalhes de configuração

## 🔄 Migração do Sistema Legado

O sistema mantém compatibilidade com o código anterior:
- `demo.py` oferece ambas as opções
- Funções legadas permanecem funcionais
- Nova arquitetura é completamente independente

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs de erro
2. Consulte este README
3. Revise a documentação em `instrucoes/geral.md`