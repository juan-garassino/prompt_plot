"""
File operation utilities for PromptPlot v2.0

This module provides common file operations, path handling, and file format
detection utilities used throughout the PromptPlot system.
"""

import os
import shutil
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple, Generator
from datetime import datetime
from enum import Enum
import mimetypes
import hashlib

from .logging import get_logger


class FileType(str, Enum):
    """Supported file types"""
    GCODE = "gcode"
    SVG = "svg"
    DXF = "dxf"
    HPGL = "hpgl"
    JSON = "json"
    IMAGE = "image"
    TEXT = "text"
    UNKNOWN = "unknown"


class FileOperation(str, Enum):
    """File operation types for logging"""
    READ = "read"
    WRITE = "write"
    COPY = "copy"
    MOVE = "move"
    DELETE = "delete"
    CREATE = "create"


logger = get_logger("file_helpers")


def detect_file_type(filepath: Union[str, Path]) -> FileType:
    """Detect file type based on extension and content
    
    Args:
        filepath: Path to file
        
    Returns:
        Detected file type
    """
    path = Path(filepath)
    extension = path.suffix.lower()
    
    # Map extensions to file types
    extension_map = {
        '.gcode': FileType.GCODE,
        '.nc': FileType.GCODE,
        '.cnc': FileType.GCODE,
        '.svg': FileType.SVG,
        '.dxf': FileType.DXF,
        '.hpgl': FileType.HPGL,
        '.plt': FileType.HPGL,
        '.json': FileType.JSON,
        '.png': FileType.IMAGE,
        '.jpg': FileType.IMAGE,
        '.jpeg': FileType.IMAGE,
        '.bmp': FileType.IMAGE,
        '.gif': FileType.IMAGE,
        '.txt': FileType.TEXT,
    }
    
    if extension in extension_map:
        return extension_map[extension]
    
    # Try to detect by content if extension is unknown
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read(1000)  # Read first 1KB
            
        # Check for G-code patterns
        if any(line.strip().startswith(('G', 'M', 'T', 'F', 'S')) for line in content.split('\n')[:10]):
            return FileType.GCODE
        
        # Check for SVG
        if '<svg' in content.lower() or '<?xml' in content.lower():
            return FileType.SVG
        
        # Check for JSON
        try:
            json.loads(content)
            return FileType.JSON
        except json.JSONDecodeError:
            pass
            
    except (UnicodeDecodeError, IOError):
        # Binary file or read error
        pass
    
    return FileType.UNKNOWN


