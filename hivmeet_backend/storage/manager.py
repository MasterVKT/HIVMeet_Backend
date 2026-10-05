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


def _requires_phase2_private_adapter(file_path: str) -> bool:
    """Keep KYC and profile-media paths out of this legacy generic adapter."""
    return isinstance(file_path, str) and file_path.startswith(('kyc/', 'profiles/'))


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
            The private object path. This legacy adapter never changes a blob
            ACL or emits a public URL.
        """
        if _requires_phase2_private_adapter(file_path):
            # Do not turn an obsolete caller into a path-bearing error/log.
            raise ValueError('private_media_requires_private_adapter')
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
            
            # Public profile objects are prohibited.  New profile media uses
            # profiles.private_storage; this compatibility adapter keeps every
            # object private if an older call site still reaches it.
            return file_path
                
        except Exception:
            logger.error("Storage upload failed")
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
        if _requires_phase2_private_adapter(base_path):
            raise ValueError('private_media_requires_private_adapter')
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
            
            try:
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
            except Exception:
                # The main object belongs to this upload attempt only. Remove
                # it when the thumbnail cannot be created.
                self.delete_file(main_path)
                raise
            
            return {
                'main': main_url,
                'thumbnail': thumb_url,
                'filename': filename
            }
            
        except Exception:
            logger.error("Storage image processing failed")
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
            logger.info("Storage object deleted")
            return True
        except Exception:
            logger.error("Storage object deletion failed")
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
        if _requires_phase2_private_adapter(file_path):
            # KYC PUT URLs and all profile-media reads are issued only by their
            # Phase-2 storage boundaries, never by this generic helper.
            raise ValueError('private_media_requires_private_adapter')
        try:
            blob = self.bucket.blob(file_path)
            
            expiration_time = datetime.utcnow() + timedelta(minutes=expiration_minutes)
            
            url = blob.generate_signed_url(
                version='v4',
                expiration=expiration_time,
                method=method
            )
            
            return url
        except Exception:
            logger.error("Storage signed URL generation failed")
            raise
    
    def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file.
        
        Args:
            file_path: Path of the file
            
        Returns:
            File metadata or None if file doesn't exist
        """
        if _requires_phase2_private_adapter(file_path):
            raise ValueError('private_media_requires_private_adapter')
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
        except Exception:
            logger.error("Storage metadata lookup failed")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            file_path: Path of the file
            
        Returns:
            True if file exists, False otherwise
        """
        if _requires_phase2_private_adapter(file_path):
            raise ValueError('private_media_requires_private_adapter')
        try:
            blob = self.bucket.blob(file_path)
            return blob.exists()
        except Exception:
            logger.error("Storage existence check failed")
            return False


# Global instance
storage_manager = StorageManager()
