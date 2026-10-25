# ORCN - Automação de Download/Análise de codumentos do SCH
Este projeto automatiza o download de anexos de requerimentos do sistema SCH da ANATEL. Uma automação básica da análise também é esperada.

## Orientações gerais
- TODOS os import devem estar no cabeçalho dos arquivos .py. Nenhum import pode estar aninhado no meio do código.
- O arquivo const.py NÃO pode possuir funções, apenas constantes.
- Funções de uso geral, utilitárias, devem estar no aquivo core/utils.py
- Ignore todos os arquivos .py começados com tbn_* .
- Todo o código modificado deve ter sua funcionalidade comentada.
- NÃO use print, apenas log_info.
- DRY - códigos comuns TEM QUE ser reutilizados.
- Códigos comuns, devem estar no arquivo utils.py - Se for o caso, organizado em classes.
- NUNCA deixe código não utilizado (invocado ou chamado por/em outros trechos do código) após uma modificação.

## 🔧 Funcionalidades

As funcionalidades da aplicação são:

### Download de arquivos

- Ao escolher **Download**, selecione o sistema **SCH (S)** ou **Certifica(C)**.
- A opção **SCH (S)** mantém o fluxo de download atual. A opção **Certifica(C)** abre https://appsnet/Acesso/, aguarda o login do usuário (até a página exibir "Caixa de Entrada Analista") e pergunta o tipo de download (1. Retornos para estudo, 2. Requerimentos em análise, 3. Todos) e o escopo (1. Todos os requerimentos, 2. Um requerimento específico). Se o escopo for **um requerimento específico**, o script lê a lista do tipo escolhido, exibe os requerimentos numerados (com a opção "Cancelar e voltar") e, para o escolhido, apenas cria a pasta e baixa os anexos (respeitando e atualizando `download_status.json`), sem gravar o JSON, ajustar abas ou gerar o `ResumoCCT.pdf`. Para **todos**, segue o fluxo abaixo. Em seguida lê a lista de requerimentos do(s) tipo(s), cria/renomeia a pasta de cada um em `req_inbox` (como no SCH), abre o link do requerimento e grava `<AA.NNNNN>.json` com os blocos `requerimento`, `fabricante`, `solicitante`, `ocd`, `lab`, `produto`, `modelos`, `caracteristicas_tecnicas` e `certificado`. `caracteristicas_tecnicas.produtos` contém o produto principal, com as características antes salvas em `frequencias`, e os demais produtos. Em seguida ajusta os campos previstos nas abas, depois baixa, na mesma pasta, os anexos dos tipos do SCH mais "Registro de Ocorrências" e "Reaproveitamento de Número de Homologação SCH" (`CERTIFICA_TIPOS_ANEXO_BAIXAR`), nomeados `[tipo][aaaa.mm.dd HHhMMmSSs][arquivo - descrição].pdf`, ignorando os marcados "(DESATIVADO)". Por fim abre **Resumo**. Se `Portaria n° 2257` ainda não estiver visível no Resumo, recarrega a página sem usar o cache (equivalente a **Ctrl+F5**) e repete a verificação até o texto aparecer. Então clica em **Gerar PDF** e salva o arquivo na pasta do requerimento como `ResumoCCT.pdf`; se o nome já existir, usa `ResumoCCT(1).pdf`, `ResumoCCT(2).pdf` e assim por diante, sem sobrescrever arquivos existentes.
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
- Reaproveitamento de Número de Homologação SCH (Certifica)

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
- Havendo mais de um CCT ou RACT na pasta do requerimento, é analisado o documento que contém a data mais recente no texto do PDF (ou no OCR, quando necessário), aceitando `dd/mm/aaaa` e datas por extenso em português. Se as datas do conteúdo forem iguais ou não forem encontradas, prevalece a data mais recente no nome do arquivo; persistindo o empate, mantém-se o primeiro documento encontrado.
- Na lista de equipamentos do relatório de cada requerimento, os nomes são identificados sem aceitar palavras parciais; se o nome de um equipamento estiver inteiramente dentro do nome de outro mais específico, só é contado separadamente quando também ocorrer fora desse nome. Depois, os equipamentos são relacionados às famílias em `familias_equipamentos.json` pelo ID. Equipamentos com o mesmo ID são agrupados e exibidos uma única vez com o nome da família; quando não há família correspondente, o nome é obtido em `equipamentos.json`.
- As palavras-chave `reaproveitar`, `reaproveitando`, `reutilizar` e `reutilizando` também são buscadas e exibidas no relatório. Quando uma delas for encontrada, ou quando houver um anexo do tipo **Reaproveitamento de Número de Homologação SCH**, o relatório inclui **Alterar homologação** em vermelho e negrito logo após o item **OCD** do requerimento.
- A validação **Modelos** aparece antes de **Exigência**: quando todos os modelos do JSON são encontrados no CCT, exibe o item `Modelos: OK`; se algum não for encontrado, acrescenta às exigências o item **Informar nome(s) do(s) modelo(s) conforme CCT.**, seguido, entre parênteses, pelos nomes dos modelos não encontrados. Se o nome comercial inteiro de algum modelo for `-`, `N/A`, `NA` ou `Não aplicável`, acrescenta uma exigência para confirmar o valor encontrado ou corrigir o cadastro, exibindo cada nome comercial inválido entre aspas. A comparação ignora maiúsculas/minúsculas e aceita `Não aplicável` com ou sem acentos. O item **Exigência** aparece alinhado como item de lista. Quando há pendências, aparece em vermelho com uma lista numerada para cada ação e subitens com marcadores para informações ausentes; sem pendências, aparece em azul. Quando uma norma com status revogado(a) em `normas.json` é citada no RACT ou no CCT, inclui nas exigências um item com o nome cadastrado da norma; se aparecer nos dois documentos, inclui apenas uma vez. A validação **Normativos** é apresentada em uma tabela única com as colunas Norma, Observação e Status; o Status sempre exibe `RACT/CCT`, colorindo cada nome de acordo com a validação correspondente e mantendo a barra em preto; nomes em cinza (norma não aplicável àquele documento) aparecem também tachados. Quando há medição numérica em qualquer campo SAR no JSON do requerimento, o Ato nº 17865 aparece em azul para RACT e CCT. Para cada ocorrência no CCT de `ipv6`, `produto não acabado`, `vinculado` ou `vinculada`, verifica se a frase correspondente está em `produto` → `Especificações Adicionais` do JSON do requerimento.
- A captura das características técnicas mantém as linhas repetidas nas tabelas de origem, inclusive quando os dados estão distribuídos em mais de uma tabela com o mesmo cabeçalho. A validação identifica linhas repetidas dentro de cada produto e inclui em **Exigência** a orientação para remover todas as cópias, listando cada linha repetida com o total de ocorrências (`(xN)`). A comparação considera todas as colunas e ignora espaços; valores vazios e `-` não aparecem na linha exibida.
- A análise do CCT valida, quando informados no bloco `certificado` do JSON do requerimento, o **Número do Certificado** (comparação sensível a maiúsculas e minúsculas, ignorando espaços) e as **Data de Emissão do CCT** e **Data de Validade do Certificado** (comparação da data, aceitando formatos numéricos e por extenso em português). Cada valor não encontrado no CCT é indicado individualmente nas exigências.
- Todos os valores das características técnicas do JSON devem constar na(s) tabela(s) de características do CCT (módulo `core/caracteristicas_cct.py`). As tabelas são lidas pela geometria do PDF (PyMuPDF `find_tables`), replicando as células mescladas nas linhas/colunas cobertas e unindo tabelas continuadas em outra página. Cada célula (do CCT e do JSON) é tratada como um conjunto de valores, ignorando maiúsculas, acentos, unidades, separadores (`;`, `–`, `/`) e diferenças de formato numérico (`2.400,0` = `2400`); `Salto em Frequência` = `FHSS` e `Sequência Direta` = `DSSS`. Uma linha do JSON está conforme se existir **uma** linha do CCT em que, em todas as colunas (cabeçalhos equivalentes), os valores do JSON sejam subconjunto dos da célula do CCT; assim, combinações das células distribuídas de outra forma nas linhas do JSON são aceitas (a mesma linha do CCT pode cobrir várias linhas do JSON), mas valores de linhas diferentes do CCT não se misturam. Todo valor só vale na coluna equivalente do CCT (a coluna de técnica de espalhamento do CCT conta como `Tecnologia`). Os valores ausentes, com o título da coluna, entram em **Exigência** numa tabela compacta (Coluna, Valores ausentes no CCT com `(xN)` linhas afetadas); se nenhuma tabela for identificada no CCT, o item `Valores das características no CCT` informa que não foi possível validar.
- Quando o CCT contém `produto não acabado`, verifica se o arquivo mais recente de **Fotos Externas do Produto** contém a frase “Por se tratar de produto não acabado, o produto sob homologação é integralmente identificado pelas fotos internas, cujo arquivo está anexado no campo respectivo”, ignorando maiúsculas/minúsculas e espaços. Se a frase não estiver presente ou não houver esse anexo, acrescenta às exigências: **Corrigir  “Fotos Externas do Produto”, conforme orientação passada por meio do item 6.6.3.2. I  do Ato nº 4083, de 31 de julho de 2020.**
- A exigência de avaliação de SAR é incluída quando nenhum dos campos `SAR (W/kg) Cabeça`, `SAR (W/kg) Tronco` ou `SAR (W/Kg) Membro` contém valor numérico no JSON do requerimento (como número ou string numérica, inclusive com vírgula decimal) e o CCT não contém uma declaração que desobrigue o Ato nº 17865. As declarações desobrigatórias do CCT são usadas nessa validação, mas não são impressas no relatório.

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
- **`familias_equipamentos.json`**: Famílias de equipamentos identificadas por ID para agrupamento na lista do relatório
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