def ensure_directory(directory: Union[str, Path]) -> Path:
    """Ensure directory exists, create if necessary
    
    Args:
        directory: Directory path
        
    Returns:
        Path object for the directory
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path}")
    return path


def safe_filename(filename: str, max_length: int = 255) -> str:
    """Create safe filename by removing invalid characters
    
    Args:
        filename: Original filename
        max_length: Maximum filename length
        
    Returns:
        Safe filename
    """
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    safe_name = ''.join(c for c in filename if c not in invalid_chars)
    
    # Replace spaces with underscores
    safe_name = safe_name.replace(' ', '_')
    
    # Truncate if too long
    if len(safe_name) > max_length:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:max_length - len(ext)] + ext
    
    return safe_name


def generate_timestamp_filename(base_name: str, extension: str = "", include_microseconds: bool = False) -> str:
    """Generate filename with timestamp
    
    Args:
        base_name: Base name for file
        extension: File extension (with or without dot)
        include_microseconds: Include microseconds in timestamp
        
    Returns:
        Filename with timestamp
    """
    if include_microseconds:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    
    return f"{base_name}_{timestamp}{extension}"


def read_file_safe(filepath: Union[str, Path], encoding: str = 'utf-8', fallback_encoding: str = 'latin-1') -> str:
    """Safely read file with encoding fallback
    
    Args:
        filepath: Path to file
        encoding: Primary encoding to try
        fallback_encoding: Fallback encoding if primary fails
        
    Returns:
        File content as string
        
    Raises:
        IOError: If file cannot be read
    """
    path = Path(filepath)
    
    try:
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
        logger.debug(f"Read file with {encoding} encoding: {path}")
        return content
    except UnicodeDecodeError:
        logger.warning(f"Failed to read with {encoding}, trying {fallback_encoding}: {path}")
        try:
            with open(path, 'r', encoding=fallback_encoding) as f:
                content = f.read()
            logger.debug(f"Read file with {fallback_encoding} encoding: {path}")
            return content
        except UnicodeDecodeError as e:
            logger.error(f"Failed to read file with any encoding: {path}")
            raise IOError(f"Cannot decode file {path}: {e}")


def write_file_safe(filepath: Union[str, Path], content: str, encoding: str = 'utf-8', backup: bool = True) -> None:
    """Safely write file with optional backup
    
    Args:
        filepath: Path to file
        content: Content to write
        encoding: Text encoding
        backup: Create backup if file exists
        
    Raises:
        IOError: If file cannot be written
    """
    path = Path(filepath)
    
    # Create backup if requested and file exists
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + '.bak')
        shutil.copy2(path, backup_path)
        logger.debug(f"Created backup: {backup_path}")
    
    # Ensure parent directory exists
    ensure_directory(path.parent)
    
    # Write to temporary file first, then move
    with tempfile.NamedTemporaryFile(mode='w', encoding=encoding, delete=False, 
                                     dir=path.parent, prefix=path.stem + '_tmp_') as tmp_file:
        tmp_file.write(content)
        tmp_path = Path(tmp_file.name)
    
    # Atomic move
    shutil.move(tmp_path, path)
    logger.debug(f"Wrote file: {path}")


def copy_file_safe(src: Union[str, Path], dst: Union[str, Path], overwrite: bool = False) -> None:
    """Safely copy file with overwrite protection
    
    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Allow overwriting existing files
        
    Raises:
        IOError: If copy operation fails
        FileExistsError: If destination exists and overwrite is False
    """
    src_path = Path(src)
    dst_path = Path(dst)
    
    if not src_path.exists():
        raise IOError(f"Source file does not exist: {src_path}")
    
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"Destination file exists: {dst_path}")
    
    # Ensure destination directory exists
    ensure_directory(dst_path.parent)
    
    shutil.copy2(src_path, dst_path)
    logger.debug(f"Copied file: {src_path} -> {dst_path}")


def move_file_safe(src: Union[str, Path], dst: Union[str, Path], overwrite: bool = False) -> None:
    """Safely move file with overwrite protection
    
    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Allow overwriting existing files
        
    Raises:
        IOError: If move operation fails
        FileExistsError: If destination exists and overwrite is False
    """
    src_path = Path(src)
    dst_path = Path(dst)
    
    if not src_path.exists():
        raise IOError(f"Source file does not exist: {src_path}")
    
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"Destination file exists: {dst_path}")
    
    # Ensure destination directory exists
    ensure_directory(dst_path.parent)
    
    shutil.move(src_path, dst_path)
    logger.debug(f"Moved file: {src_path} -> {dst_path}")


def delete_file_safe(filepath: Union[str, Path], backup: bool = False) -> None:
    """Safely delete file with optional backup
    
    Args:
        filepath: Path to file to delete
        backup: Create backup before deletion
        
    Raises:
        IOError: If deletion fails
    """
    path = Path(filepath)
    
    if not path.exists():
        logger.warning(f"File does not exist for deletion: {path}")
        return
    
    if backup:
        backup_path = path.with_suffix(path.suffix + '.deleted')
        shutil.copy2(path, backup_path)
        logger.debug(f"Created backup before deletion: {backup_path}")
    
    path.unlink()
    logger.debug(f"Deleted file: {path}")


def get_file_info(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Get comprehensive file information
    
    Args:
        filepath: Path to file
        
    Returns:
        Dictionary with file information
    """
    path = Path(filepath)
    
    if not path.exists():
        return {"exists": False, "path": str(path)}
    
    stat = path.stat()
    
    info = {
        "exists": True,
        "path": str(path),
        "name": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "size_bytes": stat.st_size,
        "size_mb": stat.st_size / (1024 * 1024),
        "created": datetime.fromtimestamp(stat.st_ctime),
        "modified": datetime.fromtimestamp(stat.st_mtime),
        "accessed": datetime.fromtimestamp(stat.st_atime),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "file_type": detect_file_type(path),
    }
    
    # Add MIME type if available
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type:
        info["mime_type"] = mime_type
    
    return info


