import camelot
import pdfplumber

# Caminho do PDF
pdf_path = r'C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN\Requerimentos\25.06062\6970-25_RACT.pdf'

# -----------------------------
# 1. Camelot - LATTICE
# -----------------------------
tables_lattice = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
print("\n=== Camelot - LATTICE ===")
print(f"Tabelas encontradas: {len(tables_lattice)}")
if tables_lattice:
    print("Primeira tabela (head):")
    print(tables_lattice[0].df.head())

# -----------------------------
# 2. Camelot - STREAM
# -----------------------------
tables_stream = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
print("\n=== Camelot - STREAM ===")
print(f"Tabelas encontradas: {len(tables_stream)}")
if tables_stream:
    print("Primeira tabela (head):")
    print(tables_stream[0].df.head())

# -----------------------------
# 3. PDFPLUMBER - texto completo
# -----------------------------
print("\n=== pdfplumber - TEXTO BRUTO ===")
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages, start=1):
        texto = page.extract_text()
        print(f"\n--- Página {i} ---")
        print(texto[:500])  # mostra só os primeiros 500 caracteres

x = 1