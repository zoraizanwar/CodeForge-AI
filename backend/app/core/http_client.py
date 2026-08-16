import ssl
import logging
import httpx

logger = logging.getLogger(__name__)

try:
    import certifi
    CA_FILE = certifi.where()
except ImportError:
    CA_FILE = None

def get_httpx_client(timeout: float = 30.0, follow_redirects: bool = False) -> httpx.AsyncClient:
    """
    Returns a robust httpx.AsyncClient using certifi CA bundle on Windows environments.
    Falls back gracefully if local certificate verification is misconfigured.
    """
    if CA_FILE:
        try:
            ssl_context = ssl.create_default_context(cafile=CA_FILE)
            return httpx.AsyncClient(verify=ssl_context, timeout=timeout, follow_redirects=follow_redirects)
        except Exception as e:
            logger.warning(f"Failed to create SSL context with certifi: {str(e)}")

    # Fallback to unverified SSL client for local development environment compatibility
    return httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=follow_redirects)
