"""
rag_pipeline.py — VERSION CORREGIDA
-------------------------------------
Pipeline RAG simple y robusto para el proyecto Jarvis.
Corrige el problema de bucle infinito en el chunking.
"""

import os
import sys
import time
import json
import argparse
import requests

CORPUS_PATH  = "data/corpus.txt"
CHROMA_DIR   = "rag/chroma_db"
COLLECTION   = "jarvis_corpus"
CHUNK_SIZE   = 1000
TOP_K        = 5
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b-instruct-q4_K_M"
EMBED_MODEL  = "paraphrase-multilingual-MiniLM-L12-v2"

def leer_corpus(ruta):
    print(f"[INFO] Leyendo corpus: {ruta}")
    if not os.path.exists(ruta):
        print(f"[ERROR] No se encontro: {ruta}")
        sys.exit(1)
    with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
        texto = f.read()
    print(f"[INFO] Texto leido: {len(texto):,} caracteres")
    return texto

def cortar_en_chunks(texto):
    """Corte simple por tamano fijo. Sin busqueda de caracteres — evita bucles infinitos."""
    chunks = []
    paso   = CHUNK_SIZE - 100
    i      = 0
    idx    = 0
    while i < len(texto):
        fin   = i + CHUNK_SIZE
        chunk = texto[i:fin].strip()
        if len(chunk) > 50:
            chunks.append({"id": f"chunk_{idx}", "texto": chunk})
            idx += 1
        i += paso
    print(f"[INFO] Corpus cortado en {len(chunks)} chunks")
    return chunks

def construir_indice(chunks):
    print(f"\n[INFO] Cargando modelo de embeddings: {EMBED_MODEL}")
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
    except ImportError as e:
        print(f"[ERROR] Libreria faltante: {e}")
        sys.exit(1)

    modelo_embed = SentenceTransformer(EMBED_MODEL)
    os.makedirs(CHROMA_DIR, exist_ok=True)
    cliente = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        cliente.delete_collection(COLLECTION)
    except Exception:
        pass

    coleccion = cliente.create_collection(name=COLLECTION, metadata={"hnsw:space": "cosine"})
    LOTE  = 50
    total = len(chunks)
    print(f"[INFO] Indexando {total} chunks...")

    for i in range(0, total, LOTE):
        lote   = chunks[i:i + LOTE]
        textos = [c["texto"] for c in lote]
        ids    = [c["id"]    for c in lote]
        embeddings = modelo_embed.encode(textos, show_progress_bar=False, batch_size=32).tolist()
        coleccion.add(documents=textos, embeddings=embeddings, ids=ids)
        progreso   = min(i + LOTE, total)
        porcentaje = int(progreso / total * 100)
        print(f"   [{porcentaje:3d}%] {progreso}/{total} chunks", end="\r")

    print(f"\n[OK] Indice guardado en: {CHROMA_DIR} — {total} chunks")

def cargar_indice():
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
    except ImportError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if not os.path.exists(CHROMA_DIR):
        print("[ERROR] No existe el indice. Ejecuta primero: --build")
        sys.exit(1)

    cliente      = chromadb.PersistentClient(path=CHROMA_DIR)
    coleccion    = cliente.get_collection(COLLECTION)
    print(f"[INFO] {coleccion.count()} chunks disponibles")
    modelo_embed = SentenceTransformer(EMBED_MODEL)
    return coleccion, modelo_embed

def recuperar_chunks(pregunta, coleccion, modelo_embed):
    emb = modelo_embed.encode([pregunta]).tolist()
    res = coleccion.query(query_embeddings=emb, n_results=TOP_K)
    chunks = res["documents"][0]
    dists  = res["distances"][0]
    print(f"\n[INFO] Top {TOP_K} chunks recuperados:")
    for idx, (c, d) in enumerate(zip(chunks, dists)):
        print(f"  [{idx+1}] sim={1-d:.3f} | {c[:80].replace(chr(10),' ')}...")
    return chunks

def llamar_ollama(prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 400, "temperature": 0.3, "seed": 42}
    }
    inicio = time.time()
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=300)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama no responde.")
        sys.exit(1)
    datos  = r.json()
    tiempo = time.time() - inicio
    tokens = datos.get("eval_count", 0)
    tps    = round(tokens / tiempo, 2) if tiempo > 0 else 0
    print(f"[INFO] {tokens} tokens en {tiempo:.1f}s ({tps} tok/s)")
    return datos.get("response", ""), tiempo

def responder_sin_rag(pregunta):
    prompt = (
        f"Responde la siguiente pregunta de forma directa y concisa. "
        f"Si no sabes algo con certeza, dilo.\n\n"
        f"Pregunta: {pregunta}\n\nRespuesta:"
    )
    print("\n[SIN RAG] Llamando al modelo...")
    return llamar_ollama(prompt)

def responder_con_rag(pregunta, chunks):
    contexto = "\n\n---\n\n".join(chunks)
    prompt = (
        f"Eres un asistente experto en análisis de textos en español antiguo.\n"
        f"Lee CUIDADOSAMENTE el siguiente texto del libro 'Don Quijote de la Mancha'\n"
        f"y responde la pregunta usando la información encontrada en él.\n"
        f"El texto está en español del siglo XVII. Si encuentras información relevante,\n"
        f"explícala en español moderno. Responde siempre con la información del texto,\n"
        f"aunque tengas que interpretar palabras antiguas.\n\n"
        f"=== TEXTO DEL LIBRO ===\n{contexto}\n=== FIN DEL TEXTO ===\n\n"
        f"PREGUNTA: {pregunta}\n\n"
        f"Analiza el texto anterior y responde la pregunta de forma clara y completa:"
    )
    print("\n[CON RAG] Llamando al modelo con contexto...")
    return llamar_ollama(prompt)

def comparar(pregunta):
    print("\n" + "="*60)
    print(f"PREGUNTA: {pregunta}")
    print("="*60)

    coleccion, modelo_embed = cargar_indice()
    resp_sin, tiempo_sin    = responder_sin_rag(pregunta)
    chunks                  = recuperar_chunks(pregunta, coleccion, modelo_embed)
    resp_con, tiempo_con    = responder_con_rag(pregunta, chunks)

    print("\n" + "-"*60)
    print("RESPUESTA SIN RAG:")
    print("-"*60)
    print(resp_sin)
    print("\n" + "-"*60)
    print("RESPUESTA CON RAG:")
    print("-"*60)
    print(resp_con)
    print("-"*60)

    resultado = {
        "pregunta": pregunta,
        "sin_rag":  {"respuesta": resp_sin,  "tiempo_s": round(tiempo_sin, 2)},
        "con_rag":  {"respuesta": resp_con,  "tiempo_s": round(tiempo_con, 2),
                     "chunks_usados": chunks}
    }

    os.makedirs("rag", exist_ok=True)
    archivo    = "rag/resultados_comparacion.json"
    anteriores = []
    if os.path.exists(archivo):
        with open(archivo, "r", encoding="utf-8") as f:
            try:
                anteriores = json.load(f)
            except Exception:
                anteriores = []

    anteriores.append(resultado)
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(anteriores, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Guardado en: {archivo}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build",   action="store_true")
    parser.add_argument("--query",   type=str)
    parser.add_argument("--compare", type=str)
    args = parser.parse_args()

    if args.build:
        print("\n=== CONSTRUYENDO INDICE RAG ===")
        texto  = leer_corpus(CORPUS_PATH)
        chunks = cortar_en_chunks(texto)
        construir_indice(chunks)
        print("\n[OK] Listo. Usa --compare 'tu pregunta'")
    elif args.query:
        coleccion, modelo_embed = cargar_indice()
        chunks   = recuperar_chunks(args.query, coleccion, modelo_embed)
        resp, _  = responder_con_rag(args.query, chunks)
        print(f"\nRESPUESTA:\n{resp}")
    elif args.compare:
        comparar(args.compare)
    else:
        print("Uso:")
        print("  python rag/rag_pipeline.py --build")
        print("  python rag/rag_pipeline.py --compare 'tu pregunta'")
        print("  python rag/rag_pipeline.py --query   'tu pregunta'")
