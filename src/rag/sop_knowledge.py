"""
SOP Knowledge Base

ChromaDB-based vector store for Standard Operating Procedures (SOPs).
Supports semantic search to find relevant SOPs for incident remediation.
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SOPKnowledgeBase:
    """
    Vector-based knowledge base for Standard Operating Procedures.
    
    Features:
    - ChromaDB for vector storage (separate collection from incidents)
    - sentence-transformers for local embeddings
    - Semantic search for relevant SOPs
    - Pre-populated with 12 SOPs on first run
    """
    
    def __init__(
        self,
        persist_path: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize SOP knowledge base.
        
        Args:
            persist_path: Path to ChromaDB persistence directory
            embedding_model: sentence-transformers model name
        """
        self._persist_path = persist_path or os.getenv(
            "CHROMA_SOP_PATH",
            "data/chroma_sops"
        )
        self._embedding_model_name = embedding_model or os.getenv(
            "EMBEDDING_MODEL",
            "all-MiniLM-L6-v2"
        )
        
        self._client = None
        self._collection = None
        self._embedding_model = None
        
        # Ensure persistence directory exists
        Path(self._persist_path).mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"Initialized SOPKnowledgeBase with path: {self._persist_path}, "
            f"model: {self._embedding_model_name}"
        )
    
    def _get_client(self):
        """Lazy initialization of ChromaDB client"""
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=self._persist_path)
                logger.debug(f"ChromaDB client initialized at {self._persist_path}")
            except ImportError:
                raise ImportError(
                    "chromadb package not installed. Install with: pip install chromadb"
                )
        return self._client
    
    def _get_collection(self):
        """Lazy initialization of ChromaDB collection"""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name="sops",
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
            logger.debug(f"ChromaDB collection 'sops' ready")
        return self._collection
    
    def _get_embedding_model(self):
        """Lazy initialization of sentence-transformers model"""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer(self._embedding_model_name)
                logger.info(f"Loaded embedding model: {self._embedding_model_name}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers package not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._embedding_model
    
    def add_sop(
        self,
        sop_id: str,
        title: str,
        description: str,
        triggers: str,
        steps: str,
        warnings: Optional[str] = None
    ) -> bool:
        """
        Add a new SOP to the knowledge base.
        
        Args:
            sop_id: Unique SOP identifier
            title: SOP title
            description: Brief description
            triggers: When to use this SOP
            steps: Step-by-step instructions
            warnings: Safety warnings (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create embedding text: title + triggers + steps
            embedding_text = f"{title}. Triggers: {triggers}. Steps: {steps}"
            
            # Generate embedding
            model = self._get_embedding_model()
            embedding = model.encode(embedding_text).tolist()
            
            # Prepare metadata
            metadata = {
                "sop_id": sop_id,
                "title": title,
                "description": description,
                "triggers": triggers,
                "steps": steps,
                "warnings": warnings or ""
            }
            
            # Store in ChromaDB
            collection = self._get_collection()
            collection.add(
                ids=[sop_id],
                embeddings=[embedding],
                documents=[embedding_text],
                metadatas=[metadata]
            )
            
            logger.info(f"Added SOP: {sop_id} - {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add SOP {sop_id}: {e}")
            return False
    
    def find_relevant_sops(
        self,
        telemetry_text: str,
        top_k: int = 3
    ) -> List[Dict]:
        """
        Find relevant SOPs for given telemetry.
        
        Args:
            telemetry_text: Text summary of telemetry
            top_k: Number of SOPs to return
            
        Returns:
            List of relevant SOPs with metadata
        """
        try:
            collection = self._get_collection()
            
            # Check if collection is empty
            count = collection.count()
            if count == 0:
                logger.warning("SOP knowledge base is empty")
                return []
            
            # Generate embedding for query
            model = self._get_embedding_model()
            query_embedding = model.encode(telemetry_text).tolist()
            
            # Query ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, count)
            )
            
            # Process results
            relevant_sops = []
            
            if results['ids'] and len(results['ids'][0]) > 0:
                for i, sop_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    
                    # Calculate relevance score
                    distance = results['distances'][0][i]
                    relevance = 1.0 - distance
                    
                    sop = {
                        "sop_id": sop_id,
                        "title": metadata.get("title", ""),
                        "description": metadata.get("description", ""),
                        "triggers": metadata.get("triggers", ""),
                        "steps": metadata.get("steps", ""),
                        "warnings": metadata.get("warnings", ""),
                        "relevance_score": round(relevance, 3)
                    }
                    
                    relevant_sops.append(sop)
            
            logger.info(f"Found {len(relevant_sops)} relevant SOPs")
            return relevant_sops
            
        except Exception as e:
            logger.warning(f"Failed to find relevant SOPs: {e}")
            return []
    
    def get_sop_count(self) -> int:
        """Get total number of SOPs in knowledge base"""
        try:
            collection = self._get_collection()
            return collection.count()
        except Exception as e:
            logger.warning(f"Failed to get SOP count: {e}")
            return 0
    
    def clear(self) -> bool:
        """Clear all SOPs from knowledge base"""
        try:
            client = self._get_client()
            client.delete_collection("sops")
            self._collection = None
            logger.info("Cleared SOP knowledge base")
            return True
        except Exception as e:
            logger.error(f"Failed to clear SOP knowledge base: {e}")
            return False
