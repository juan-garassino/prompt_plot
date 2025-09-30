"""
Performance optimization utilities for PromptPlot.

This module provides caching, profiling, and optimization utilities
to improve system performance, especially for G-code generation and
large drawing operations.
"""

import time
import functools
import hashlib
import pickle
import logging
from typing import Any, Dict, Optional, Callable, Union, List
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import asyncio
import threading
from contextlib import contextmanager

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import memory_profiler
    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    cache_hits: int = 0
    cache_misses: int = 0
    
    @property
    def cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class PerformanceProfiler:
    """Performance profiler for monitoring system performance."""
    
    def __init__(self, enable_memory_tracking: bool = True):
        self.enable_memory_tracking = enable_memory_tracking and PSUTIL_AVAILABLE
        self.metrics: Dict[str, List[PerformanceMetrics]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @contextmanager
    def profile(self, operation_name: str):
        """Context manager for profiling operations."""
        start_time = time.time()
        start_memory = None
        start_cpu = None
        
        if self.enable_memory_tracking:
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_cpu = process.cpu_percent()
        
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            end_memory = None
            end_cpu = None
            
            if self.enable_memory_tracking:
                end_memory = process.memory_info().rss / 1024 / 1024  # MB
                end_cpu = process.cpu_percent()
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_usage_mb=end_memory - start_memory if end_memory and start_memory else None,
                cpu_usage_percent=end_cpu if end_cpu else None
            )
            
            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
            self.metrics[operation_name].append(metrics)
            
            self.logger.debug(f"Operation '{operation_name}' took {duration:.3f}s")
    
    def get_metrics(self, operation_name: Optional[str] = None) -> Union[List[PerformanceMetrics], Dict[str, List[PerformanceMetrics]]]:
        """Get performance metrics."""
        if operation_name:
            return self.metrics.get(operation_name, [])
        return self.metrics
    
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance summary statistics."""
        summary = {}
        
        for operation_name, metrics_list in self.metrics.items():
            if not metrics_list:
                continue
                
            durations = [m.duration for m in metrics_list]
            memory_usage = [m.memory_usage_mb for m in metrics_list if m.memory_usage_mb is not None]
            
            summary[operation_name] = {
                "count": len(metrics_list),
                "total_duration": sum(durations),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
            }
            
            if memory_usage:
                summary[operation_name].update({
                    "avg_memory_mb": sum(memory_usage) / len(memory_usage),
                    "max_memory_mb": max(memory_usage),
                })
        
        return summary
    
    def clear_metrics(self):
        """Clear all collected metrics."""
        self.metrics.clear()


class LRUCache:
    """Thread-safe LRU cache implementation."""
    
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self.cache: Dict[str, Any] = {}
        self.access_order: List[str] = []
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.access_order.remove(key)
                self.access_order.append(key)
                self.hits += 1
                return self.cache[key]
            else:
                self.misses += 1
                return None
    
    def put(self, key: str, value: Any):
        """Put item in cache."""
        with self.lock:
            if key in self.cache:
                # Update existing item
                self.access_order.remove(key)
            elif len(self.cache) >= self.max_size:
                # Remove least recently used item
                lru_key = self.access_order.pop(0)
                del self.cache[lru_key]
            
            self.cache[key] = value
            self.access_order.append(key)
    
    def clear(self):
        """Clear cache."""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
            self.hits = 0
            self.misses = 0
    
    @property
    def hit_ratio(self) -> float:
        """Get cache hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


class GCodeCache:
    """Specialized cache for G-code generation results."""
    
    def __init__(self, cache_dir: Optional[Path] = None, max_memory_items: int = 100):
        self.cache_dir = cache_dir or Path.home() / ".promptplot" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory_cache = LRUCache(max_memory_items)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _get_cache_key(self, prompt: str, strategy: str, config_hash: str) -> str:
        """Generate cache key for prompt and configuration."""
        content = f"{prompt}:{strategy}:{config_hash}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{cache_key}.pkl"
    
    def get(self, prompt: str, strategy: str, config_hash: str) -> Optional[Any]:
        """Get cached G-code result."""
        cache_key = self._get_cache_key(prompt, strategy, config_hash)
        
        # Try memory cache first
        result = self.memory_cache.get(cache_key)
        if result is not None:
            self.logger.debug(f"Cache hit (memory): {cache_key[:8]}...")
            return result
        
        # Try disk cache
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    result = pickle.load(f)
                
                # Store in memory cache for faster access
                self.memory_cache.put(cache_key, result)
                
                self.logger.debug(f"Cache hit (disk): {cache_key[:8]}...")
                return result
                
            except Exception as e:
                self.logger.warning(f"Failed to load cache file {cache_file}: {e}")
                # Remove corrupted cache file
                cache_file.unlink(missing_ok=True)
        
        self.logger.debug(f"Cache miss: {cache_key[:8]}...")
        return None
    
    def put(self, prompt: str, strategy: str, config_hash: str, result: Any):
        """Store G-code result in cache."""
        cache_key = self._get_cache_key(prompt, strategy, config_hash)
        
        # Store in memory cache
        self.memory_cache.put(cache_key, result)
        
        # Store in disk cache
        cache_file = self._get_cache_file(cache_key)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
            
            self.logger.debug(f"Cached result: {cache_key[:8]}...")
            
        except Exception as e:
            self.logger.warning(f"Failed to save cache file {cache_file}: {e}")
    
    def clear(self):
        """Clear all caches."""
        self.memory_cache.clear()
        
        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to delete cache file {cache_file}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        disk_files = list(self.cache_dir.glob("*.pkl"))
        total_disk_size = sum(f.stat().st_size for f in disk_files)
        
        return {
            "memory_cache_size": self.memory_cache.size,
            "memory_cache_hit_ratio": self.memory_cache.hit_ratio,
            "disk_cache_files": len(disk_files),
            "disk_cache_size_mb": total_disk_size / 1024 / 1024,
        }


