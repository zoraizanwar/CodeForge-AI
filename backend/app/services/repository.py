import os
import zipfile
import shutil
import logging
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import io
import uuid

from app.core.config import settings
from app.models.repository import Repository
from app.services.github import GitHubService

logger = logging.getLogger(__name__)

# Excluded folders from indexing and file tree Walks
EXCLUDED_FOLDERS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
}

# Excluded sensitive/binary files or extensions
EXCLUDED_EXTENSIONS = {
    ".pem",
    ".key",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".zip",
    ".tar",
    ".gz",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
}

EXCLUDED_FILES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

def get_safe_workspace_path(repo_local_path: str, relative_path: str = "") -> str:
    """
    Validates that a target path lies strictly inside the repository's local folder.
    Blocks directory traversals, symlink escapes, and absolute path injections.
    """
    if not repo_local_path:
        raise PermissionError("Invalid workspace path.")
        
    # Check for empty relative path (resolved to base path)
    if not relative_path:
        return os.path.realpath(repo_local_path)

    # Do not strip leading slashes before running isabs check
    if os.path.isabs(relative_path):
        raise PermissionError("Absolute paths are forbidden.")

    # Normalize separators for check consistency
    normalized_rel = relative_path.replace("\\", "/")
    
    # Reject Unix absolute paths, Windows absolute paths, UNC paths, and drive prefixes
    if (
        normalized_rel.startswith("/") or 
        normalized_rel.startswith("//") or 
        ":" in normalized_rel or
        normalized_rel.startswith("\\\\")
    ):
        raise PermissionError("Absolute, UNC, or drive paths are forbidden.")

    # Reject traversal sequences
    parts = [p for p in normalized_rel.split("/") if p]
    if ".." in parts:
        raise PermissionError("Directory traversal components are forbidden.")

    # Resolve and check boundary bounds
    base_path = os.path.realpath(repo_local_path)
    target_path = os.path.realpath(os.path.join(base_path, relative_path))
    
    # Use commonpath boundary check to prevent sibling/prefix confusion (e.g. repo vs repo_evil)
    try:
        common = os.path.commonpath([base_path, target_path])
        if os.path.realpath(common) != base_path:
            raise PermissionError("Target path lies outside the repository boundary.")
    except Exception as e:
        raise PermissionError(f"Security validation boundary check failed: {str(e)}")
        
    return target_path

