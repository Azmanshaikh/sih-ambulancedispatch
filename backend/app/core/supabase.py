from supabase import create_client, Client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client | None:
    """
    Initializes and returns the Supabase client.
    Returns None if SUPABASE_URL or SUPABASE_SERVICE_KEY is not configured.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        logger.warning("Supabase URL or Service Key missing. Supabase client will not be initialized.")
        return None
        
    try:
        supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        return supabase
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None

# Singleton instance
supabase_client = get_supabase_client()
