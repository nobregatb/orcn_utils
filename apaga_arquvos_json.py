import os

# Caminho base a partir do qual procurar
base_dir = r"C:\Users\tbnobrega\OneDrive - ANATEL\Anatel\_ORCN\req_inbox"

for root, dirs, files in os.walk(base_dir):
    # Filtra apenas subdiretórios que começam com "_"
    if not os.path.basename(root).startswith("_"):
        continue

    for filename in files:
        if filename.endswith(".json"):# and filename.startswith("_"):
            old_path = os.path.join(root, filename)
            new_filename = filename[1:]  # remove o primeiro caractere "_"
            new_path = os.path.join(root, new_filename)

            # Renomeia o arquivo
            #os.rename(old_path, new_path)
            #print(f"Renomeado: {old_path} -> {new_path}")
            if os.path.exists(new_path):
                os.remove(new_path)
            if os.path.exists(old_path):
                os.remove(old_path)
                
