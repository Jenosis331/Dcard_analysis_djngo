import os
import sys
import argparse
import chromadb

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="Incrementally update Chroma Vector DB with new Dcard posts.")
    parser.add_argument("--source", choices=["db", "tmp"], default="db", help="Data source: 'db' (SQLite) or 'tmp' (csv_tmp file)")
    args = parser.parse_args()

    # 1. Setup paths
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    
    chroma_db_path = os.path.join(BASE_DIR, "app_poa_langchain", "chroma_dcard_db")

    print(f"Connecting to Chroma DB at: {chroma_db_path}")
    if not os.path.exists(chroma_db_path):
        print(f"Chroma DB directory does not exist. Creating a new one at {chroma_db_path}")
        os.makedirs(chroma_db_path, exist_ok=True)
        
    try:
        chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        collection = chroma_client.get_or_create_collection(name="dcard_articles")
        # Trigger initial query immediately to prevent DLL/lock conflicts with subsequent imports
        _ = collection.count()
    except Exception as e:
        print(f"Error connecting to Chroma DB: {e}")
        sys.exit(1)

    print("Fetching existing document metadatas from Chroma...")
    try:
        existing_docs = collection.get(include=['metadatas'])
        existing_titles = set()
        existing_article_ids = set()
        
        for meta in existing_docs.get('metadatas', []):
            if not meta:
                continue
            if 'title' in meta:
                existing_titles.add(meta['title'])
            if 'article_id' in meta:
                existing_article_ids.add(str(meta['article_id']))
                
        print(f"Chroma currently has {len(existing_titles)} unique titles and {len(existing_article_ids)} unique article IDs.")
    except Exception as e:
        print(f"Error fetching existing Chroma documents: {e}")
        sys.exit(1)

    # Now that Chroma has successfully initialized and queried, import other libraries
    print("Loading remaining libraries (pandas, sqlite3, genai, etc.)...")
    import sqlite3
    import pandas as pd
    from google import genai
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from tqdm import tqdm

    db_path = os.path.join(BASE_DIR, "db.sqlite3")
    tmp_csv_path = os.path.join(BASE_DIR, "data", "csv_file", "csv_tmp", "dcard_data1_tmp.csv")

    # Load environment variables for Gemini API Key
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        sys.exit(1)

    # 3. Read data from source
    if args.source == "db":
        print(f"Reading from SQLite database: {db_path}")
        if not os.path.exists(db_path):
            print(f"Error: Database file not found at {db_path}")
            sys.exit(1)
        conn = sqlite3.connect(db_path)
        try:
            df = pd.read_sql_query("SELECT article_id, category, article_dates, title, content FROM dcard_data1_all", conn)
        except Exception as e:
            print(f"Error reading SQLite table dcard_data1_all: {e}")
            conn.close()
            sys.exit(1)
        conn.close()
    else:  # tmp
        print(f"Reading from temp CSV: {tmp_csv_path}")
        if not os.path.exists(tmp_csv_path):
            print(f"Error: Temp CSV file not found at {tmp_csv_path}")
            sys.exit(1)
        try:
            df = pd.read_csv(tmp_csv_path, sep="|")
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit(1)

    # Clean data
    df['article_id'] = df['article_id'].astype(str)
    df['title'] = df['title'].fillna("無標題").astype(str)
    df['content'] = df['content'].fillna("").astype(str)
    df['article_dates'] = df['article_dates'].fillna("無日期").astype(str)

    # 4. Filter out already embedded articles
    new_rows = []
    for _, row in df.iterrows():
        aid = row['article_id']
        title = row['title']
        # Check if it's already embedded by title (backward compat) or by article_id
        if aid in existing_article_ids or title in existing_titles:
            continue
        new_rows.append(row)

    print(f"Total articles in source: {len(df)}")
    print(f"New articles to embed: {len(new_rows)}")

    if not new_rows:
        print("No new articles to add. Database is up to date.")
        sys.exit(0)

    # 5. Chunking and preparing for embedding
    # Chunk size 800, overlap 150 (balanced for general context representation)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    
    chunks_to_embed = []
    chunk_metadatas = []
    chunk_ids = []

    for row in new_rows:
        aid = row['article_id']
        title = row['title']
        content = row['content']
        date = row['article_dates']
        
        # Combine title and content to preserve title context in retrieved chunks
        full_text = f"標題: {title}\n內容: {content}"
        
        split_texts = text_splitter.split_text(full_text)
        for i, text in enumerate(split_texts):
            chunks_to_embed.append(text)
            chunk_metadatas.append({
                "article_id": aid,
                "title": title,
                "article_dates": date,
                "chunk_index": i
            })
            # Global unique ID format
            chunk_ids.append(f"article_{aid}_chunk_{i}")

    print(f"Split {len(new_rows)} articles into {len(chunks_to_embed)} chunks.")

    # 6. Generate embeddings and insert to Chroma in batches
    try:
        genai_client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error initializing GenAI Client: {e}")
        sys.exit(1)
        
    batch_size = 50
    print(f"Generating embeddings and writing to Chroma in batches of {batch_size}...")
    
    for idx in tqdm(range(0, len(chunks_to_embed), batch_size)):
        batch_texts = chunks_to_embed[idx : idx + batch_size]
        batch_metas = chunk_metadatas[idx : idx + batch_size]
        batch_ids = chunk_ids[idx : idx + batch_size]
        
        try:
            # Batch embedding call (gemini-embedding-001)
            embed_response = genai_client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch_texts
            )
            embeddings = [emb.values for emb in embed_response.embeddings]
            
            # Upsert into ChromaDB
            collection.upsert(
                ids=batch_ids,
                embeddings=embeddings,
                metadatas=batch_metas,
                documents=batch_texts
            )
        except Exception as e:
            print(f"\nError during embedding/upsert at batch index {idx}: {e}")
            sys.exit(1)

    print(f"Successfully added/updated {len(chunks_to_embed)} chunks for {len(new_rows)} new articles.")

if __name__ == "__main__":
    main()
