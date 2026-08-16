"""
Patch fingerprint helper for CodeForge AI Git & PR automation (Step 9).
Computes deterministic SHA-256 hashes of approved code changes.
"""
import hashlib
import json
from typing import List, Dict, Any


def compute_patch_hash(changes: List[Dict[str, Any]]) -> str:
    """
    Computes a SHA-256 hash string for a list of file change dictionaries.
    Ensures exact verification between approved, executed, and committed patches.
    """
    if not changes:
        return hashlib.sha256(b"empty").hexdigest()

    normalized = []
    for c in changes:
        normalized.append({
            "file_path": c.get("file_path", "").strip(),
            "operation": c.get("operation", "").strip().lower(),
            "proposed_content": c.get("proposed_content", "")
        })

    # Sort by file path to ensure deterministic order
    normalized.sort(key=lambda x: x["file_path"])

    dumped = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
