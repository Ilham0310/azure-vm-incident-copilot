"""
Incident Memory Store

ChromaDB-based vector store for past incidents with human feedback.
Supports similarity search, verified case prioritization, and feedback updates.
"""

import os
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class IncidentMemoryStore:
    """
    Vector-based memory store for past incidents.
    
    Features:
    - ChromaDB for vector storage with HNSW index
    - sentence-transformers for local embeddings (no API calls)
    - Similarity search with cosine distance
    - Human feedback tracking (verified cases prioritized)
    - Automatic incident storage after each decision
    """
    
    def __init__(
        self,
        persist_path: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize incident memory store.
        
        Args:
            persist_path: Path to ChromaDB persistence directory
            embedding_model: sentence-transformers model name
        """
        self._persist_path = persist_path or os.getenv(
            "CHROMA_MEMORY_PATH",
            "data/chroma_memory"
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
            f"Initialized IncidentMemoryStore with path: {self._persist_path}, "
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
                name="incidents",
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
            logger.debug(f"ChromaDB collection 'incidents' ready")
        return self._collection
    
    def _get_embedding_model(self):
        """
        Lazy initialization of sentence-transformers model with retry logic.
        
        Retries download 3 times with exponential backoff if model fails to load.
        """
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                max_retries = 3
                retry_delay = 2  # seconds
                
                for attempt in range(max_retries):
                    try:
                        logger.info(
                            f"Loading embedding model: {self._embedding_model_name} "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        self._embedding_model = SentenceTransformer(self._embedding_model_name)
                        logger.info(f"Successfully loaded embedding model: {self._embedding_model_name}")
                        break
                    except Exception as download_error:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(
                                f"Failed to load embedding model (attempt {attempt + 1}/{max_retries}): "
                                f"{download_error}. Retrying in {wait_time}s..."
                            )
                            import time
                            time.sleep(wait_time)
                        else:
                            logger.error(
                                f"Failed to load embedding model after {max_retries} attempts: "
                                f"{download_error}"
                            )
                            raise
                            
            except ImportError:
                raise ImportError(
                    "sentence-transformers package not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load embedding model after all retries: {e}. "
                    "RAG features will be disabled. To manually download the model, run: "
                    "python -c \"from sentence_transformers import SentenceTransformer; "
                    f"SentenceTransformer('{self._embedding_model_name}')\""
                )
                raise
        return self._embedding_model

    
    def _telemetry_to_text(self, telemetry: Dict) -> str:
        """
        Convert telemetry to concise text summary for embedding.
        
        Extracts only key discriminative signals to ensure high-quality embeddings.
        Does not include all 30+ fields to keep embeddings focused.
        
        Args:
            telemetry: Telemetry dict or TelemetryInput object
            
        Returns:
            Concise text summary of key signals
        """
        # Handle both dict and TelemetryInput objects
        if hasattr(telemetry, 'model_dump'):
            t = telemetry.model_dump()
        elif hasattr(telemetry, 'dict'):
            t = telemetry.dict()
        else:
            t = telemetry
        
        # Extract key discriminative signals
        parts = []
        
        # Power and provisioning state
        if t.get('power_state'):
            parts.append(f"VM state: {t['power_state']}")
        if t.get('provisioning_state'):
            parts.append(f"Provisioning: {t['provisioning_state']}")
        
        # Health status
        if t.get('resource_health_status'):
            parts.append(f"Health: {t['resource_health_status']}")
        
        # Performance metrics
        if t.get('cpu_percent') is not None:
            parts.append(f"CPU: {t['cpu_percent']:.0f}%")
        if t.get('memory_percent') is not None:
            parts.append(f"Memory: {t['memory_percent']:.0f}%")
        
        # Heartbeat
        if t.get('heartbeat_present') is not None:
            parts.append(f"Heartbeat: {t['heartbeat_present']}")
        
        # Boot diagnostics
        if t.get('boot_diagnostics_status'):
            parts.append(f"Boot: {t['boot_diagnostics_status']}")
        
        # Network connectivity
        if t.get('nsg_allow_rdp_3389') is not None:
            parts.append(f"RDP allowed: {t['nsg_allow_rdp_3389']}")
        if t.get('nsg_allow_ssh_22') is not None:
            parts.append(f"SSH allowed: {t['nsg_allow_ssh_22']}")
        
        # Application health
        if t.get('app_health_status'):
            parts.append(f"App health: {t['app_health_status']}")
        
        # VM agent
        if t.get('azure_vm_agent_status'):
            parts.append(f"VM agent: {t['azure_vm_agent_status']}")
        
        # Disk usage
        if t.get('os_disk_percent_full') is not None:
            parts.append(f"Disk: {t['os_disk_percent_full']:.0f}% full")
        
        return ". ".join(parts) + "."

    
    def add_incident(
        self,
        telemetry: Dict,
        decision: str,
        diagnosis: str,
        confidence: float,
        pattern: Optional[str] = None,
        next_check: Optional[str] = None,
        vm_name: Optional[str] = None
    ) -> str:
        """
        Store a new incident in the memory store.
        
        Args:
            telemetry: Telemetry dict or TelemetryInput object
            decision: Decision state (diagnose, diagnose_low_confidence, abstain)
            diagnosis: Diagnosis text
            confidence: Confidence score (0.0-1.0)
            pattern: Pattern name (optional)
            next_check: Next check recommendation (optional)
            vm_name: VM name (optional)
            
        Returns:
            incident_id: Unique identifier for this incident
        """
        try:
            # Generate incident ID
            timestamp = datetime.now().isoformat()
            vm = vm_name or telemetry.get('vm_name', 'unknown')
            incident_id = hashlib.md5(
                f"{vm}_{timestamp}".encode()
            ).hexdigest()[:12]
            
            # Convert telemetry to text
            telemetry_text = self._telemetry_to_text(telemetry)
            
            # Generate embedding
            model = self._get_embedding_model()
            embedding = model.encode(telemetry_text).tolist()
            
            # Extract power_state and health_status for metadata
            if hasattr(telemetry, 'model_dump'):
                t = telemetry.model_dump()
            elif hasattr(telemetry, 'dict'):
                t = telemetry.dict()
            else:
                t = telemetry
            
            # Prepare metadata
            metadata = {
                "incident_id": incident_id,
                "vm_name": vm,
                "timestamp": timestamp,
                "decision": decision,
                "diagnosis": diagnosis,
                "next_check": next_check or "",
                "confidence": str(confidence),
                "human_verified": "False",
                "outcome": "pending",
                "pattern": pattern or "unknown",
                "power_state": t.get('power_state', 'Unknown'),
                "health_status": t.get('resource_health_status', 'Unknown')
            }
            
            # Store in ChromaDB
            collection = self._get_collection()
            collection.add(
                ids=[incident_id],
                embeddings=[embedding],
                documents=[telemetry_text],
                metadatas=[metadata]
            )
            
            logger.info(f"Stored incident {incident_id} in memory store")
            return incident_id
            
        except Exception as e:
            logger.warning(f"Failed to store incident in memory: {e}")
            # Non-fatal - return empty ID
            return ""

    
    def find_similar_incidents(
        self,
        telemetry: Dict,
        top_k: int = 5,
        min_similarity: float = 0.65
    ) -> List[Dict]:
        """
        Find similar past incidents using vector similarity search.
        
        Args:
            telemetry: Telemetry dict or TelemetryInput object
            top_k: Number of similar incidents to return
            min_similarity: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            List of similar incidents with metadata, sorted by:
            1. human_verified DESC (verified cases first)
            2. similarity DESC (most similar first)
        """
        try:
            collection = self._get_collection()
            
            # Check if collection is empty
            count = collection.count()
            if count == 0:
                logger.debug("Memory store is empty, no similar incidents")
                return []
            
            # Convert telemetry to text and generate embedding
            telemetry_text = self._telemetry_to_text(telemetry)
            model = self._get_embedding_model()
            query_embedding = model.encode(telemetry_text).tolist()
            
            # Query ChromaDB (returns top_k * 2 to allow filtering)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 2, count)
            )
            
            # Process results
            similar_incidents = []
            
            if results['ids'] and len(results['ids'][0]) > 0:
                for i, incident_id in enumerate(results['ids'][0]):
                    # Calculate similarity from distance
                    # ChromaDB returns cosine distance, convert to similarity
                    distance = results['distances'][0][i]
                    similarity = 1.0 - distance
                    
                    # Filter by minimum similarity
                    if similarity < min_similarity:
                        continue
                    
                    metadata = results['metadatas'][0][i]
                    document = results['documents'][0][i]
                    
                    incident = {
                        "incident_id": incident_id,
                        "telemetry_summary": document,
                        "diagnosis": metadata.get("diagnosis", ""),
                        "next_check": metadata.get("next_check", ""),
                        "decision": metadata.get("decision", ""),
                        "confidence": float(metadata.get("confidence", 0.0)),
                        "human_verified": metadata.get("human_verified", "False") == "True",
                        "outcome": metadata.get("outcome", "pending"),
                        "pattern": metadata.get("pattern", "unknown"),
                        "similarity_score": round(similarity, 3)
                    }
                    
                    # Include corrected diagnosis/next_check if available
                    if metadata.get("corrected_diagnosis"):
                        incident["corrected_diagnosis"] = metadata.get("corrected_diagnosis")
                    if metadata.get("corrected_next_check"):
                        incident["corrected_next_check"] = metadata.get("corrected_next_check")
                    
                    similar_incidents.append(incident)
            
            # Sort by: human_verified DESC, similarity DESC
            similar_incidents.sort(
                key=lambda x: (x["human_verified"], x["similarity_score"]),
                reverse=True
            )
            
            # Return top K
            result = similar_incidents[:top_k]
            logger.info(
                f"Found {len(result)} similar incidents "
                f"(min_similarity={min_similarity})"
            )
            return result
            
        except Exception as e:
            logger.warning(f"Failed to find similar incidents: {e}")
            return []

    
    def update_feedback(
        self,
        incident_id: str,
        correct: bool,
        corrected_diagnosis: Optional[str] = None,
        corrected_next_check: Optional[str] = None,
        outcome: str = "resolved"
    ) -> bool:
        """
        Update incident with human feedback.
        
        Args:
            incident_id: Incident identifier
            correct: Whether the diagnosis was correct
            corrected_diagnosis: Corrected diagnosis if incorrect
            corrected_next_check: Corrected next_check if incorrect
            outcome: Outcome status (resolved, escalated, false_positive)
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            collection = self._get_collection()
            
            # Get existing incident
            result = collection.get(ids=[incident_id])
            if not result['ids']:
                logger.warning(f"Incident {incident_id} not found")
                return False
            
            # Update metadata
            metadata = result['metadatas'][0]
            metadata['human_verified'] = "True"
            metadata['outcome'] = outcome
            
            # Store corrected versions as alternative fields (keep originals)
            if not correct and corrected_diagnosis:
                metadata['corrected_diagnosis'] = corrected_diagnosis
            if not correct and corrected_next_check:
                metadata['corrected_next_check'] = corrected_next_check
            
            # Update in ChromaDB
            collection.update(
                ids=[incident_id],
                metadatas=[metadata]
            )
            
            logger.info(
                f"Updated incident {incident_id} with feedback "
                f"(correct={correct}, outcome={outcome})"
            )
            return True
            
        except Exception as e:
            logger.warning(f"Failed to update feedback for {incident_id}: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get memory store statistics.
        
        Returns:
            Dict with total, verified, patterns distribution
        """
        try:
            collection = self._get_collection()
            total = collection.count()
            
            if total == 0:
                return {
                    "total": 0,
                    "verified": 0,
                    "patterns": {},
                    "top_patterns": []
                }
            
            # Get all incidents
            results = collection.get()
            
            # Count verified
            verified = sum(
                1 for m in results['metadatas']
                if m.get('human_verified') == 'True'
            )
            
            # Count patterns
            patterns = {}
            for m in results['metadatas']:
                pattern = m.get('pattern', 'unknown')
                patterns[pattern] = patterns.get(pattern, 0) + 1
            
            # Sort patterns by count
            top_patterns = sorted(
                patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            return {
                "total": total,
                "verified": verified,
                "patterns": patterns,
                "top_patterns": top_patterns
            }
            
        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            return {
                "total": 0,
                "verified": 0,
                "patterns": {},
                "top_patterns": []
            }