def calculate_file_hash(filepath: Union[str, Path], algorithm: str = 'md5') -> str:
    """Calculate file hash
    
    Args:
        filepath: Path to file
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')
        
    Returns:
        Hex digest of file hash
    """
    path = Path(filepath)
    
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    elif algorithm == 'sha256':
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def find_files(directory: Union[str, Path], 
               pattern: str = "*", 
               file_type: Optional[FileType] = None,
               recursive: bool = True) -> List[Path]:
    """Find files matching criteria
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        file_type: Filter by file type
        recursive: Search recursively
        
    Returns:
        List of matching file paths
    """
    path = Path(directory)
    
    if not path.exists():
        return []
    
    if recursive:
        files = path.rglob(pattern)
    else:
        files = path.glob(pattern)
    
    # Filter by file type if specified
    if file_type:
        files = [f for f in files if f.is_file() and detect_file_type(f) == file_type]
    else:
        files = [f for f in files if f.is_file()]
    
    return sorted(files)


def cleanup_temp_files(directory: Union[str, Path], max_age_hours: int = 24) -> int:
    """Clean up temporary files older than specified age
    
    Args:
        directory: Directory to clean
        max_age_hours: Maximum age in hours
        
    Returns:
        Number of files deleted
    """
    path = Path(directory)
    
    if not path.exists():
        return 0
    
    cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
    deleted_count = 0
    
    for file_path in path.iterdir():
        if file_path.is_file():
            # Check for temp file patterns
            if ('tmp' in file_path.name.lower() or 
                file_path.name.startswith('.') or
                file_path.suffix == '.bak'):
                
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted temp file: {file_path}")
                    except OSError as e:
                        logger.warning(f"Failed to delete temp file {file_path}: {e}")
    
    return deleted_count


def archive_old_files(directory: Union[str, Path], 
                      archive_dir: Union[str, Path],
                      max_age_days: int = 30,
                      compress: bool = True) -> int:
    """Archive old files to separate directory
    
    Args:
        directory: Source directory
        archive_dir: Archive directory
        max_age_days: Maximum age in days
        compress: Compress archived files
        
    Returns:
        Number of files archived
    """
    src_path = Path(directory)
    archive_path = Path(archive_dir)
    
    if not src_path.exists():
        return 0
    
    ensure_directory(archive_path)
    cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
    archived_count = 0
    
    for file_path in src_path.iterdir():
        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
            # Create archive filename with timestamp
            archive_name = f"{file_path.stem}_{datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y%m%d')}{file_path.suffix}"
            archive_file = archive_path / archive_name
            
            try:
                if compress and file_path.suffix in ['.txt', '.gcode', '.svg', '.json']:
                    import gzip
                    with open(file_path, 'rb') as f_in:
                        with gzip.open(archive_file.with_suffix(archive_file.suffix + '.gz'), 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                else:
                    shutil.copy2(file_path, archive_file)
                
                file_path.unlink()
                archived_count += 1
                logger.debug(f"Archived file: {file_path} -> {archive_file}")
                
            except OSError as e:
                logger.warning(f"Failed to archive file {file_path}: {e}")
    
    return archived_count


def batch_rename_files(directory: Union[str, Path], 
                       pattern: str,
                       replacement: str,
                       dry_run: bool = True) -> List[Tuple[Path, Path]]:
    """Batch rename files using pattern replacement
    
    Args:
        directory: Directory containing files
        pattern: Pattern to match in filenames
        replacement: Replacement string
        dry_run: Only return what would be renamed
        
    Returns:
        List of (old_path, new_path) tuples
    """
    path = Path(directory)
    renames = []
    
    if not path.exists():
        return renames
    
    for file_path in path.iterdir():
        if file_path.is_file() and pattern in file_path.name:
            new_name = file_path.name.replace(pattern, replacement)
            new_path = file_path.parent / new_name
            
            renames.append((file_path, new_path))
            
            if not dry_run:
                try:
                    file_path.rename(new_path)
                    logger.debug(f"Renamed file: {file_path} -> {new_path}")
                except OSError as e:
                    logger.warning(f"Failed to rename file {file_path}: {e}")
    
    return renames