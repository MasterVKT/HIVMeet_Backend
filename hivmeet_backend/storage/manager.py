"""
Firebase Storage manager for file operations.
"""
from hivmeet_backend.firebase_service import firebase_service
from google.cloud import storage
from typing import Optional, Tuple, Dict, Any
import logging
import mimetypes
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
import hashlib

logger = logging.getLogger('hivmeet.storage')


class StorageManager:
    """
    Manager for Firebase Storage operations.
    """
    
    def __init__(self):
        self.bucket = firebase_service.bucket
    
    def upload_file(
        self,
        file_data: bytes,
        file_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload a file to Firebase Storage.
        
        Args:
            file_data: File content as bytes
            file_path: Path where to store the file
            content_type: MIME type of the file
            metadata: Additional metadata for the file
            
        Returns:
            Public URL of the uploaded file
        """
        try:
            blob = self.bucket.blob(file_path)
            
            # Set content type
            if content_type:
                blob.content_type = content_type
            else:
                # Try to guess content type from file path
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type:
                    blob.content_type = content_type
            
            # Set metadata
            if metadata:
                blob.metadata = metadata
            
            # Upload file
            blob.upload_from_string(file_data, content_type=content_type)
            
            # Make the blob publicly accessible (for profile photos)
            # For sensitive documents, we'll use signed URLs instead
            if file_path.startswith('profiles/'):
                blob.make_public()
                return blob.public_url
            else:
                # Return the path for sensitive files
                return file_path
                
        except Exception as e:
            logger.error(f"Error uploading file to {file_path}: {str(e)}")
            raise
    
    def upload_image(
        self,
        image_data: bytes,
        base_path: str,
        max_size: Tuple[int, int] = (1920, 1920),
        thumbnail_size: Tuple[int, int] = (200, 200),
        quality: int = 85
    ) -> Dict[str, str]:
        """
        Upload an image with automatic resizing and thumbnail generation.
        
        Args:
            image_data: Image data as bytes
            base_path: Base path for storing the image (e.g., 'profiles/user123/')
            max_size: Maximum dimensions for the main image
            thumbnail_size: Dimensions for the thumbnail
            quality: JPEG quality (1-100)
            
        Returns:
            Dictionary with 'main' and 'thumbnail' URLs
        """
        try:
            # Open image
            image = Image.open(BytesIO(image_data))
            
            # Convert RGBA to RGB if necessary
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            # Generate unique filename
            file_hash = hashlib.md5(image_data).hexdigest()[:8]
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{file_hash}.jpg"
            
            # Process main image
            main_image = image.copy()
            main_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save main image to bytes
            main_buffer = BytesIO()
            main_image.save(main_buffer, format='JPEG', quality=quality, optimize=True)
            main_data = main_buffer.getvalue()
            
            # Upload main image
            main_path = f"{base_path}main/{filename}"
            main_url = self.upload_file(
                main_data,
                main_path,
                content_type='image/jpeg'
            )
            
            # Process thumbnail
            thumb_image = image.copy()
            thumb_image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            
            # Save thumbnail to bytes
            thumb_buffer = BytesIO()
            thumb_image.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
            thumb_data = thumb_buffer.getvalue()
            
            # Upload thumbnail
            thumb_path = f"{base_path}thumbnails/{filename}"
            thumb_url = self.upload_file(
                thumb_data,
                thumb_path,
                content_type='image/jpeg'
            )
            
            return {
                'main': main_url,
                'thumbnail': thumb_url,
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f"Error processing and uploading image: {str(e)}")
            raise
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from Firebase Storage.
        
        Args:
            file_path: Path of the file to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            return False
    
    def generate_signed_url(
        self,
        file_path: str,
        expiration_minutes: int = 60,
        method: str = 'GET'
    ) -> str:
        """
        Generate a signed URL for temporary access to a file.
        
        Args:
            file_path: Path of the file
            expiration_minutes: URL expiration time in minutes
            method: HTTP method ('GET' for download, 'PUT' for upload)
            
        Returns:
            Signed URL
        """
        try:
            blob = self.bucket.blob(file_path)
            
            expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
            
            url = blob.generate_signed_url(
                version='v4',
                expiration=expiration_time,
                method=method
            )
            
            return url
        except Exception as e:
            logger.error(f"Error generating signed URL for {file_path}: {str(e)}")
            raise
    
    def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file.
        
        Args:
            file_path: Path of the file
            
        Returns:
            File metadata or None if file doesn't exist
        """
        try:
            blob = self.bucket.blob(file_path)
            blob.reload()
            
            return {
                'name': blob.name,
                'size': blob.size,
                'content_type': blob.content_type,
                'created': blob.time_created,
                'updated': blob.updated,
                'metadata': blob.metadata,
                'md5_hash': blob.md5_hash,
                'etag': blob.etag
            }
        except Exception as e:
            logger.error(f"Error getting metadata for {file_path}: {str(e)}")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            file_path: Path of the file
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            blob = self.bucket.blob(file_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking if file exists {file_path}: {str(e)}")
            return False


# Global instance
storage_manager = StorageManager()