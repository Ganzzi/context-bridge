"""UI styling utilities for consistent look and feel."""

import streamlit as st


def apply_custom_css():
    """Apply custom CSS styling to the Streamlit app."""
    st.markdown(
        """
        <style>
        /* Main container styling */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Card styling */
        .stCard {
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        /* Button styling */
        .stButton>button {
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        
        /* Success message styling */
        .success-message {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            padding: 0.75rem 1.25rem;
            margin: 1rem 0;
            color: #155724;
        }
        
        /* Error message styling */
        .error-message {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 0.75rem 1.25rem;
            margin: 1rem 0;
            color: #721c24;
        }
        
        /* Info message styling */
        .info-message {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 5px;
            padding: 0.75rem 1.25rem;
            margin: 1rem 0;
            color: #0c5460;
        }
        
        /* Metric styling */
        [data-testid="stMetric"] {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        /* DataFrame styling */
        .dataframe {
            font-size: 14px;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }
        
        /* Title styling */
        h1 {
            color: #2c3e50;
            font-weight: 600;
        }
        
        h2, h3 {
            color: #34495e;
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 1rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            border-radius: 5px 5px 0 0;
            padding: 0.5rem 1rem;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            font-weight: 600;
            border-radius: 5px;
        }
        
        /* Loading spinner color */
        .stSpinner > div {
            border-color: #3498db;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_success(message: str):
    """Display a styled success message."""
    st.markdown(f'<div class="success-message">✅ {message}</div>', unsafe_allow_html=True)


def show_error(message: str):
    """Display a styled error message."""
    st.markdown(f'<div class="error-message">❌ {message}</div>', unsafe_allow_html=True)


def show_info(message: str):
    """Display a styled info message."""
    st.markdown(f'<div class="info-message">ℹ️ {message}</div>', unsafe_allow_html=True)


def show_loading(message: str = "Loading..."):
    """Display a loading indicator with message."""
    with st.spinner(message):
        yield


def create_metric_card(
    label: str, value: str | int, delta: str | None = None, help_text: str | None = None
):
    """Create a styled metric card."""
    st.metric(label=label, value=value, delta=delta, help=help_text)


def add_tooltip(text: str, tooltip: str):
    """Add a tooltip to text."""
    return f'<span title="{tooltip}" style="cursor: help; border-bottom: 1px dotted #999;">{text}</span>'


# Error Handling Utilities


def handle_error(error: Exception, context: str = "Operation", show_details: bool = False):
    """
    Handle and display errors in a user-friendly way.

    Args:
        error: The exception that occurred
        context: Context of where the error occurred (e.g., "Document Loading")
        show_details: Whether to show technical error details in an expander
    """
    import traceback

    # Determine error type and message
    error_type = type(error).__name__
    error_message = str(error)

    # User-friendly messages for common errors
    friendly_messages = {
        "ConnectionError": "Unable to connect to the database. Please check your connection.",
        "TimeoutError": "The operation took too long. Please try again.",
        "ValueError": "Invalid input provided. Please check your data.",
        "PermissionError": "Permission denied. Please check your access rights.",
        "FileNotFoundError": "Required file not found.",
    }

    # Get friendly message or use generic one
    friendly_message = friendly_messages.get(error_type, "An unexpected error occurred.")

    # Display the error
    show_error(f"{context} failed: {friendly_message}")

    # Show details in expander if requested
    if show_details:
        with st.expander("🔍 Technical Details"):
            st.code(f"Error Type: {error_type}\nMessage: {error_message}", language="text")
            if st.checkbox("Show Full Traceback", key=f"traceback_{id(error)}"):
                st.code(traceback.format_exc(), language="python")


def with_error_handling(func):
    """
    Decorator to add automatic error handling to functions.

    Usage:
        @with_error_handling
        async def my_function():
            # Your code here
            pass
    """
    import functools
    import asyncio

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            handle_error(e, context=func.__name__, show_details=True)
            return None

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            handle_error(e, context=func.__name__, show_details=True)
            return None

    # Return appropriate wrapper based on whether function is async
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def show_retry_button(operation_name: str, callback, *args, **kwargs):
    """
    Show a retry button for failed operations.

    Args:
        operation_name: Name of the operation to retry
        callback: Function to call when retry is clicked
        *args, **kwargs: Arguments to pass to the callback
    """
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(f"🔄 Retry {operation_name}", key=f"retry_{operation_name}_{id(callback)}"):
            callback(*args, **kwargs)


def validate_input(
    value: any,
    field_name: str,
    required: bool = False,
    min_length: int = None,
    max_length: int = None,
) -> tuple[bool, str]:
    """
    Validate user input and return validation status with message.

    Args:
        value: The value to validate
        field_name: Name of the field being validated
        required: Whether the field is required
        min_length: Minimum length for string values
        max_length: Maximum length for string values

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if required
    if required and (
        value is None or value == "" or (isinstance(value, str) and value.strip() == "")
    ):
        return False, f"{field_name} is required"

    # Skip further validation if value is empty and not required
    if not value and not required:
        return True, ""

    # Validate string length
    if isinstance(value, str):
        if min_length and len(value) < min_length:
            return False, f"{field_name} must be at least {min_length} characters"
        if max_length and len(value) > max_length:
            return False, f"{field_name} must be at most {max_length} characters"

    return True, ""


def show_connection_status(is_connected: bool, service_name: str = "Database"):
    """
    Show connection status indicator.

    Args:
        is_connected: Whether the connection is active
        service_name: Name of the service being connected to
    """
    if is_connected:
        st.sidebar.success(f"✅ {service_name} Connected")
    else:
        st.sidebar.error(f"❌ {service_name} Disconnected")
        st.sidebar.button("🔄 Reconnect", key=f"reconnect_{service_name}")


def safe_execute(func, fallback_value=None, error_message: str = None):
    """
    Safely execute a function and return fallback value on error.

    Args:
        func: Function to execute
        fallback_value: Value to return if function fails
        error_message: Custom error message to display

    Returns:
        Function result or fallback value
    """
    try:
        return func()
    except Exception as e:
        if error_message:
            show_error(error_message)
        else:
            show_error(f"Operation failed: {str(e)}")
        return fallback_value
