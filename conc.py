# Instale o conclave se ainda não tiver
# pip install conclave

from conclave import PDFReader, DocumentProcessor
import json

# 1️⃣ Caminho do PDF
pdf_path = "C:\\Users\\tbnobrega\\OneDrive - ANATEL\\Anatel\\_ORCN\\Requerimentos\\25.06062\\6970-25_CERT_CONFORMIDADE.pdf"

# 2️⃣ Ler o PDF
reader = PDFReader(pdf_path)
texto = reader.extract_text()

# 3️⃣ Processar o texto para JSON
processor = DocumentProcessor()

# Aqui você define como quer estruturar o JSON
instructions = """
Transforme o texto em JSON com as seguintes chaves:
- 'titulo': título principal do documento
- 'autor': nome do autor
- 'conteudo': resumo do conteúdo
Se alguma informação não estiver disponível, use null.
"""

json_output = processor.to_json(texto, instructions=instructions)

# 4️⃣ Converter para dicionário Python
data = json.loads(json_output)

# 5️⃣ Mostrar resultado
print(json.dumps(data, indent=4, ensure_ascii=False))