def cached_gcode_generation(cache: Optional[GCodeCache] = None):
    """Decorator for caching G-code generation results."""
    if cache is None:
        cache = GCodeCache()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract cache parameters
            prompt = kwargs.get('prompt', args[0] if args else '')
            strategy = kwargs.get('strategy', 'default')
            config_hash = kwargs.get('config_hash', 'default')
            
            # Try cache first
            if kwargs.get('use_cache', True):
                cached_result = cache.get(prompt, strategy, config_hash)
                if cached_result is not None:
                    return cached_result
            
            # Generate result
            result = await func(*args, **kwargs)
            
            # Cache result
            if kwargs.get('use_cache', True) and result is not None:
                cache.put(prompt, strategy, config_hash, result)
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract cache parameters
            prompt = kwargs.get('prompt', args[0] if args else '')
            strategy = kwargs.get('strategy', 'default')
            config_hash = kwargs.get('config_hash', 'default')
            
            # Try cache first
            if kwargs.get('use_cache', True):
                cached_result = cache.get(prompt, strategy, config_hash)
                if cached_result is not None:
                    return cached_result
            
            # Generate result
            result = func(*args, **kwargs)
            
            # Cache result
            if kwargs.get('use_cache', True) and result is not None:
                cache.put(prompt, strategy, config_hash, result)
            
            return result
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ParallelProcessor:
    """Parallel processing utilities for G-code operations."""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers)
    
    async def process_commands_parallel(self, commands: List[Any], processor_func: Callable) -> List[Any]:
        """Process G-code commands in parallel using threads."""
        loop = asyncio.get_event_loop()
        
        # Split commands into batches for parallel processing
        batch_size = max(1, len(commands) // (self.max_workers or 4))
        batches = [commands[i:i + batch_size] for i in range(0, len(commands), batch_size)]
        
        # Process batches in parallel
        tasks = []
        for batch in batches:
            task = loop.run_in_executor(
                self.thread_executor,
                lambda b=batch: [processor_func(cmd) for cmd in b]
            )
            tasks.append(task)
        
        # Collect results
        batch_results = await asyncio.gather(*tasks)
        
        # Flatten results
        results = []
        for batch_result in batch_results:
            results.extend(batch_result)
        
        return results
    
    def close(self):
        """Close executors."""
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)


class MemoryOptimizer:
    """Memory optimization utilities."""
    
    @staticmethod
    def optimize_gcode_program(program) -> Any:
        """Optimize G-code program for memory usage."""
        # Remove duplicate commands
        seen_commands = set()
        optimized_commands = []
        
        for command in program.commands:
            command_str = str(command)
            if command_str not in seen_commands:
                seen_commands.add(command_str)
                optimized_commands.append(command)
        
        # Create new program with optimized commands
        program.commands = optimized_commands
        return program
    
    @staticmethod
    def compress_command_history(history: List[str], max_size: int = 1000) -> List[str]:
        """Compress command history to save memory."""
        if len(history) <= max_size:
            return history
        
        # Keep recent commands and sample from older ones
        recent_size = max_size // 2
        sample_size = max_size - recent_size
        
        recent_commands = history[-recent_size:]
        older_commands = history[:-recent_size]
        
        # Sample older commands
        if len(older_commands) > sample_size:
            step = len(older_commands) // sample_size
            sampled_commands = older_commands[::step][:sample_size]
        else:
            sampled_commands = older_commands
        
        return sampled_commands + recent_commands


# Global instances
_global_profiler = PerformanceProfiler()
_global_cache = GCodeCache()

def get_profiler() -> PerformanceProfiler:
    """Get global performance profiler."""
    return _global_profiler

def get_cache() -> GCodeCache:
    """Get global G-code cache."""
    return _global_cache

def profile_operation(operation_name: str):
    """Decorator for profiling operations."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with _global_profiler.profile(operation_name):
                return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with _global_profiler.profile(operation_name):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator