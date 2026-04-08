"""
Langfuse 4.x compatibility layer.
Provides @observe decorator and langfuse_context using the new SDK API.
"""
from functools import wraps
from backend.config import settings

try:
    from langfuse import Langfuse
    from langfuse._client.propagation import propagate_attributes

    _lf = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
    )

    def observe(name=None, **kwargs):
        """@observe decorator using langfuse 4.x start_as_current_observation."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kw):
                obs_name = name if name else func.__name__
                with _lf.start_as_current_observation(name=obs_name):
                    result = func(*args, **kw)
                return result
            return wrapper
        return decorator

    class _LangfuseContext:
        def update_current_trace(self, **kwargs):
            try:
                # session_id and user_id must be set via propagate_attributes, not here
                # Only forward supported span-level fields
                span_kwargs = {k: v for k, v in kwargs.items()
                               if k in ("input", "output", "metadata", "version", "level", "status_message")
                               and v is not None}
                if span_kwargs:
                    _lf.update_current_span(**span_kwargs)
            except Exception:
                pass

        def update_current_observation(self, **kwargs):
            try:
                _lf.update_current_span(**kwargs)
            except Exception:
                pass

        def get_current_trace_id(self):
            try:
                return _lf.get_current_trace_id()
            except Exception:
                return None

    langfuse_context = _LangfuseContext()
    LANGFUSE_DECORATORS = True

except Exception:
    LANGFUSE_DECORATORS = False

    def propagate_attributes(**kwargs):
        """No-op context manager when Langfuse is unavailable."""
        from contextlib import contextmanager
        @contextmanager
        def _noop():
            yield
        return _noop()

    def observe(name=None, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kw):
                return func(*args, **kw)
            return wrapper
        return decorator

    class _NoOpContext:
        def update_current_trace(self, **kwargs): pass
        def update_current_observation(self, **kwargs): pass
        def get_current_trace_id(self): return None

    langfuse_context = _NoOpContext()
