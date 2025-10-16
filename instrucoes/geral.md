# ORCN - Automação de Download/Análise de codumentos do SCH
Este projeto automatiza o download de anexos de requerimentos do sistema SCH da ANATEL. Uma automação básica da análise também é esperada.

## Orientações gerais
- TODOS os import devem estar no cabeçalho dos arquivos .py. Nenhum import pode estar aninhado no meio do código.
- O arquivo const.py NÃO pode possuir funções, apenas constantes.
- Funções de uso geral, utilitárias, devem estar no aquivo core/utils.py
- Ignore todos os arquivos .py começados com tbn_* .
- Todo o código modificado deve ter sua funcionalidade comentada.

## 🔧 Funcionalidades

As funcionalidades da aplicação são:

### Download de arquivos

- ✅ Download automático de PDFs por categoria
- ✅ Nomenclatura padronizada dos arquivos
- ✅ Controle de timeout preventivo (28 minutos)
- ✅ Verificação de arquivos existentes (não redownload)
- ✅ Atualização automática da planilha Excel
- ✅ Navegação por múltiplas páginas (100 itens por página)

#### 📋 Categorias de PDFs

O sistema busca PDFs nas seguintes categorias:
- Outros
- ART
- Selo ANATEL
- Relatório de Avaliação da Conformidade - RACT
- Manual do Produto
- Certificado de Conformidade Técnica - CCT
- Contrato Social
- Fotos internas
- Relatório de Ensaio
- Fotos do produto

### Análise de requerimentos

O sistema de análise automatizada avalia todos os documentos de um requerimento e gera relatórios estruturados dos resultados.

#### 🔍 Processo de Análise

**1. Análise por Requerimento**
- Cada requerimento é analisado individualmente
- Todos os documentos da pasta do requerimento são processados
- Aplicação de roteiros específicos por tipo de documento
- Validação automática de conformidade técnica

**2. Tipos de Documentos Analisados**
- **CCT (Certificado de Conformidade Técnica)**: Validação de datas, equipamentos e conformidade
- **RACT (Relatório de Avaliação da Conformidade Técnica)**: Verificação de ensaios e normas
- **Manual do Produto**: Análise de especificações técnicas
- **Relatório de Ensaio**: Validação de testes e resultados
- **ART (Anotação de Responsabilidade Técnica)**: Verificação de responsáveis técnicos
- **Fotos do Produto**: Análise visual e conformidade
- **Contrato Social**: Validação de dados da empresa

#### 📊 Saídas do Sistema

**1. Arquivo JSON de Análise**
- Resultado estruturado da análise de cada requerimento
- Contém status de conformidade por documento
- Inclui detalhes de não conformidades encontradas
- Metadados de processamento e timestamps

**2. Relatório PDF Consolidado**
- Sumário executivo de todos os requerimentos analisados
- Estatísticas de conformidade por categoria
- Lista detalhada de não conformidades
- Recomendações de ações corretivas

#### ⚙️ Regras de Análise

O sistema utiliza arquivos de configuração JSON para definir:
- **`regras.json`**: Regras de negócio e validações
- **`equipamentos.json`**: Catálogo de equipamentos homologados
- **`requisitos.json`**: Mapeamento equipamento-norma
- **`normas.json`**: Especificações técnicas por norma
- **`ocds.json`**: Códigos OCDS para classificação

#### 🚨 Status de Análise

- ✅ **Conforme**: Documento atende todos os requisitos
- ⚠️ **Não Conforme**: Documento apresenta irregularidades
- ❓ **Inconclusivo**: Análise requer revisão manual
- ❌ **Erro**: Falha no processamento do documento

## 📁 Estrutura do Projeto

```
orcn_utils/
├── core/                    # Módulos principais
│   ├── analyzer.py         # Motor de análise de documentos
│   ├── downloader.py       # Sistema de download
│   ├── log_print.py        # Sistema de logging
│   └── menu.py             # Interface do usuário
├── utils/                   # Arquivos de configuração
│   ├── equipamentos.json   # Catálogo de equipamentos
│   ├── normas.json         # Especificações técnicas
│   ├── regras.json         # Regras de análise
│   ├── requisitos.json     # Mapeamento equipamento-norma
│   └── ocds.json           # Códigos de classificação
├── instrucoes/             # Documentação
│   └── geral.md            # Este arquivo
└── [scripts principais]    # Scripts de execução
```

## 🎯 Orientações gerais

- O sistema opera em dois modos principais: **Download** e **Análise**
- Todos os arquivos de configuração estão centralizados na pasta `utils/`
- Os logs são gerados automaticamente durante a execução
- O sistema possui proteções contra timeout e falhas de rede
- A nomenclatura de arquivos segue padrões específicos da ANATEL

## ⚡ Como Usar

### Execução Principal
```bash
python main.py
```

### Modo de Análise
```bash
python demo.py  # Para demonstração
```

## 🚀 Como Compilar o Executável
```bash
python build_exe.py
```

## 🔧 Configuração

### Arquivos de Configuração
Antes de executar, certifique-se de que os arquivos JSON na pasta `utils/` estão atualizados:
- Verifique se `equipamentos.json` contém todos os equipamentos necessários
- Confirme que `regras.json` possui as validações atualizadas
- Certifique-se de que `requisitos.json` mapeia corretamente equipamentos e normas

### Parâmetros do Sistema
- **Timeout**: 28 minutos por operação
- **Itens por página**: 100 requerimentos
- **Formato de saída**: PDF + JSON
- **Controle de duplicatas**: Automático