## 📊 Atualização da Planilha ORCN

### Função `processar_requerimentos_excel`

A função `processar_requerimentos_excel` em `core/utils.py` permite atualizar automaticamente a planilha ORCN.xlsx com informações de requerimentos.

#### Uso da Função

```python
from core.utils import processar_requerimentos_excel

# Processar um requerimento específico
processar_requerimentos_excel("25.06969")

# Processar todos os requerimentos do diretório
processar_requerimentos_excel("*")
```

#### Funcionalidades

- **Leitura de JSONs**: Lê arquivos `xx.xxxxx.json` do diretório de requerimentos
- **Verificação de Duplicatas**: Não adiciona uma linha se já houver uma linha com os mesmos dados em B-H e a data de hoje em I
- **Mapeamento Automático**: Mapeia dados do JSON para colunas da planilha (A-K):
  - **A**: `Simplificada`
  - **B**: Nº do Requerimento
  - **C**: Nº de Homologação  
  - **D**: Nº do Certificado
  - **E**: Tipo do Produto
  - **F**: Modelo Produto e Nome Comercial, um par por linha na mesma célula
  - **G**: Solicitante
  - **H**: Fabricante
  - **I**: Data do processamento, como data Excel exibida em `dd/mm/aaaa`
  - **J**: Em branco
  - **K**: Em branco
- **Processamento em Lote**: Suporte ao caractere "*" para processar todos os requerimentos
- **Relatório Detalhado**: Gera relatório de processamento com estatísticas

#### Requisitos

- **Dependências**: `pandas`, `openpyxl`
- **Arquivos**: Planilha ORCN.xlsx na localização configurada
- **Estrutura**: Diretórios de requerimentos no formato `xx.xxxxx` com arquivos JSON correspondentes

#### Comportamento

1. **Validação**: Verifica existência de arquivos e diretórios necessários
2. **Carregamento**: Lê planilha Excel e identifica requerimentos existentes
3. **Processamento**: Para cada requerimento:
   - Verifica se já existe na planilha uma linha com os mesmos dados em B-H e a data atual em I
   - Lê arquivo JSON correspondente
   - Mapeia dados para formato da planilha
   - Adiciona nova linha se necessário
4. **Salvamento**: Atualiza planilha com novos requerimentos
5. **Relatório**: Apresenta estatísticas de processamento
