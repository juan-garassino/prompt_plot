"""
Hot-Reloading and Runtime Configuration for PromptPlot v2.0

This module implements runtime configuration updates for non-critical settings,
configuration change notification and validation system, and configuration
backup and rollback capabilities.

Requirements addressed:
- 8.5: Runtime configuration updates and hot-reloading
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Callable, Set, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import weakref

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from .settings import PromptPlotConfig, ConfigurationManager
from .profiles import ProfileManager, ConfigurationProfile


class ConfigChangeType(str, Enum):
    """Types of configuration changes"""
    UPDATE = "update"
    RELOAD = "reload"
    PROFILE_SWITCH = "profile_switch"
    BACKUP_RESTORE = "backup_restore"


class ChangeScope(str, Enum):
    """Scope of configuration changes"""
    GLOBAL = "global"
    COMPONENT = "component"
    FIELD = "field"


class UpdateResult(str, Enum):
    """Result of configuration update"""
    SUCCESS = "success"
    FAILED = "failed"
    REQUIRES_RESTART = "requires_restart"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ConfigChange:
    """Represents a configuration change"""
    change_type: ConfigChangeType
    scope: ChangeScope
    path: str  # Dot-notation path to changed field
    old_value: Any
    new_value: Any
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"  # Source of change (file, api, user, etc.)


@dataclass
class ConfigBackup:
    """Configuration backup with metadata"""
    config: PromptPlotConfig
    timestamp: float
    description: str = ""
    automatic: bool = True
    change_count: int = 0


class ConfigChangeNotifier:
    """
    Notification system for configuration changes
    
    Manages callbacks and notifications when configuration changes occur.
    """
    
    def __init__(self):
        """Initialize change notifier"""
        self._callbacks: Dict[str, List[Callable]] = {
            "before_change": [],
            "after_change": [],
            "validation_error": [],
            "backup_created": [],
            "rollback": []
        }
        self._weak_callbacks: Dict[str, List] = {
            "before_change": [],
            "after_change": [],
            "validation_error": [],
            "backup_created": [],
            "rollback": []
        }
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def register_callback(
        self,
        event_type: str,
        callback: Callable,
        weak_ref: bool = False
    ) -> None:
        """
        Register callback for configuration change events
        
        Args:
            event_type: Type of event to listen for
            callback: Callback function
            weak_ref: Whether to use weak reference
        """
        if event_type not in self._callbacks:
            raise ValueError(f"Unknown event type: {event_type}")
        
        if weak_ref:
            self._weak_callbacks[event_type].append(weakref.ref(callback))
        else:
            self._callbacks[event_type].append(callback)
    
    def unregister_callback(self, event_type: str, callback: Callable) -> None:
        """
        Unregister callback
        
        Args:
            event_type: Type of event
            callback: Callback function to remove
        """
        if event_type in self._callbacks:
            if callback in self._callbacks[event_type]:
                self._callbacks[event_type].remove(callback)
        
        # Clean up weak references
        if event_type in self._weak_callbacks:
            self._weak_callbacks[event_type] = [
                ref for ref in self._weak_callbacks[event_type]
                if ref() is not None and ref() != callback
            ]
    
    async def notify(self, event_type: str, *args, **kwargs) -> None:
        """
        Notify all registered callbacks
        
        Args:
            event_type: Type of event
            *args: Arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
        """
        # Notify regular callbacks
        for callback in self._callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Callback error for {event_type}: {str(e)}")
        
        # Notify weak reference callbacks
        dead_refs = []
        for ref in self._weak_callbacks.get(event_type, []):
            callback = ref()
            if callback is None:
                dead_refs.append(ref)
                continue
            
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Weak callback error for {event_type}: {str(e)}")
        
        # Clean up dead weak references
        for ref in dead_refs:
            self._weak_callbacks[event_type].remove(ref)


class FileWatcher:
    """
    File system watcher for configuration files
    
    Monitors configuration files for changes and triggers reloads.
    """
    
    def __init__(self, runtime_manager: 'RuntimeConfigManager'):
        """
        Initialize file watcher
        
        Args:
            runtime_manager: Runtime configuration manager
        """
        self.runtime_manager = runtime_manager
        self.observer: Optional[Observer] = None
        self.watched_files: Set[Path] = set()
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def start_watching(self, config_files: List[Path]) -> bool:
        """
        Start watching configuration files
        
        Args:
            config_files: List of configuration files to watch
            
        Returns:
            True if watching started successfully
        """
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Watchdog not available, file watching disabled")
            return False
        
        try:
            self.observer = Observer()
            
            # Watch each file's directory
            watched_dirs = set()
            for config_file in config_files:
                if config_file.exists():
                    parent_dir = config_file.parent
                    if parent_dir not in watched_dirs:
                        event_handler = ConfigFileHandler(self.runtime_manager, config_file)
                        self.observer.schedule(event_handler, str(parent_dir), recursive=False)
                        watched_dirs.add(parent_dir)
                        self.watched_files.add(config_file)
            
            self.observer.start()
            self.logger.info(f"Started watching {len(self.watched_files)} configuration files")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start file watching: {str(e)}")
            return False
    
    def stop_watching(self) -> None:
        """Stop watching configuration files"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.watched_files.clear()
            self.logger.info("Stopped file watching")


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for configuration file system events"""
    
    def __init__(self, runtime_manager: 'RuntimeConfigManager', config_file: Path):
        """
        Initialize file handler
        
        Args:
            runtime_manager: Runtime configuration manager
            config_file: Configuration file to monitor
        """
        self.runtime_manager = runtime_manager
        self.config_file = config_file
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory and Path(event.src_path) == self.config_file:
            self.logger.info(f"Configuration file modified: {event.src_path}")
            
            # Debounce rapid changes
            asyncio.create_task(self._handle_file_change())
    
    async def _handle_file_change(self) -> None:
        """Handle configuration file change with debouncing"""
        # Wait a bit to avoid rapid successive changes
        await asyncio.sleep(0.5)
        
        try:
            await self.runtime_manager.reload_from_file(self.config_file)
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {str(e)}")


class RuntimeConfigManager:
    """
    Runtime configuration manager with hot-reloading and backup capabilities
    
    Provides:
    - Runtime configuration updates for non-critical settings
    - Configuration change notification and validation system
    - Configuration backup and rollback capabilities
    - File watching and automatic reloading
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigurationManager] = None,
        profile_manager: Optional[ProfileManager] = None,
        max_backups: int = 10,
        auto_backup_interval: int = 5  # Number of changes before auto-backup
    ):
        """
        Initialize runtime configuration manager
        
        Args:
            config_manager: Configuration manager instance
            profile_manager: Profile manager instance
            max_backups: Maximum number of backups to keep
            auto_backup_interval: Number of changes before automatic backup
        """
        self.config_manager = config_manager or ConfigurationManager()
        self.profile_manager = profile_manager or ProfileManager()
        self.max_backups = max_backups
        self.auto_backup_interval = auto_backup_interval
        
        # Change tracking
        self.change_notifier = ConfigChangeNotifier()
        self.change_history: List[ConfigChange] = []
        self.change_count = 0
        
        # Backup system
        self.backups: List[ConfigBackup] = []
        self.backup_directory = Path("backups/config")
        
        # File watching
        self.file_watcher = FileWatcher(self)
        self.watched_files: List[Path] = []
        
        # Runtime state
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._lock = threading.Lock()
        
        # Non-critical settings that can be updated at runtime
        self.runtime_updatable_fields = {
            "debug",
            "log_level",
            "visualization.enable_animation",
            "visualization.figure_width",
            "visualization.figure_height",
            "visualization.grid_color",
            "visualization.grid_alpha",
            "workflow.save_intermediate_results",
            "workflow.progress_update_interval",
            "vision.enable_caching",
            "vision.feedback_threshold",
            # Paper settings that can be changed at runtime
            "plotter.paper.margin_top",
            "plotter.paper.margin_bottom", 
            "plotter.paper.margin_left",
            "plotter.paper.margin_right",
            "plotter.paper.safe_zone_top",
            "plotter.paper.safe_zone_bottom",
            "plotter.paper.safe_zone_left",
            "plotter.paper.safe_zone_right",
            "plotter.paper.pen_down_pressure",
            "plotter.drawing_speed",
            "plotter.travel_speed",
            "plotter.pen_up_delay",
            "plotter.pen_down_delay"
        }
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    async def start(self, watch_files: Optional[List[Path]] = None) -> bool:
        """
        Start runtime configuration management
        
        Args:
            watch_files: Optional list of files to watch for changes
            
        Returns:
            True if started successfully
        """
        try:
            self.is_running = True
            
            # Create backup directory
            self.backup_directory.mkdir(parents=True, exist_ok=True)
            
            # Create initial backup
            await self.create_backup("Initial backup", automatic=True)
            
            # Start file watching if files provided
            if watch_files:
                self.watched_files = watch_files
                self.file_watcher.start_watching(watch_files)
            
            self.logger.info("Runtime configuration manager started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start runtime config manager: {str(e)}")
            return False
    
    async def stop(self) -> None:
        """Stop runtime configuration management"""
        try:
            self.is_running = False
            
            # Stop file watching
            self.file_watcher.stop_watching()
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            self.logger.info("Runtime configuration manager stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping runtime config manager: {str(e)}")
    
    async def update_field(
        self,
        field_path: str,
        new_value: Any,
        source: str = "runtime",
        validate: bool = True
    ) -> UpdateResult:
        """
        Update a single configuration field at runtime
        
        Args:
            field_path: Dot-notation path to field (e.g., "llm.max_retries")
            new_value: New value for the field
            source: Source of the change
            validate: Whether to validate the change
            
        Returns:
            Result of the update operation
        """
        if not self.is_running:
            return UpdateResult.FAILED
        
        # Check if field is runtime updatable
        if field_path not in self.runtime_updatable_fields:
            self.logger.warning(f"Field {field_path} is not runtime updatable")
            return UpdateResult.REQUIRES_RESTART
        
        try:
            with self._lock:
                config = self.config_manager.get_config()
                
                # Get current value
                old_value = self._get_field_value(config, field_path)
                
                # Create change object
                change = ConfigChange(
                    change_type=ConfigChangeType.UPDATE,
                    scope=ChangeScope.FIELD,
                    path=field_path,
                    old_value=old_value,
                    new_value=new_value,
                    source=source
                )
                
                # Notify before change
                await self.change_notifier.notify("before_change", change)
                
                # Validate change if requested
                if validate:
                    validation_errors = await self._validate_field_change(field_path, new_value)
                    if validation_errors:
                        await self.change_notifier.notify("validation_error", change, validation_errors)
                        return UpdateResult.VALIDATION_ERROR
                
                # Apply change
                self._set_field_value(config, field_path, new_value)
                
                # Update change tracking
                self.change_history.append(change)
                self.change_count += 1
                
                # Notify after change
                await self.change_notifier.notify("after_change", change)
                
                # Auto-backup if needed
                if self.change_count % self.auto_backup_interval == 0:
                    await self.create_backup(
                        f"Auto-backup after {self.change_count} changes",
                        automatic=True
                    )
                
                self.logger.info(f"Updated {field_path}: {old_value} -> {new_value}")
                return UpdateResult.SUCCESS
                
        except Exception as e:
            self.logger.error(f"Failed to update field {field_path}: {str(e)}")
            return UpdateResult.FAILED
    
    async def update_multiple_fields(
        self,
        updates: Dict[str, Any],
        source: str = "runtime",
        validate: bool = True
    ) -> Dict[str, UpdateResult]:
        """
        Update multiple configuration fields at runtime
        
        Args:
            updates: Dictionary mapping field paths to new values
            source: Source of the changes
            validate: Whether to validate changes
            
        Returns:
            Dictionary mapping field paths to update results
        """
        results = {}
        
        for field_path, new_value in updates.items():
            result = await self.update_field(field_path, new_value, source, validate)
            results[field_path] = result
        
        return results
    
    async def reload_from_file(self, config_file: Path) -> UpdateResult:
        """
        Reload configuration from file
        
        Args:
            config_file: Configuration file to reload from
            
        Returns:
            Result of the reload operation
        """
        try:
            # Load new configuration
            new_config = self.config_manager.load_config(config_file)
            
            # Get current configuration
            current_config = self.config_manager.get_config()
            
            # Find differences
            changes = self._find_config_differences(current_config, new_config)
            
            if not changes:
                self.logger.info("No configuration changes detected")
                return UpdateResult.SUCCESS
            
            # Create backup before reload
            await self.create_backup("Before file reload", automatic=True)
            
            # Apply changes
            for change in changes:
                await self.change_notifier.notify("before_change", change)
            
            # Update configuration
            self.config_manager._config = new_config
            
            # Notify after changes
            for change in changes:
                self.change_history.append(change)
                await self.change_notifier.notify("after_change", change)
            
            self.change_count += len(changes)
            
            self.logger.info(f"Reloaded configuration from {config_file} ({len(changes)} changes)")
            return UpdateResult.SUCCESS
            
        except Exception as e:
            self.logger.error(f"Failed to reload from file {config_file}: {str(e)}")
            return UpdateResult.FAILED
    
    async def switch_profile_runtime(self, profile_name: str) -> UpdateResult:
        """
        Switch configuration profile at runtime
        
        Args:
            profile_name: Name of profile to switch to
            
        Returns:
            Result of the profile switch
        """
        try:
            # Get current and new profiles
            current_profile = self.profile_manager.get_active_profile()
            new_profile = self.profile_manager.get_profile(profile_name)
            
            if not new_profile:
                self.logger.error(f"Profile not found: {profile_name}")
                return UpdateResult.FAILED
            
            # Create backup before switch
            await self.create_backup(f"Before profile switch to {profile_name}", automatic=True)
            
            # Find differences
            current_config = current_profile.config if current_profile else self.config_manager.get_config()
            changes = self._find_config_differences(current_config, new_profile.config)
            
            # Create profile switch change
            profile_change = ConfigChange(
                change_type=ConfigChangeType.PROFILE_SWITCH,
                scope=ChangeScope.GLOBAL,
                path="profile",
                old_value=current_profile.name if current_profile else None,
                new_value=profile_name,
                source="profile_switch"
            )
            
            # Notify before change
            await self.change_notifier.notify("before_change", profile_change)
            
            # Switch profile
            success = self.profile_manager.switch_profile(profile_name)
            if not success:
                return UpdateResult.FAILED
            
            # Track changes
            self.change_history.append(profile_change)
            for change in changes:
                self.change_history.append(change)
            
            self.change_count += len(changes) + 1
            
            # Notify after change
            await self.change_notifier.notify("after_change", profile_change)
            
            self.logger.info(f"Switched to profile: {profile_name}")
            return UpdateResult.SUCCESS
            
        except Exception as e:
            self.logger.error(f"Failed to switch profile: {str(e)}")
            return UpdateResult.FAILED
    
    async def create_backup(self, description: str = "", automatic: bool = False) -> bool:
        """
        Create configuration backup
        
        Args:
            description: Description of the backup
            automatic: Whether this is an automatic backup
            
        Returns:
            True if backup created successfully
        """
        try:
            config = deepcopy(self.config_manager.get_config())
            
            backup = ConfigBackup(
                config=config,
                timestamp=time.time(),
                description=description,
                automatic=automatic,
                change_count=self.change_count
            )
            
            self.backups.append(backup)
            
            # Limit number of backups
            if len(self.backups) > self.max_backups:
                self.backups.pop(0)
            
            # Save backup to file
            await self._save_backup_to_file(backup)
            
            # Notify
            await self.change_notifier.notify("backup_created", backup)
            
            self.logger.debug(f"Created backup: {description}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {str(e)}")
            return False
    
    async def rollback_to_backup(self, backup_index: int = -1) -> UpdateResult:
        """
        Rollback to a previous backup
        
        Args:
            backup_index: Index of backup to rollback to (-1 for most recent)
            
        Returns:
            Result of the rollback operation
        """
        try:
            if not self.backups:
                self.logger.error("No backups available for rollback")
                return UpdateResult.FAILED
            
            if backup_index < -len(self.backups) or backup_index >= len(self.backups):
                self.logger.error(f"Invalid backup index: {backup_index}")
                return UpdateResult.FAILED
            
            backup = self.backups[backup_index]
            current_config = self.config_manager.get_config()
            
            # Find differences
            changes = self._find_config_differences(current_config, backup.config)
            
            # Create rollback change
            rollback_change = ConfigChange(
                change_type=ConfigChangeType.BACKUP_RESTORE,
                scope=ChangeScope.GLOBAL,
                path="config",
                old_value="current",
                new_value=f"backup_{backup.timestamp}",
                source="rollback"
            )
            
            # Notify before rollback
            await self.change_notifier.notify("rollback", rollback_change, backup)
            
            # Apply backup
            self.config_manager._config = deepcopy(backup.config)
            
            # Track changes
            self.change_history.append(rollback_change)
            for change in changes:
                self.change_history.append(change)
            
            self.change_count += len(changes) + 1
            
            self.logger.info(f"Rolled back to backup from {backup.timestamp}")
            return UpdateResult.SUCCESS
            
        except Exception as e:
            self.logger.error(f"Failed to rollback: {str(e)}")
            return UpdateResult.FAILED
    
    def _get_field_value(self, config: PromptPlotConfig, field_path: str) -> Any:
        """Get field value using dot notation path"""
        parts = field_path.split('.')
        current = config
        
        for part in parts:
            current = getattr(current, part)
        
        return current
    
    def _set_field_value(self, config: PromptPlotConfig, field_path: str, value: Any) -> None:
        """Set field value using dot notation path"""
        parts = field_path.split('.')
        current = config
        
        for part in parts[:-1]:
            current = getattr(current, part)
        
        setattr(current, parts[-1], value)
    
    async def _validate_field_change(self, field_path: str, new_value: Any) -> List[str]:
        """Validate a field change"""
        errors = []
        
        try:
            # Create temporary config with the change
            temp_config = deepcopy(self.config_manager.get_config())
            self._set_field_value(temp_config, field_path, new_value)
            
            # Validate the temporary config
            validation_errors = self.config_manager.validate_config(temp_config)
            errors.extend(validation_errors)
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return errors
    
    def _find_config_differences(
        self,
        old_config: PromptPlotConfig,
        new_config: PromptPlotConfig
    ) -> List[ConfigChange]:
        """Find differences between two configurations"""
        changes = []
        
        # Compare each component
        components = ['llm', 'plotter', 'visualization', 'workflow', 'vision']
        
        for component in components:
            old_component = getattr(old_config, component)
            new_component = getattr(new_config, component)
            
            component_changes = self._compare_dataclass_objects(
                old_component, new_component, component
            )
            changes.extend(component_changes)
        
        # Compare top-level fields
        top_level_fields = ['debug', 'log_level', 'log_file', 'validation_level', 'strict_mode']
        
        for field in top_level_fields:
            old_value = getattr(old_config, field)
            new_value = getattr(new_config, field)
            
            if old_value != new_value:
                changes.append(ConfigChange(
                    change_type=ConfigChangeType.UPDATE,
                    scope=ChangeScope.FIELD,
                    path=field,
                    old_value=old_value,
                    new_value=new_value,
                    source="config_diff"
                ))
        
        return changes
    
    def _compare_dataclass_objects(self, old_obj: Any, new_obj: Any, prefix: str) -> List[ConfigChange]:
        """Compare two dataclass objects and return changes"""
        changes = []
        
        from dataclasses import fields
        
        for field_info in fields(old_obj):
            old_value = getattr(old_obj, field_info.name)
            new_value = getattr(new_obj, field_info.name)
            
            if old_value != new_value:
                field_path = f"{prefix}.{field_info.name}"
                changes.append(ConfigChange(
                    change_type=ConfigChangeType.UPDATE,
                    scope=ChangeScope.FIELD,
                    path=field_path,
                    old_value=old_value,
                    new_value=new_value,
                    source="config_diff"
                ))
        
        return changes
    
    async def _save_backup_to_file(self, backup: ConfigBackup) -> None:
        """Save backup to file"""
        try:
            timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(backup.timestamp))
            backup_file = self.backup_directory / f"config_backup_{timestamp_str}.json"
            
            backup_data = {
                "timestamp": backup.timestamp,
                "description": backup.description,
                "automatic": backup.automatic,
                "change_count": backup.change_count,
                "config": self.config_manager._config_to_dict(backup.config)
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
                
        except Exception as e:
            self.logger.warning(f"Failed to save backup to file: {str(e)}")
    
    def get_change_history(self, limit: Optional[int] = None) -> List[ConfigChange]:
        """
        Get configuration change history
        
        Args:
            limit: Maximum number of changes to return
            
        Returns:
            List of configuration changes
        """
        if limit:
            return self.change_history[-limit:]
        return self.change_history.copy()
    
    def get_backups(self) -> List[ConfigBackup]:
        """
        Get list of available backups
        
        Returns:
            List of configuration backups
        """
        return self.backups.copy()
    
    def get_runtime_updatable_fields(self) -> Set[str]:
        """
        Get set of fields that can be updated at runtime
        
        Returns:
            Set of runtime updatable field paths
        """
        return self.runtime_updatable_fields.copy()
    
    def add_runtime_updatable_field(self, field_path: str) -> None:
        """
        Add field to runtime updatable fields
        
        Args:
            field_path: Dot-notation path to field
        """
        self.runtime_updatable_fields.add(field_path)
    
    def remove_runtime_updatable_field(self, field_path: str) -> None:
        """
        Remove field from runtime updatable fields
        
        Args:
            field_path: Dot-notation path to field
        """
        self.runtime_updatable_fields.discard(field_path)


# Global runtime configuration manager
_runtime_manager: Optional[RuntimeConfigManager] = None


def get_runtime_manager() -> RuntimeConfigManager:
    """
    Get global runtime configuration manager
    
    Returns:
        Global runtime manager instance
    """
    global _runtime_manager
    if _runtime_manager is None:
        _runtime_manager = RuntimeConfigManager()
    return _runtime_manager


async def start_runtime_config(watch_files: Optional[List[Path]] = None) -> bool:
    """
    Start runtime configuration management
    
    Args:
        watch_files: Optional list of files to watch
        
    Returns:
        True if started successfully
    """
    manager = get_runtime_manager()
    return await manager.start(watch_files)


async def stop_runtime_config() -> None:
    """Stop runtime configuration management"""
    global _runtime_manager
    if _runtime_manager:
        await _runtime_manager.stop()


async def update_config_field(
    field_path: str,
    new_value: Any,
    source: str = "api"
) -> UpdateResult:
    """
    Update configuration field at runtime
    
    Args:
        field_path: Dot-notation path to field
        new_value: New value for field
        source: Source of change
        
    Returns:
        Result of update operation
    """
    manager = get_runtime_manager()
    return await manager.update_field(field_path, new_value, source)


def register_change_callback(event_type: str, callback: Callable) -> None:
    """
    Register callback for configuration changes
    
    Args:
        event_type: Type of event to listen for
        callback: Callback function
    """
    manager = get_runtime_manager()
    manager.change_notifier.register_callback(event_type, callback)