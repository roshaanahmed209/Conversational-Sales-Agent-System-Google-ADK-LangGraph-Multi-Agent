from typing import List, Dict, Any
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv()

class RAGProcessor:
    def __init__(self, persist_directory: str = "chroma_db"):
        # Use Gemini for embeddings (since Groq doesn't provide embeddings)
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        groq_api_key = os.getenv("GROQ_API_KEY")
        
        if not gemini_api_key:
            print("Warning: GEMINI_API_KEY not found. Embeddings may not work.")
        if not groq_api_key:
            print("Warning: GROQ_API_KEY not found. Text generation may not work.")

        # Use Gemini for embeddings
        if gemini_api_key:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=gemini_api_key
            )
        else:
            self.embeddings = None

        # Use Groq for text generation
        if groq_api_key:
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=groq_api_key,
                temperature=0.7
            )
        else:
            self.llm = None

        self.persist_directory = persist_directory
        self.vectorstore = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Try to load existing vectorstore
        self._try_load_existing_vectorstore()

    def _try_load_existing_vectorstore(self):
        """Try to load an existing vectorstore from persistence."""
        if not self.embeddings:
            print("[RAG] No embeddings available, cannot load existing vectorstore")
            return
            
        try:
            if os.path.exists(self.persist_directory):
                print(f"[RAG] Found existing vectorstore directory: {self.persist_directory}")
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings
                )
                # Test if vectorstore has any documents
                try:
                    collection = self.vectorstore._collection
                    count = collection.count()
                    print(f"[RAG] Loaded existing vectorstore with {count} documents")
                    if count == 0:
                        print("[RAG] Vectorstore is empty, will need to reload documents")
                        self.vectorstore = None
                except Exception as e:
                    print(f"[RAG] Error checking vectorstore content: {e}")
                    self.vectorstore = None
            else:
                print(f"[RAG] No existing vectorstore found at {self.persist_directory}")
        except Exception as e:
            print(f"[RAG] Error loading existing vectorstore (likely protobuf issue): {e}")
            print("[RAG] Will continue without vectorstore - RAG functionality will be limited")
            self.vectorstore = None

    def load_documents(self, directory_path: str) -> None:
        print(f"[RAG] Loading documents from: {directory_path}")
        
        if not self.embeddings:
            print("[RAG] Warning: No embeddings available, skipping document loading")
            return
        
        try:
            # Check if directory exists
            if not os.path.exists(directory_path):
                print(f"[RAG] Error: Directory {directory_path} does not exist!")
                return
            
            # List files in directory
            files = []
            for root, dirs, filenames in os.walk(directory_path):
                for filename in filenames:
                    if filename.endswith('.txt'):
                        files.append(os.path.join(root, filename))
            
            print(f"[RAG] Found {len(files)} .txt files: {files}")
            
            # Custom text loader that handles encoding issues
            class SafeTextLoader:
                def __init__(self, file_path: str):
                    self.file_path = file_path
                
                def load(self):
                    from langchain_core.documents import Document
                    
                    print(f"[RAG] Attempting to load: {self.file_path}")
                    
                    # Try different encodings
                    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                    
                    for encoding in encodings:
                        try:
                            with open(self.file_path, 'r', encoding=encoding) as f:
                                content = f.read()
                            
                            print(f"[RAG] Successfully loaded {self.file_path} with {encoding} encoding, content length: {len(content)}")
                            metadata = {"source": self.file_path}
                            return [Document(page_content=content, metadata=metadata)]
                        
                        except UnicodeDecodeError:
                            print(f"[RAG] Failed to load {self.file_path} with {encoding} encoding")
                            continue
                        except Exception as e:
                            print(f"[RAG] Error reading {self.file_path} with {encoding}: {e}")
                            continue
                    
                    # If all encodings fail, skip this file
                    print(f"[RAG] Warning: Could not read {self.file_path} with any encoding, skipping...")
                    return []
                
                def lazy_load(self):
                    """Implement lazy_load method for compatibility with DirectoryLoader."""
                    docs = self.load()
                    for doc in docs:
                        yield doc
            
            loader = DirectoryLoader(
                directory_path,
                glob="**/*.txt",
                loader_cls=SafeTextLoader
            )
            documents = loader.load()
            print(f"[RAG] Loaded {len(documents)} raw documents")

            if not documents:
                print("[RAG] Warning: No documents were loaded successfully")
                return

            # Print sample of loaded content
            for i, doc in enumerate(documents[:4]):  # Show all docs
                source = doc.metadata.get('source', 'unknown')
                filename = source.split('\\')[-1].split('/')[-1]
                print(f"[RAG] Document {i+1} ({filename}): {doc.page_content[:200]}...")

            texts = self.text_splitter.split_documents(documents)
            print(f"[RAG] Split into {len(texts)} chunks")

            # Print chunks by source to see distribution
            chunk_sources = {}
            for chunk in texts:
                source = chunk.metadata.get('source', 'unknown')
                filename = source.split('\\')[-1].split('/')[-1]
                if filename not in chunk_sources:
                    chunk_sources[filename] = 0
                chunk_sources[filename] += 1
            
            print(f"[RAG] Chunks per source: {chunk_sources}")

            # Print sample of chunks with source info
            for i, chunk in enumerate(texts[:4]):  # Show first 4 chunks
                source = chunk.metadata.get('source', 'unknown')
                filename = source.split('\\')[-1].split('/')[-1]
                print(f"[RAG] Chunk {i+1} ({filename}): {chunk.page_content[:100]}...")
            
            # Show some chunks from sample_data.txt specifically
            sample_chunks = [chunk for chunk in texts if 'sample_data.txt' in chunk.metadata.get('source', '')]
            print(f"[RAG] Found {len(sample_chunks)} chunks from sample_data.txt")
            for i, chunk in enumerate(sample_chunks[:2]):
                print(f"[RAG] Sample chunk {i+1}: {chunk.page_content[:100]}...")

            print("[RAG] Creating vectorstore with Chroma...")
            try:
                # Create empty vectorstore first
                self.vectorstore = Chroma(
                    embedding_function=self.embeddings,
                    persist_directory=self.persist_directory
                )
                print(f"[RAG] Empty Chroma vectorstore created")
                
                # Add documents in batches by source to identify issues
                sources_added = set()
                for source_file in ['diff.txt', 'hallu.txt', 'reHack.txt', 'sample_data.txt']:
                    source_chunks = [chunk for chunk in texts if source_file in chunk.metadata.get('source', '')]
                    if source_chunks:
                        print(f"[RAG] Adding {len(source_chunks)} chunks from {source_file}...")
                        try:
                            self.vectorstore.add_documents(source_chunks)
                            sources_added.add(source_file)
                            print(f"[RAG] Successfully added chunks from {source_file}")
                        except Exception as e:
                            print(f"[RAG] Error adding chunks from {source_file}: {e}")
                    else:
                        print(f"[RAG] No chunks found for {source_file}")
                
                print(f"[RAG] Successfully added chunks from sources: {sources_added}")
                
            except Exception as e:
                print(f"[RAG] Error creating Chroma vectorstore (likely protobuf issue): {e}")
                print("[RAG] Continuing without vectorstore - documents loaded but not indexed")
                return
            
            try:
                self.vectorstore.persist()
                print(f"[RAG] Vectorstore persisted successfully")
            except Exception as e:
                print(f"[RAG] Error persisting vectorstore: {e}")
            
            print(f"[RAG] Vectorstore created and persisted with {len(texts)} chunks")
            
            # Verify what's actually in the vectorstore
            print("[RAG] Verifying vectorstore contents...")
            try:
                # Try multiple search terms
                search_terms = ["the", "machine learning", "artificial intelligence", "AI"]
                
                for term in search_terms:
                    verification_docs = self.vectorstore.similarity_search(term, k=20)
                    vectorstore_sources = set()
                    for doc in verification_docs:
                        source = doc.metadata.get('source', '')
                        if source:
                            filename = source.split('\\')[-1].split('/')[-1]
                            vectorstore_sources.add(filename)
                    print(f"[RAG] Search '{term}' found sources: {vectorstore_sources}")
                
                # Try to get all documents in the vectorstore
                print("[RAG] Attempting to get all documents...")
                try:
                    collection = self.vectorstore._collection
                    all_docs = collection.get()
                    if 'metadatas' in all_docs:
                        all_sources = set()
                        for metadata in all_docs['metadatas']:
                            if metadata and 'source' in metadata:
                                source = metadata['source']
                                filename = source.split('\\')[-1].split('/')[-1]
                                all_sources.add(filename)
                        print(f"[RAG] All documents in collection by source: {all_sources}")
                    else:
                        print("[RAG] No metadata found in collection")
                except Exception as e:
                    print(f"[RAG] Error getting all documents: {e}")
                
            except Exception as e:
                print(f"[RAG] Error verifying vectorstore: {e}")
            
        except Exception as e:
            print(f"[RAG] Error during document loading: {e}")
            import traceback
            traceback.print_exc()
            print("[RAG] Continuing without document loading...")

    def retrieve(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        print(f"[RAG] Starting retrieval for query: '{query}' with k={k}")
        
        if not self.vectorstore:
            print("[RAG] Warning: No vectorstore available. Documents may not have been loaded properly.")
            return []

        if not query or query.strip() == "":
            print("[RAG] Empty or invalid query received in retrieve()")
            return []

        print(f"[RAG] Vectorstore exists, attempting similarity search...")
        try:
            docs = self.vectorstore.similarity_search(query, k=k)
            print(f"[RAG] Similarity search returned {len(docs)} documents")

            if docs:
                # Print detailed info about retrieved documents
                for i, doc in enumerate(docs):
                    source = doc.metadata.get('source', 'unknown')
                    print(f"[RAG] Retrieved doc {i+1} from: {source}")
                    print(f"[RAG] Content preview: {doc.page_content[:200]}...")
                    print(f"[RAG] Full metadata: {doc.metadata}")
                    print("---")
            else:
                print("[RAG] No documents found by similarity search")
                
                # Let's try a broader search to see what's in the vectorstore
                print("[RAG] Attempting to retrieve any documents to check vectorstore content...")
                try:
                    all_docs = self.vectorstore.similarity_search("the", k=10)  # Very common word
                    print(f"[RAG] Found {len(all_docs)} documents with broad search")
                    for i, doc in enumerate(all_docs[:3]):  # Show first 3
                        source = doc.metadata.get('source', 'unknown')
                        print(f"[RAG] Sample doc {i+1} from: {source}")
                        print(f"[RAG] Sample content: {doc.page_content[:100]}...")
                except Exception as e:
                    print(f"[RAG] Error in broad search: {e}")

            result = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in docs
            ]
            print(f"[RAG] Returning {len(result)} processed documents")
            return result
        except Exception as e:
            print(f"[RAG] Error during retrieval: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def generate_response(self, query: str, retrieved_docs: List[Dict[str, Any]]) -> str:
        if not self.llm:
            print("[RAG] Warning: No LLM available, returning fallback response")
            return "Sorry, the language model is not available to generate a response."
            
        if not retrieved_docs:
            print("[RAG] No documents retrieved, returning fallback response.")
            return "Sorry, I couldn't find relevant information to answer your question."

        context = "\n\n".join([doc["content"] for doc in retrieved_docs])

        prompt = f"""Based on the following context, please answer the question.
If the answer cannot be found in the context, say so.

Context:
{context}

Question: {query}

Answer:"""

        print("[RAG] Generating response with Groq model")

        try:
            response = await self.llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            print(f"[RAG] Error generating response: {e}")
            return "Sorry, there was an error generating a response to your question."

    def clear_database(self) -> None:
        if os.path.exists(self.persist_directory):
            import shutil
            shutil.rmtree(self.persist_directory)
            print("[RAG] Cleared vectorstore database")

    def debug_status(self):
        """Debug method to check the status of the RAG system."""
        print("\n=== RAG System Debug Status ===")
        print(f"Embeddings available: {self.embeddings is not None}")
        print(f"LLM available: {self.llm is not None}")
        print(f"Vectorstore available: {self.vectorstore is not None}")
        print(f"Persist directory: {self.persist_directory}")
        print(f"Persist directory exists: {os.path.exists(self.persist_directory)}")
        
        if self.vectorstore:
            try:
                collection = self.vectorstore._collection
                count = collection.count()
                print(f"Documents in vectorstore: {count}")
                
                # Get a sample of documents to see what sources are included
                sample_docs = self.vectorstore.similarity_search("the", k=10)
                sources = set()
                for doc in sample_docs:
                    source = doc.metadata.get('source', 'unknown')
                    sources.add(source)
                
                print(f"Document sources found: {list(sources)}")
                
                # Test specific queries
                test_queries = [
                    "machine learning",
                    "reward hacking", 
                    "hallucination",
                    "reinforcement learning"
                ]
                
                for query in test_queries:
                    test_docs = self.vectorstore.similarity_search(query, k=2)
                    print(f"Test query '{query}' returned {len(test_docs)} documents")
                    if test_docs:
                        for i, doc in enumerate(test_docs):
                            source = doc.metadata.get('source', 'unknown')
                            print(f"  Result {i+1} from {source}: {doc.page_content[:100]}...")
                    
            except Exception as e:
                print(f"Error checking vectorstore: {e}")
                import traceback
                traceback.print_exc()
        
        print("=== End Debug Status ===\n")

    def force_reload_documents(self, directory_path: str) -> None:
        """Force reload documents by clearing existing vectorstore first."""
        print("[RAG] Force reloading documents...")
        
        # Properly close existing vectorstore connection
        if self.vectorstore:
            try:
                # Close the collection connection
                if hasattr(self.vectorstore, '_collection'):
                    self.vectorstore._collection = None
                if hasattr(self.vectorstore, '_client'):
                    self.vectorstore._client = None
                print("[RAG] Closed existing vectorstore connections")
            except Exception as e:
                print(f"[RAG] Warning: Error closing vectorstore: {e}")
        
        self.vectorstore = None
        
        # Clear existing vectorstore with retry logic for Windows
        vectorstore_deleted = False
        if os.path.exists(self.persist_directory):
            import shutil
            import time
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(self.persist_directory)
                    print(f"[RAG] Cleared existing vectorstore at {self.persist_directory}")
                    vectorstore_deleted = True
                    break
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        print(f"[RAG] Attempt {attempt + 1} failed to delete vectorstore (file locked), retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        print(f"[RAG] Warning: Could not delete vectorstore after {max_retries} attempts: {e}")
                        print("[RAG] Will create new vectorstore with different name...")
                        # Use a different directory name if deletion fails
                        import uuid
                        self.persist_directory = f"chroma_db_{uuid.uuid4().hex[:8]}"
                        print(f"[RAG] Using new persist directory: {self.persist_directory}")
                        vectorstore_deleted = True
                        break
                except Exception as e:
                    print(f"[RAG] Error deleting vectorstore: {e}")
                    break
        else:
            vectorstore_deleted = True
        
        # Only reload documents if we successfully cleared or can create new vectorstore
        if vectorstore_deleted:
            self.load_documents(directory_path)
        else:
            print("[RAG] Skipping document reload due to vectorstore deletion failure")

    def close_vectorstore(self):
        """Properly close the vectorstore connections."""
        if self.vectorstore:
            try:
                # Close the collection connection
                if hasattr(self.vectorstore, '_collection'):
                    self.vectorstore._collection = None
                if hasattr(self.vectorstore, '_client'):
                    self.vectorstore._client = None
                print("[RAG] Closed vectorstore connections")
            except Exception as e:
                print(f"[RAG] Warning: Error closing vectorstore: {e}")
        self.vectorstore = None
