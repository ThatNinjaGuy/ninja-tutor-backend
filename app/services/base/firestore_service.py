"""
Base Firestore service with common CRUD operations
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from firebase_admin import firestore

from ...core.exceptions import FirestoreException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class FirestoreBaseService:
    """Base service for Firestore operations"""
    
    def __init__(self, collection_name: str):
        """
        Initialize base service
        
        Args:
            collection_name: Name of the Firestore collection
        """
        self.collection_name = collection_name
        self.db = firestore.client()
        self.collection = self.db.collection(collection_name)
    
    async def get_all_by_user(self, user_id: str, order_by: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all documents for a user
        
        Args:
            user_id: User ID to filter by
            order_by: Field to order by
            limit: Maximum number of results
            
        Returns:
            List of documents
            
        Raises:
            FirestoreException: If query fails
        """
        try:
            query = self.collection.where("user_id", "==", user_id)
            
            if order_by:
                query = query.order_by(order_by)
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            logger.info(f"Retrieved {len(results)} documents from {self.collection_name} for user {user_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving documents from {self.collection_name}: {str(e)}")
            raise FirestoreException(
                f"Failed to retrieve documents from {self.collection_name}",
                details={"user_id": user_id, "error": str(e)}
            )
    
    async def get_by_id(self, doc_id: str) -> Dict[str, Any]:
        """
        Get a document by ID
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document data
            
        Raises:
            ResourceNotFoundException: If document not found
            FirestoreException: If query fails
        """
        try:
            doc_ref = self.collection.document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ResourceNotFoundException(
                    f"Document not found in {self.collection_name}",
                    details={"doc_id": doc_id}
                )
            
            data = doc.to_dict()
            data['id'] = doc.id
            
            logger.info(f"Retrieved document {doc_id} from {self.collection_name}")
            return data
            
        except ResourceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id} from {self.collection_name}: {str(e)}")
            raise FirestoreException(
                f"Failed to retrieve document from {self.collection_name}",
                details={"doc_id": doc_id, "error": str(e)}
            )
    
    async def create(self, data: Dict[str, Any], doc_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new document
        
        Args:
            data: Document data
            doc_id: Optional document ID (auto-generated if not provided)
            
        Returns:
            Created document with ID
            
        Raises:
            FirestoreException: If creation fails
        """
        try:
            # Add timestamps
            data['created_at'] = datetime.utcnow().isoformat()
            data['updated_at'] = datetime.utcnow().isoformat()
            
            if doc_id:
                doc_ref = self.collection.document(doc_id)
                doc_ref.set(data)
                result_id = doc_id
            else:
                _, doc_ref = self.collection.add(data)
                result_id = doc_ref.id
            
            data['id'] = result_id
            
            logger.info(f"Created document {result_id} in {self.collection_name}")
            return data
            
        except Exception as e:
            logger.error(f"Error creating document in {self.collection_name}: {str(e)}")
            raise FirestoreException(
                f"Failed to create document in {self.collection_name}",
                details={"error": str(e)}
            )
    
    async def update(self, doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing document
        
        Args:
            doc_id: Document ID
            data: Data to update
            
        Returns:
            Updated document
            
        Raises:
            ResourceNotFoundException: If document not found
            FirestoreException: If update fails
        """
        try:
            doc_ref = self.collection.document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ResourceNotFoundException(
                    f"Document not found in {self.collection_name}",
                    details={"doc_id": doc_id}
                )
            
            # Add update timestamp
            data['updated_at'] = datetime.utcnow().isoformat()
            
            doc_ref.update(data)
            
            # Retrieve updated document
            updated_doc = doc_ref.get()
            result = updated_doc.to_dict()
            result['id'] = doc_id
            
            logger.info(f"Updated document {doc_id} in {self.collection_name}")
            return result
            
        except ResourceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error updating document {doc_id} in {self.collection_name}: {str(e)}")
            raise FirestoreException(
                f"Failed to update document in {self.collection_name}",
                details={"doc_id": doc_id, "error": str(e)}
            )
    
    async def delete(self, doc_id: str) -> bool:
        """
        Delete a document
        
        Args:
            doc_id: Document ID
            
        Returns:
            True if successful
            
        Raises:
            ResourceNotFoundException: If document not found
            FirestoreException: If deletion fails
        """
        try:
            doc_ref = self.collection.document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ResourceNotFoundException(
                    f"Document not found in {self.collection_name}",
                    details={"doc_id": doc_id}
                )
            
            doc_ref.delete()
            
            logger.info(f"Deleted document {doc_id} from {self.collection_name}")
            return True
            
        except ResourceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {self.collection_name}: {str(e)}")
            raise FirestoreException(
                f"Failed to delete document from {self.collection_name}",
                details={"doc_id": doc_id, "error": str(e)}
            )
    
    async def query(
        self,
        filters: List[tuple],
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query documents with custom filters
        
        Args:
            filters: List of (field, operator, value) tuples
            order_by: Field to order by
            limit: Maximum number of results
            
        Returns:
            List of matching documents
            
        Raises:
            FirestoreException: If query fails
        """
        try:
            query = self.collection
            
            for field, operator, value in filters:
                query = query.where(field, operator, value)
            
            if order_by:
                query = query.order_by(order_by)
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            logger.info(f"Query returned {len(results)} documents from {self.collection_name}")
            return results
            
        except Exception as e:
            logger.error(f"Error querying {self.collection_name}: {str(e)}")
            raise FirestoreException(
                f"Failed to query {self.collection_name}",
                details={"error": str(e)}
            )

