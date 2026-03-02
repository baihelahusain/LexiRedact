"""
Timing utilities for performance measurement.

Provides context managers and decorators for tracking execution time.
"""
import time
from typing import Optional, Callable, Any
from functools import wraps
import asyncio


class Timer:
    """
    Context manager for timing code execution.
    
    Example:
        >>> with Timer() as t:
        ...     # some code
        ...     pass
        >>> print(f"Elapsed: {t.elapsed_ms:.2f}ms")
    """
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.perf_counter()
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed_seconds * 1000
    
    @property
    def elapsed_us(self) -> float:
        """Get elapsed time in microseconds."""
        return self.elapsed_seconds * 1_000_000


def measure_time(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.
    
    Works with both sync and async functions.
    
    Example:
        >>> @measure_time
        ... async def process_data():
        ...     await asyncio.sleep(0.1)
        >>> await process_data()
        # Prints: process_data took 100.xx ms
    """
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            print(f"{func.__name__} took {elapsed:.2f} ms")
            return result
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            print(f"{func.__name__} took {elapsed:.2f} ms")
            return result
        return sync_wrapper


class MovingAverage:
    """
    Calculate moving average of timing measurements.
    
    Useful for tracking average latency over multiple operations.
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize moving average calculator.
        
        Args:
            window_size: Number of samples to keep in window
        """
        self.window_size = window_size
        self.values: list[float] = []
    
    def add(self, value: float) -> None:
        """Add a new value to the moving average."""
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values.pop(0)
    
    @property
    def average(self) -> float:
        """Get current moving average."""
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)
    
    @property
    def count(self) -> int:
        """Get number of samples in current window."""
        return len(self.values)
    
    def reset(self) -> None:
        """Reset the moving average."""
        self.values.clear()