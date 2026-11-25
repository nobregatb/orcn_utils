# Validação de E-mail do Fabricante

## Resumo das Mudanças

Foi implementada a validação do e-mail do fabricante na geração do relatório de análise de requerimentos. A funcionalidade verifica se o e-mail informado no JSON do requerimento (campo `fabricante.E-mail`) atende aos critérios de validação definidos.

## Regras de Validação

### Tipo 1: Domínio Proibido
- Se o e-mail pertencer ao domínio `anatel.gov.br`
- Se o e-mail pertencer a um domínio de OCD cadastrado em `OCDs.json`

**Mensagem de Exigência:**
```
O e-mail XXXX não é válido, deve-se informar um e-mail do próprio fabricante.
```

### Tipo 2: Formato Inválido
- Se o e-mail não atender ao padrão básico: `algo@algo.algo`

**Mensagem de Exigência:**
```
O e-mail XXXX não parece válido, favor verificar/corrigir cadastro, se necessário.
```

## Comportamento

- **Validação case-insensitive**: A comparação com `anatel.gov.br` e domínios de OCD ignora maiúsculas/minúsculas
- **Remoção de espaços em branco**: E-mails com espaços antes/depois são processados corretamente
- **E-mail vazio ou ausente**: Se o campo estiver vazio ou ausente, nenhuma exigência é gerada
- **Ordem de verificação**: Primeiro verifica se é domínio proibido (tipo 1), depois valida o formato (tipo 2)

## Arquivos Modificados

### 1. `core/analyzer.py`

#### Função Nova: `_validar_email_fabricante()`
- **Localização**: Após a função `_validar_campos_cadastrais()`
- **Parâmetros**:
  - `dados_requerimento: Optional[Dict]` - Dicionário com dados do requerimento
  - `ocds_list: Optional[List[Dict]]` - Lista de OCDs carregada de `OCDs.json`
- **Retorno**:
  - `None` se o e-mail é válido ou ausente
  - `Tuple[int, str]` contendo `(tipo_erro, email)` se houver erro
    - tipo_erro = 1: Domínio proibido
    - tipo_erro = 2: Formato inválido

#### Modificações na Classe `AnalisadorRequerimentos`

**Método `_construir_secao_exigencias()`:**
- Adicionado parâmetro: `validacao_email_fabricante: Optional[Tuple[int, str]] = None`
- Adicionada lógica para gerar exigências de e-mail conforme o tipo de erro
- Atualizada verificação de `tem_exigencias` para incluir validação de e-mail

**Método `_gerar_relatorio_latex()`:**
- Adicionada chamada para `_validar_email_fabricante()` antes de gerar exigências
- Passagem do resultado para `_construir_secao_exigencias()` como novo parâmetro

### 2. `instrucoes/geral.md`

Adicionada documentação sobre a validação de e-mail do fabricante na seção de análise de requerimentos.

## Testes

A implementação foi validada com os seguintes cenários:

1. ✅ E-mail válido do fabricante - Sem exigência
2. ✅ E-mail com domínio ANATEL - Tipo 1 (domínio proibido)
3. ✅ E-mail com domínio de OCD - Tipo 1 (domínio proibido)
4. ✅ E-mail com formato inválido - Tipo 2 (formato inválido)
5. ✅ E-mail vazio - Sem exigência
6. ✅ Campo de e-mail ausente - Sem exigência
7. ✅ Dados do requerimento nulos - Sem exigência
8. ✅ Case-insensitive para ANATEL - Detecta corretamente
9. ✅ E-mail com espaços em branco - Processado corretamente
10. ✅ Case-insensitive para domínios OCD - Detecta corretamente

## Integração com OCDs.json

A validação utiliza o arquivo `utils/OCDs.json` para verificar os domínios de OCD. Os domínios são extraídos do campo `email` de cada OCD e comparados com o domínio do e-mail do fabricante.

Exemplo de OCDs.json:
```json
{
  "sigla": "ICC",
  "email": "icc-ocd.com.br",
  ...
}
```

Neste caso, e-mails como `contato@icc-ocd.com.br` serão detectados como inválidos (tipo 1).

## Notas Importantes

- A validação é executada durante a geração do relatório de análise
- Não há modificação no fluxo de download ou processamento de PDFs
- A validação é realizada apenas se o JSON do requerimento contiver os dados de fabricante
- As exigências são incluídas na seção de exigências do relatório gerado em LaTeX/PDF

## Compatibilidade

- Mantém compatibilidade com todos os campos existentes no JSON do requerimento
- Não afeta outras validações já implementadas
- Segue o padrão de código e nomenclatura do projeto