def is_binary_file(file_path: str) -> bool:
    """Checks if a file is binary by scanning the first 1024 bytes for null bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except Exception:
        return True  # Treat unreadable files as binary/unsafe

def should_exclude_file(file_name: str) -> bool:
    """Returns True if the file matches sensitive file lists or excluded extensions."""
    file_lower = file_name.lower()
    
    # Check exact names
    if file_lower in EXCLUDED_FILES or file_lower.startswith(".env"):
        return True
        
    # Check extensions
    _, ext = os.path.splitext(file_lower)
    if ext in EXCLUDED_EXTENSIONS:
        return True
        
    return False

class RepositoryService:
    @staticmethod
    def get_user_workspace_root(user_id: uuid.UUID) -> str:
        """Returns the absolute path to the user's isolated workspace directory."""
        workspace_root = settings.workspace_root_resolved
        path = os.path.join(workspace_root, f"user_{user_id}")
        return os.path.abspath(path)

    @staticmethod
    def get_repository_workspace(user_id: uuid.UUID, github_repo_id: int) -> str:
        """Returns the absolute path to a specific repository workspace folder."""
        user_root = RepositoryService.get_user_workspace_root(user_id)
        path = os.path.join(user_root, f"repo_{github_repo_id}")
        return os.path.abspath(path)

    @staticmethod
    def extract_zip_securely(zip_bytes: bytes, target_dir: str):
        """
        Extracts repository zipball contents with strict bounds verification:
        - Max total extracted size: 50MB
        - Max file count: 1000 files
        - Traversal protection on each path entry
        - Skip sensitive folder structures like .git
        """
        # Ensure target directory exists and is absolute
        target_dir = os.path.realpath(target_dir)
        os.makedirs(target_dir, exist_ok=True)
        
        # Read from bytes in-memory zip structure
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                infolist = z.infolist()
                
                # Check limits
                if len(infolist) > 1000:
                    raise ValueError("ZIP archive contains too many files (maximum 1000).")
                    
                total_size = 0
                for info in infolist:
                    total_size += info.file_size
                if total_size > 50 * 1024 * 1024:
                     raise ValueError("ZIP archive extracted size exceeds limit of 50MB.")
                     
                # Verify and extract files
                for info in infolist:
                    # Sanitize slashes and check traversal patterns
                    name = info.filename.replace("\\", "/")
                    
                    # Reject absolute paths, UNC paths, and drive prefixes in zip file names
                    if name.startswith("/") or name.startswith("//") or ":" in name or name.startswith("\\\\"):
                        continue
                    
                    # Skip root folder segments if needed, but verify path
                    parts = [p for p in name.split("/") if p]
                    if not parts:
                        continue
                        
                    # Trap traversal elements
                    if ".." in parts or "." in parts[:1]:
                        # Reject directory traversals or relative paths
                        continue
                        
                    # Skip files inside control folders (like .git)
                    if any(p in EXCLUDED_FOLDERS for p in parts):
                        continue
                        
                    # Resolve destination path
                    dest_path = os.path.realpath(os.path.join(target_dir, *parts))
                    
                    # Verify boundary containment
                    try:
                        common = os.path.commonpath([target_dir, dest_path])
                        if os.path.realpath(common) != target_dir:
                            raise PermissionError("ZIP extraction traversal attempt blocked.")
                    except Exception:
                        continue  # Skip invalid paths
                        
                    # Create parent folder structure if missing
                    if info.is_dir():
                        os.makedirs(dest_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with z.open(info) as source, open(dest_path, "wb") as dest:
                            shutil.copyfileobj(source, dest)
                            
        except zipfile.BadZipFile as e:
            raise ValueError(f"Malformed ZIP archive: {str(e)}") from e

    @staticmethod
    def index_codebase(local_path: str) -> Dict[str, Any]:
        """
        Scans workspace directory recursively and parses file counts, language ratios,
        detected frameworks, and dependency files list.
        """
        languages_count = {}
        frameworks = set()
        dependency_files = []
        file_count = 0
        
        # Extensions language mapping
        ext_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".html": "HTML",
            ".css": "CSS",
            ".md": "Markdown",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
        }
        
        for root, dirs, files in os.walk(local_path):
            # Prune excluded folders in-place to prevent walking them
            dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS]
            
            for file in files:
                if should_exclude_file(file):
                    continue
                    
                file_path = os.path.join(root, file)
                if os.path.islink(file_path):
                    continue  # Ignore symlinks
                    
                file_count += 1
                _, ext = os.path.splitext(file.lower())
                
                # Language ratios detection
                if ext in ext_map:
                    lang = ext_map[ext]
                    languages_count[lang] = languages_count.get(lang, 0) + 1
                    
                # Framework configuration checks
                if file.lower() == "package.json":
                    dependency_files.append(file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            if "react" in content:
                                frameworks.add("React")
                            if "next" in content:
                                frameworks.add("Next.js")
                            if "vue" in content:
                                frameworks.add("Vue")
                    except Exception:
                        pass
                elif file.lower() in ["requirements.txt", "pyproject.toml"]:
                    dependency_files.append(file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().lower()
                            if "fastapi" in content:
                                frameworks.add("FastAPI")
                            if "django" in content:
                                frameworks.add("Django")
                            if "flask" in content:
                                frameworks.add("Flask")
                    except Exception:
                        pass
                elif file.lower() == "cargo.toml":
                    dependency_files.append(file)
                    frameworks.add("Rust Cargo")
                    
        # Calculate percentage split ratios
        total_matched_files = sum(languages_count.values())
        languages_percentages = {}
        if total_matched_files > 0:
            for lang, count in languages_count.items():
                languages_percentages[lang] = round((count / total_matched_files) * 100, 1)
                
        return {
            "languages": languages_percentages,
            "frameworks": list(frameworks),
            "dependency_files": dependency_files,
            "file_count": file_count
        }

    @classmethod
    async def import_repository_task(
        cls, 
        repo_db_id: uuid.UUID, 
        installation_id: int, 
        db: Session
    ):
        """
        Asynchronous background task managing the importing and indexing of repositories.
        Catches exceptions and marks statuses as failed with generic messages.
        """
        # Lookup repository record
        repo = db.query(Repository).filter(Repository.id == repo_db_id).first()
        if not repo:
            logger.error("Repository record %s not found in background import task", str(repo_db_id))
            return
            
        try:
            # 1. Fetch metadata directly from GitHub API
            github_service = GitHubService()
            details = await github_service.get_repository(installation_id, repo.github_repo_id)
            
            repo.name = details.get("name")
            repo.full_name = details.get("full_name")
            repo.owner = details.get("owner", {}).get("login")
            repo.default_branch = details.get("default_branch", "main")
            db.commit()
            
            # 2. Download zipball stream
            zip_bytes = await github_service.download_repository_zipball(
                installation_id=installation_id,
                owner=repo.owner,
                repo=repo.name,
                ref=repo.default_branch
            )
            
            # 3. Create isolated target folder
            workspace_dir = repo.local_path
            # Create a temporary extraction folder
            temp_extract_dir = os.path.join(os.path.dirname(workspace_dir), f"temp_{uuid.uuid4()}")
            cls.extract_zip_securely(zip_bytes, temp_extract_dir)
            
            # Find the root folder inside the extracted directory (GitHub zipballs contain a commit-hash root folder)
            extracted_roots = os.listdir(temp_extract_dir)
            source_dir = temp_extract_dir
            if extracted_roots:
                inner_dir = os.path.join(temp_extract_dir, extracted_roots[0])
                if os.path.isdir(inner_dir):
                    source_dir = inner_dir

            os.makedirs(workspace_dir, exist_ok=True)
            shutil.copytree(source_dir, workspace_dir, dirs_exist_ok=True)
            
            # Automatically unpack nested zip archives if present
            try:
                import zipfile
                for file_name in os.listdir(workspace_dir):
                    if file_name.endswith(".zip"):
                        zip_path = os.path.join(workspace_dir, file_name)
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            zf.extractall(workspace_dir)
            except Exception as zip_err:
                logger.warning(f"Could not extract nested zip file in {workspace_dir}: {zip_err}")
                
            # Clean up temp folder if it remains
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                
            # 4. Perform directory walking and indexing
            index_data = cls.index_codebase(workspace_dir)
            
            # 5. Save indexing results and update statuses
            repo.status = "indexed"
            repo.languages = index_data["languages"]
            repo.frameworks = index_data["frameworks"]
            repo.dependency_files = index_data["dependency_files"]
            repo.last_indexed_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()

            # Auto-enqueue analysis job for the repository
            try:
                from app.services.jobs import JobManager
                JobManager.enqueue_job(
                    db=db,
                    user_id=repo.user_id,
                    repository_id=repo.id,
                    job_type="analysis"
                )
            except Exception as analysis_enqueue_err:
                logger.warning(f"Failed to auto-enqueue analysis for repo {repo.id}: {str(analysis_enqueue_err)}")

            logger.info("Successfully imported and indexed repository: %s", repo.full_name)

            
        except Exception as e:
            logger.exception("Failed to import repository %s in background task", str(repo_db_id))
            try:
                db.rollback()
                # Re-query the repo in case the rollback removed a flushed-only record from tests
                repo = db.query(Repository).filter(Repository.id == repo_db_id).first()
                if repo:
                    repo.status = "failed"
                    repo.error_message = f"Background indexing failed: {str(e)}"
                    db.commit()
            except Exception as inner_err:
                logger.error("Failed to mark repository as failed: %s", str(inner_err))
