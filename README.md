# ORCN Scrapper - Automação de Download de Anexos

Este projeto automatiza o download de anexos de requerimentos do sistema ORCN da ANATEL.

## 🚀 Como Compilar o Executável

### Opção 1: Script Automático (Recomendado)
```bash
python build_exe.py
```

### Opção 2: Manual
```bash
# Instalar dependências
pip install openpyxl playwright pyinstaller

# Instalar browsers do Playwright
python -m playwright install chromium

# Compilar executável
pyinstaller --onefile --name=ORCN_Scrapper tbn_scrapper_ajax.py
```

## 📁 Estrutura de Arquivos

Após a compilação, organize os arquivos assim:

```
pasta_de_trabalho/
├── ORCN_Scrapper.exe      # Executável principal
├── ORCN.xlsx              # Planilha de controle
├── meu_perfil_chrome/     # Perfil do Chrome (opcional)
└── Requerimentos/         # Pasta onde serão salvos os PDFs
    ├── _2024.12345/
    ├── _2024.12346/
    └── ...
```

## 🎯 Como Usar

### Modo Normal (Produção)
```bash
ORCN_Scrapper.exe
```
- Usa o diretório onde o executável está localizado
- Cria pastas e arquivos no mesmo local

### Modo Debug (Desenvolvimento)
```bash
ORCN_Scrapper.exe debug
```
- Usa o caminho fixo configurado no código
- Útil para desenvolvimento e testes

## ⚙️ Configurações

### Caminhos Automáticos
- **Modo Executável**: Uses `C:\caminho\para\executavel\`
- **Modo Debug**: Usa `C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN`

### Arquivos Necessários
- `ORCN.xlsx` - Planilha de controle dos requerimentos
- `meu_perfil_chrome/` - Perfil do Chrome (criado automaticamente se não existir)

## 🔧 Funcionalidades

- ✅ Download automático de PDFs por categoria
- ✅ Nomenclatura padronizada dos arquivos
- ✅ Controle de timeout preventivo (28 minutos)
- ✅ Verificação de arquivos existentes (não redownload)
- ✅ Atualização automática da planilha Excel
- ✅ Navegação por múltiplas páginas (100 itens por página)

## 📋 Categorias de PDFs

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

## ⚠️ Observações Importantes

1. **Chrome**: Certifique-se de que o Google Chrome está instalado
2. **Permissions**: Execute como administrador se necessário
3. **Timeout**: O sistema encerra automaticamente após 28 minutos para evitar timeout do Mosaico
4. **Reexecução**: Após timeout, execute novamente para continuar processando
5. **Internet**: Conexão estável é necessária

## 🐛 Troubleshooting

### Erro: "Chrome não encontrado"
- Verifique se o Chrome está instalado em `C:\Program Files\Google\Chrome\Application\chrome.exe`

### Erro: "ORCN.xlsx não encontrado"
- Certifique-se de que a planilha está no mesmo diretório do executável

### Erro: "Timeout do Mosaico"
- Normal após 28 minutos, execute novamente para continuar

### Modo Debug não funciona
- Execute: `ORCN_Scrapper.exe debug` (com espaço)
- Verifique se o caminho de debug existe