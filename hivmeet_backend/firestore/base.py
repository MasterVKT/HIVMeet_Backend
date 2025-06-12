"""
Base Firestore manager class.
"""
from datetime import datetime
from hivmeet_backend.firebase_service import firebase_service
from google.cloud.firestore_v1 import FieldFilter, Query
from google.api_core.exceptions import NotFound
import logging
from typing import Dict, List, Optional, Any, Tuple
from django.utils import timezone

logger = logging.getLogger('hivmeet.firestore')


class BaseFirestoreManager:
    """
    Base class for Firestore collection managers.
    """
    collection_name: str = None
    
    def __init__(self):
        if not self.collection_name:
            raise ValueError("collection_name must be defined")
        self.db = firebase_service.db
        self.collection = self.db.collection(self.collection_name)
    
    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.
        """
        try:
            doc = self.collection.document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Error getting document {doc_id} from {self.collection_name}: {str(e)}")
            raise
    
    def create(self, data: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """
        Create a new document.
        """
        try:
            # Add timestamps
            data['created_at'] = datetime.now(datetime.timezone.utc)
            data['updated_at'] = datetime.now(datetime.timezone.utc)
            
            if doc_id:
                self.collection.document(doc_id).set(data)
                logger.info(f"Created document with ID {doc_id} in {self.collection_name}")
                return doc_id
            else:
                doc_ref = self.collection.add(data)
                doc_id = doc_ref[1].id
                logger.info(f"Created document with auto-generated ID {doc_id} in {self.collection_name}")
                return doc_id
        except Exception as e:
            logger.error(f"Error creating document in {self.collection_name}: {str(e)}")
            raise
    
    def update(self, doc_id: str, data: Dict[str, Any]) -> bool:
        """
        Update a document.
        """
        try:
            # Add updated timestamp
            data['updated_at'] = datetime.utcnow()
            
            self.collection.document(doc_id).update(data)
            logger.info(f"Updated document {doc_id} in {self.collection_name}")
            return True
        except NotFound:
            logger.error(f"Document {doc_id} not found in {self.collection_name}")
            return False
        except Exception as e:
            logger.error(f"Error updating document {doc_id} in {self.collection_name}: {str(e)}")
            raise
    
    def delete(self, doc_id: str) -> bool:
        """
        Delete a document.
        """
        try:
            self.collection.document(doc_id).delete()
            logger.info(f"Deleted document {doc_id} from {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {self.collection_name}: {str(e)}")
            raise
    
    def query(
        self,
        filters: List[Tuple[str, str, Any]] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query documents with filters.
        
        Args:
            filters: List of tuples (field, operator, value)
            order_by: Field to order by
            order_direction: 'asc' or 'desc'
            limit: Maximum number of results
            offset: Number of results to skip
        """
        try:
            query = self.collection
            
            # Apply filters
            if filters:
                for field, operator, value in filters:
                    if operator == '==':
                        query = query.where(filter=FieldFilter(field, '==', value))
                    elif operator == '!=':
                        query = query.where(filter=FieldFilter(field, '!=', value))
                    elif operator == '<':
                        query = query.where(filter=FieldFilter(field, '<', value))
                    elif operator == '<=':
                        query = query.where(filter=FieldFilter(field, '<=', value))
                    elif operator == '>':
                        query = query.where(filter=FieldFilter(field, '>', value))
                    elif operator == '>=':
                        query = query.where(filter=FieldFilter(field, '>=', value))
                    elif operator == 'in':
                        query = query.where(filter=FieldFilter(field, 'in', value))
                    elif operator == 'array-contains':
                        query = query.where(filter=FieldFilter(field, 'array_contains', value))
            
            # Apply ordering
            if order_by:
                direction = Query.DESCENDING if order_direction == 'desc' else Query.ASCENDING
                query = query.order_by(order_by, direction=direction)
            
            # Apply pagination
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            # Execute query
            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            return results
        except Exception as e:
            logger.error(f"Error querying {self.collection_name}: {str(e)}")
            raise
    
    def batch_create(self, documents: List[Dict[str, Any]]) -> List[str]:
        """
        Create multiple documents in a batch.
        """
        batch = self.db.batch()
        doc_ids = []
        
        try:
            for data in documents:
                # Add timestamps
                data['created_at'] = datetime.utcnow()
                data['updated_at'] = datetime.utcnow()
                
                doc_ref = self.collection.document()
                batch.set(doc_ref, data)
                doc_ids.append(doc_ref.id)
            
            batch.commit()
            logger.info(f"Batch created {len(documents)} documents in {self.collection_name}")
            return doc_ids
        except Exception as e:
            logger.error(f"Error in batch create for {self.collection_name}: {str(e)}")
            raise
    
    def batch_update(self, updates: List[Tuple[str, Dict[str, Any]]]) -> bool:
        """
        Update multiple documents in a batch.
        
        Args:
            updates: List of tuples (doc_id, update_data)
        """
        batch = self.db.batch()
        
        try:
            for doc_id, data in updates:
                # Add updated timestamp
                data['updated_at'] = datetime.utcnow()
                
                doc_ref = self.collection.document(doc_id)
                batch.update(doc_ref, data)
            
            batch.commit()
            logger.info(f"Batch updated {len(updates)} documents in {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error in batch update for {self.collection_name}: {str(e)}")
            raise