"""
Hashing utilities for model and file integrity checks.
"""

import hashlib
import os
from typing import Optional


def calculate_md5(file_path: str, chunk_size: int = 8192) -> str:
    """
    Calculate MD5 hash of a file.
    
    Args:
        file_path: Path to file
        chunk_size: Size of chunks to read at a time
        
    Returns:
        MD5 hash as hexadecimal string
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    md5_hash = hashlib.md5()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
    
    return md5_hash.hexdigest()


def calculate_sha256(file_path: str, chunk_size: int = 8192) -> str:
    """
    Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to file
        chunk_size: Size of chunks to read at a time
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    sha256_hash = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


def calculate_string_hash(text: str, algorithm: str = 'md5') -> str:
    """
    Calculate hash of a string.
    
    Args:
        text: Input string
        algorithm: Hash algorithm ('md5' or 'sha256')
        
    Returns:
        Hash as hexadecimal string
    """
    if algorithm == 'md5':
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def get_model_hash(model_path: Optional[str] = None, 
                  algorithm_description: Optional[str] = None) -> str:
    """
    Get hash for model file or algorithm description.
    
    Args:
        model_path: Path to model file (for ML models)
        algorithm_description: Description of classical algorithm
        
    Returns:
        Hash string
    """
    if model_path and os.path.exists(model_path):
        return calculate_md5(model_path)
    elif algorithm_description:
        return calculate_string_hash(algorithm_description)
    else:
        # Default for classical Stage-1 algorithm
        default_description = "classical_logratio_otsu_morphology_v1.0"
        return calculate_string_hash(default_description)


def verify_file_integrity(file_path: str, expected_hash: str, 
                         algorithm: str = 'md5') -> bool:
    """
    Verify file integrity against expected hash.
    
    Args:
        file_path: Path to file
        expected_hash: Expected hash value
        algorithm: Hash algorithm to use
        
    Returns:
        True if hash matches
    """
    try:
        if algorithm == 'md5':
            actual_hash = calculate_md5(file_path)
        elif algorithm == 'sha256':
            actual_hash = calculate_sha256(file_path)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        return actual_hash.lower() == expected_hash.lower()
    
    except Exception:
        return False


def save_hash_file(hash_value: str, output_path: str, 
                  description: Optional[str] = None) -> None:
    """
    Save hash to file with optional description.
    
    Args:
        hash_value: Hash value to save
        output_path: Output file path
        description: Optional description
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        if description:
            f.write(f"# {description}\n")
        f.write(hash_value)


def load_hash_file(hash_file_path: str) -> str:
    """
    Load hash from file, ignoring comments.
    
    Args:
        hash_file_path: Path to hash file
        
    Returns:
        Hash value
    """
    with open(hash_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    
    raise ValueError("No hash found in file")