import asyncio
import logging
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

logger = logging.getLogger(__name__)

def get_or_create_event_loop():
    """
    Get the current event loop or create a new one if none exists or the current one is closed.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            logger.debug("Current event loop is closed, creating a new one.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        logger.debug("No event loop found, creating a new one.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def run_async(coro):
    """
    Helper to run async coroutines in Streamlit.
    Handles existing event loops using nest_asyncio.
    
    Args:
        coro: The coroutine to execute.
        
    Returns:
        The result of the coroutine.
    """
    loop = get_or_create_event_loop()
    return loop.run_until_complete(coro)
