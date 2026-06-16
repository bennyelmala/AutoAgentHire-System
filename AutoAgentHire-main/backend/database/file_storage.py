"""
File Storage Manager for AutoAgentHire
Handles resume uploads, screenshots, cover letters, and reports
"""

import os
import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Dict, List, Any
from datetime import datetime, timedelta
import uuid as uuid_lib

# Optional S3 imports with proper type handling
boto3: Any = None
ClientError: Any = Exception
S3_AVAILABLE = False

try:
    import boto3 as _boto3  # type: ignore[import-not-found]
    from botocore.exceptions import ClientError as _ClientError  # type: ignore[import-not-found]
    boto3 = _boto3
    ClientError = _ClientError
    S3_AVAILABLE = True
except ImportError:
    pass


class FileStorageManager:
    """
    Centralized file storage manager supporting local and cloud storage.
    
    Directory Structure:
    data/
    ├── resumes/
    │   └── {user_id}/
    │       └── {resume_uuid}.pdf
    ├── cover_letters/
    │   └── {agent_run_id}/
    │       └── {application_id}.txt
    ├── screenshots/
    │   └── {agent_run_id}/
    │       └── {timestamp}.png
    └── reports/
        └── {user_id}/
            └── {report_uuid}.pdf
    """
    
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        
        # Define storage directories
        self.resume_dir = self.base_dir / "resumes"
        self.cover_letter_dir = self.base_dir / "cover_letters"
        self.screenshot_dir = self.base_dir / "screenshots"
        self.report_dir = self.base_dir / "reports"
        self.temp_dir = self.base_dir / "temp"
        
        # Create directories
        for dir_path in [
            self.resume_dir, 
            self.cover_letter_dir, 
            self.screenshot_dir, 
            self.report_dir,
            self.temp_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Storage provider configuration
        self.storage_provider = os.getenv('STORAGE_PROVIDER', 'local')
        
        # S3 client (if configured)
        self.s3_client = None
        self.s3_bucket = os.getenv('S3_BUCKET')
        if self.storage_provider == 's3' and S3_AVAILABLE and self.s3_bucket:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                    region_name=os.getenv('AWS_REGION', 'us-east-1')
                )
                print("✅ S3 storage configured")
            except Exception as e:
                print(f"⚠️ S3 configuration failed: {e}")
    
    def _calculate_file_hash(self, file: BinaryIO) -> str:
        """Calculate SHA-256 hash of file content"""
        file.seek(0)
        hash_obj = hashlib.sha256()
        for chunk in iter(lambda: file.read(8192), b''):
            hash_obj.update(chunk)
        file.seek(0)
        return hash_obj.hexdigest()
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename"""
        ext = Path(filename).suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    def save_resume(
        self, 
        user_id: int, 
        file: BinaryIO, 
        filename: str
    ) -> Dict:
        """
        Save resume file and return file metadata.
        
        Args:
            user_id: User ID
            file: File object
            filename: Original filename
            
        Returns:
            Dict with file_path, file_hash, storage_url, etc.
        """
        # Generate unique ID
        resume_uuid = str(uuid_lib.uuid4())
        
        # Calculate file hash (for deduplication)
        file_hash = self._calculate_file_hash(file)
        
        # Get file info
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        ext = Path(filename).suffix.lower()
        
        # Create user directory
        user_dir = self.resume_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        # Save file locally
        file_path = user_dir / f"{resume_uuid}{ext}"
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file, f)
        
        # Upload to S3 if configured
        storage_url = str(file_path)
        if self.s3_client and self.s3_bucket:
            try:
                s3_key = f"resumes/{user_id}/{resume_uuid}{ext}"
                self.s3_client.upload_file(
                    str(file_path),
                    self.s3_bucket,
                    s3_key,
                    ExtraArgs={'ContentType': self._get_mime_type(filename)}
                )
                storage_url = f"s3://{self.s3_bucket}/{s3_key}"
            except Exception as e:
                print(f"⚠️ S3 upload failed: {e}")
        
        return {
            "uuid": resume_uuid,
            "filename": filename,
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "file_type": ext.lstrip('.'),
            "file_hash": file_hash,
            "mime_type": self._get_mime_type(filename),
            "storage_provider": self.storage_provider,
            "storage_url": storage_url,
        }
    
    def save_cover_letter(
        self, 
        agent_run_id: int, 
        application_id: int, 
        content: str
    ) -> str:
        """
        Save AI-generated cover letter.
        
        Args:
            agent_run_id: Agent run ID
            application_id: Application ID
            content: Cover letter text
            
        Returns:
            File path
        """
        # Create directory
        run_dir = self.cover_letter_dir / str(agent_run_id)
        run_dir.mkdir(exist_ok=True)
        
        # Save file
        file_path = run_dir / f"{application_id}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
    
    def save_screenshot(
        self, 
        agent_run_id: int, 
        screenshot_data: bytes, 
        description: str = ""
    ) -> str:
        """
        Save error screenshot.
        
        Args:
            agent_run_id: Agent run ID
            screenshot_data: PNG image bytes
            description: Optional description for filename
            
        Returns:
            File path
        """
        # Create directory
        run_dir = self.screenshot_dir / str(agent_run_id)
        run_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_desc = "".join(c if c.isalnum() else "_" for c in description[:30])
        filename = f"{timestamp}_{safe_desc}.png" if description else f"{timestamp}.png"
        
        # Save file
        file_path = run_dir / filename
        with open(file_path, 'wb') as f:
            f.write(screenshot_data)
        
        return str(file_path)
    
    def save_report(
        self, 
        user_id: int, 
        report_data: bytes, 
        report_type: str = "summary",
        extension: str = "pdf"
    ) -> Dict:
        """
        Save generated report.
        
        Args:
            user_id: User ID
            report_data: Report content bytes
            report_type: Type of report (summary, detailed, etc.)
            extension: File extension (pdf, xlsx, etc.)
            
        Returns:
            Dict with file info
        """
        # Generate unique ID
        report_uuid = str(uuid_lib.uuid4())
        
        # Create directory
        user_dir = self.report_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{timestamp}.{extension}"
        
        # Save file
        file_path = user_dir / f"{report_uuid}.{extension}"
        with open(file_path, 'wb') as f:
            f.write(report_data)
        
        return {
            "uuid": report_uuid,
            "filename": filename,
            "file_path": str(file_path),
            "file_size_bytes": len(report_data),
            "file_type": extension,
        }
    
    def get_file(self, file_path: str) -> Optional[bytes]:
        """
        Read file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            File content bytes or None
        """
        path = Path(file_path)
        if path.exists():
            with open(path, 'rb') as f:
                return f.read()
        return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if deleted, False otherwise
        """
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def cleanup_old_screenshots(self, days: int = 30):
        """
        Delete screenshots older than specified days.
        
        Args:
            days: Number of days to keep screenshots
        """
        cutoff = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for run_dir in self.screenshot_dir.iterdir():
            if run_dir.is_dir():
                for screenshot in run_dir.glob("*.png"):
                    if datetime.fromtimestamp(screenshot.stat().st_mtime) < cutoff:
                        screenshot.unlink()
                        deleted_count += 1
                
                # Remove empty directories
                if not any(run_dir.iterdir()):
                    run_dir.rmdir()
        
        print(f"🧹 Cleaned up {deleted_count} old screenshots")
    
    def cleanup_old_cover_letters(self, days: int = 90):
        """
        Delete cover letters older than specified days.
        
        Args:
            days: Number of days to keep cover letters
        """
        cutoff = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for run_dir in self.cover_letter_dir.iterdir():
            if run_dir.is_dir():
                for letter in run_dir.glob("*.txt"):
                    if datetime.fromtimestamp(letter.stat().st_mtime) < cutoff:
                        letter.unlink()
                        deleted_count += 1
                
                # Remove empty directories
                if not any(run_dir.iterdir()):
                    run_dir.rmdir()
        
        print(f"🧹 Cleaned up {deleted_count} old cover letters")
    
    def get_user_files(self, user_id: int) -> Dict[str, List[Dict]]:
        """
        Get all files for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with lists of files by category
        """
        files = {
            "resumes": [],
            "reports": []
        }
        
        # Get resumes
        resume_dir = self.resume_dir / str(user_id)
        if resume_dir.exists():
            for file in resume_dir.iterdir():
                if file.is_file():
                    files["resumes"].append({
                        "filename": file.name,
                        "file_path": str(file),
                        "size_bytes": file.stat().st_size,
                        "created_at": datetime.fromtimestamp(file.stat().st_ctime).isoformat(),
                    })
        
        # Get reports
        report_dir = self.report_dir / str(user_id)
        if report_dir.exists():
            for file in report_dir.iterdir():
                if file.is_file():
                    files["reports"].append({
                        "filename": file.name,
                        "file_path": str(file),
                        "size_bytes": file.stat().st_size,
                        "created_at": datetime.fromtimestamp(file.stat().st_ctime).isoformat(),
                    })
        
        return files
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        def get_dir_size(path: Path) -> int:
            total = 0
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
            return total
        
        def count_files(path: Path) -> int:
            if path.exists():
                return len(list(path.rglob("*")))
            return 0
        
        return {
            "storage_provider": self.storage_provider,
            "resumes": {
                "count": count_files(self.resume_dir),
                "size_bytes": get_dir_size(self.resume_dir),
            },
            "cover_letters": {
                "count": count_files(self.cover_letter_dir),
                "size_bytes": get_dir_size(self.cover_letter_dir),
            },
            "screenshots": {
                "count": count_files(self.screenshot_dir),
                "size_bytes": get_dir_size(self.screenshot_dir),
            },
            "reports": {
                "count": count_files(self.report_dir),
                "size_bytes": get_dir_size(self.report_dir),
            },
        }


# Global file storage instance
file_storage = FileStorageManager()


# Convenience functions
def save_resume(user_id: int, file: BinaryIO, filename: str) -> Dict:
    """Save a resume file"""
    return file_storage.save_resume(user_id, file, filename)


def save_screenshot(agent_run_id: int, data: bytes, description: str = "") -> str:
    """Save a screenshot"""
    return file_storage.save_screenshot(agent_run_id, data, description)


def get_file(file_path: str) -> Optional[bytes]:
    """Get file content"""
    return file_storage.get_file(file_path)
