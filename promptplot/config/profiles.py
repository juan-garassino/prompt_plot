"""
Configuration Profiles for PromptPlot v2.0

This module implements configuration profiles for different use case scenarios,
with profile switching and inheritance mechanisms, and profile validation
and conflict resolution.

Requirements addressed:
- 8.2: Multiple configuration profiles for different scenarios
- 8.3: Profile switching and inheritance mechanisms
"""

import json
import logging
from typing import Dict, Any, Optional, List, Union, Set
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

from .settings import PromptPlotConfig, ConfigurationManager, ConfigFormat


class ProfileType(str, Enum):
    """Types of configuration profiles"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    DEMO = "demo"
    CUSTOM = "custom"


class InheritanceMode(str, Enum):
    """Profile inheritance modes"""
    OVERRIDE = "override"  # Child completely overrides parent
    MERGE = "merge"       # Child merges with parent (default)
    EXTEND = "extend"     # Child extends parent lists/dicts


@dataclass
class ProfileMetadata:
    """Metadata for configuration profiles"""
    name: str
    profile_type: ProfileType
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    parent_profile: Optional[str] = None
    inheritance_mode: InheritanceMode = InheritanceMode.MERGE


@dataclass
class ProfileValidationResult:
    """Result of profile validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)


class ConfigurationProfile:
    """
    Configuration profile with inheritance and validation
    
    Represents a named configuration profile that can inherit from other profiles
    and provides validation and conflict resolution capabilities.
    """
    
    def __init__(
        self,
        name: str,
        config: PromptPlotConfig,
        metadata: Optional[ProfileMetadata] = None
    ):
        """
        Initialize configuration profile
        
        Args:
            name: Profile name
            config: Configuration object
            metadata: Optional profile metadata
        """
        self.name = name
        self.config = config
        self.metadata = metadata or ProfileMetadata(
            name=name,
            profile_type=ProfileType.CUSTOM
        )
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    def inherit_from(
        self,
        parent_profile: 'ConfigurationProfile',
        inheritance_mode: Optional[InheritanceMode] = None
    ) -> 'ConfigurationProfile':
        """
        Create new profile inheriting from parent
        
        Args:
            parent_profile: Parent profile to inherit from
            inheritance_mode: How to handle inheritance (uses metadata default if None)
            
        Returns:
            New profile with inherited configuration
        """
        mode = inheritance_mode or self.metadata.inheritance_mode
        
        if mode == InheritanceMode.OVERRIDE:
            # Child completely overrides parent
            new_config = deepcopy(self.config)
        elif mode == InheritanceMode.MERGE:
            # Merge parent and child configurations
            new_config = self._merge_configs(parent_profile.config, self.config)
        elif mode == InheritanceMode.EXTEND:
            # Extend parent with child (for lists and dicts)
            new_config = self._extend_configs(parent_profile.config, self.config)
        else:
            raise ValueError(f"Unknown inheritance mode: {mode}")
        
        # Update metadata
        new_metadata = deepcopy(self.metadata)
        new_metadata.parent_profile = parent_profile.name
        new_metadata.inheritance_mode = mode
        
        return ConfigurationProfile(
            name=self.name,
            config=new_config,
            metadata=new_metadata
        )
    
    def _merge_configs(
        self,
        parent_config: PromptPlotConfig,
        child_config: PromptPlotConfig
    ) -> PromptPlotConfig:
        """Merge parent and child configurations"""
        # Start with parent config
        merged_config = deepcopy(parent_config)
        
        # Merge each component
        merged_config.llm = self._merge_dataclass(parent_config.llm, child_config.llm)
        merged_config.plotter = self._merge_dataclass(parent_config.plotter, child_config.plotter)
        merged_config.visualization = self._merge_dataclass(parent_config.visualization, child_config.visualization)
        merged_config.workflow = self._merge_dataclass(parent_config.workflow, child_config.workflow)
        merged_config.vision = self._merge_dataclass(parent_config.vision, child_config.vision)
        
        # Merge top-level fields
        if child_config.debug != parent_config.debug:
            merged_config.debug = child_config.debug
        if child_config.log_level != parent_config.log_level:
            merged_config.log_level = child_config.log_level
        if child_config.log_file != parent_config.log_file:
            merged_config.log_file = child_config.log_file
        if child_config.validation_level != parent_config.validation_level:
            merged_config.validation_level = child_config.validation_level
        if child_config.strict_mode != parent_config.strict_mode:
            merged_config.strict_mode = child_config.strict_mode
        
        return merged_config
    
    def _merge_dataclass(self, parent_obj: Any, child_obj: Any) -> Any:
        """Merge two dataclass objects"""
        # Create new object starting with parent
        merged_obj = deepcopy(parent_obj)
        
        # Get all fields from child
        from dataclasses import fields
        
        for field_info in fields(child_obj):
            child_value = getattr(child_obj, field_info.name)
            parent_value = getattr(parent_obj, field_info.name)
            
            # Only override if child value is different from default
            if child_value != field_info.default and child_value != parent_value:
                setattr(merged_obj, field_info.name, child_value)
        
        return merged_obj
    
    def _extend_configs(
        self,
        parent_config: PromptPlotConfig,
        child_config: PromptPlotConfig
    ) -> PromptPlotConfig:
        """Extend parent configuration with child (for lists and dicts)"""
        # For now, extend mode is the same as merge
        # In the future, this could handle extending lists and dicts specifically
        return self._merge_configs(parent_config, child_config)
    
    def validate(self) -> ProfileValidationResult:
        """
        Validate profile configuration
        
        Returns:
            Validation result with errors, warnings, and conflicts
        """
        errors = []
        warnings = []
        conflicts = []
        
        try:
            # Validate the configuration itself
            config_manager = ConfigurationManager()
            config_errors = config_manager.validate_config(self.config)
            errors.extend(config_errors)
            
            # Validate metadata
            if not self.metadata.name:
                errors.append("Profile name is required")
            
            if not self.metadata.description and self.metadata.profile_type == ProfileType.CUSTOM:
                warnings.append("Custom profiles should have a description")
            
            # Check for potential conflicts
            self._check_conflicts(conflicts)
            
        except Exception as e:
            errors.append(f"Profile validation failed: {str(e)}")
        
        return ProfileValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            conflicts=conflicts
        )
    
    def _check_conflicts(self, conflicts: List[str]) -> None:
        """Check for configuration conflicts"""
        # Check LLM provider conflicts
        if (self.config.llm.default_provider == "azure_openai" and 
            not self.config.llm.azure_api_key):
            conflicts.append("Azure OpenAI provider selected but no API key configured")
        
        # Check plotter conflicts
        if (self.config.plotter.default_type == "serial" and 
            self.config.plotter.serial_port == "/dev/ttyUSB0" and 
            self.metadata.profile_type == ProfileType.PRODUCTION):
            conflicts.append("Production profile using default serial port")
        
        # Check visualization conflicts
        if (self.config.visualization.enable_animation and 
            self.config.workflow.max_steps > 100):
            conflicts.append("Animation enabled with high step count may cause performance issues")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary representation"""
        config_manager = ConfigurationManager()
        config_dict = config_manager._config_to_dict(self.config)
        
        return {
            "metadata": {
                "name": self.metadata.name,
                "profile_type": self.metadata.profile_type.value,
                "description": self.metadata.description,
                "version": self.metadata.version,
                "author": self.metadata.author,
                "created_at": self.metadata.created_at,
                "updated_at": self.metadata.updated_at,
                "tags": self.metadata.tags,
                "parent_profile": self.metadata.parent_profile,
                "inheritance_mode": self.metadata.inheritance_mode.value
            },
            "config": config_dict
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigurationProfile':
        """Create profile from dictionary representation"""
        metadata_data = data.get("metadata", {})
        config_data = data.get("config", {})
        
        # Create metadata
        metadata = ProfileMetadata(
            name=metadata_data.get("name", "unnamed"),
            profile_type=ProfileType(metadata_data.get("profile_type", "custom")),
            description=metadata_data.get("description", ""),
            version=metadata_data.get("version", "1.0.0"),
            author=metadata_data.get("author", ""),
            created_at=metadata_data.get("created_at"),
            updated_at=metadata_data.get("updated_at"),
            tags=metadata_data.get("tags", []),
            parent_profile=metadata_data.get("parent_profile"),
            inheritance_mode=InheritanceMode(metadata_data.get("inheritance_mode", "merge"))
        )
        
        # Create configuration
        config_manager = ConfigurationManager()
        config = config_manager._create_config_from_dict(config_data)
        
        return cls(
            name=metadata.name,
            config=config,
            metadata=metadata
        )


class ProfileManager:
    """
    Manager for configuration profiles with switching and inheritance
    
    Provides:
    - Profile registration and management
    - Profile switching and inheritance mechanisms
    - Profile validation and conflict resolution
    - Built-in profiles for common scenarios
    """
    
    def __init__(self, profiles_directory: Optional[Path] = None):
        """
        Initialize profile manager
        
        Args:
            profiles_directory: Directory to store profile files
        """
        self.profiles_directory = profiles_directory or Path("profiles")
        self.profiles: Dict[str, ConfigurationProfile] = {}
        self.active_profile: Optional[str] = None
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
        # Load built-in profiles
        self._load_builtin_profiles()
        
        # Load profiles from directory
        self._load_profiles_from_directory()
    
    def _load_builtin_profiles(self) -> None:
        """Load built-in configuration profiles"""
        # Development profile
        dev_config = PromptPlotConfig(
            debug=True,
            log_level="DEBUG",
            strict_mode=False
        )
        dev_config.llm.default_provider = "ollama"
        dev_config.plotter.default_type = "simulated"
        # Development uses A4 with generous margins for safety
        dev_config.plotter.paper.paper_size = "A4"
        dev_config.plotter.paper.margin_top = 15.0
        dev_config.plotter.paper.margin_bottom = 15.0
        dev_config.plotter.paper.margin_left = 15.0
        dev_config.plotter.paper.margin_right = 15.0
        dev_config.visualization.enable_animation = True
        dev_config.workflow.max_steps = 20
        dev_config.workflow.save_intermediate_results = True
        
        dev_metadata = ProfileMetadata(
            name="development",
            profile_type=ProfileType.DEVELOPMENT,
            description="Development profile with debugging enabled and simulated plotter",
            version="1.0.0",
            author="PromptPlot"
        )
        
        self.register_profile(ConfigurationProfile(
            name="development",
            config=dev_config,
            metadata=dev_metadata
        ))
        
        # Production profile
        prod_config = PromptPlotConfig(
            debug=False,
            log_level="INFO",
            strict_mode=True
        )
        prod_config.llm.default_provider = "azure_openai"
        prod_config.plotter.default_type = "serial"
        # Production uses precise margins for real plotting
        prod_config.plotter.paper.paper_size = "A4"
        prod_config.plotter.paper.margin_top = 10.0
        prod_config.plotter.paper.margin_bottom = 10.0
        prod_config.plotter.paper.margin_left = 10.0
        prod_config.plotter.paper.margin_right = 10.0
        prod_config.plotter.paper.safe_zone_top = 2.0
        prod_config.plotter.paper.safe_zone_bottom = 2.0
        prod_config.plotter.paper.safe_zone_left = 2.0
        prod_config.plotter.paper.safe_zone_right = 2.0
        prod_config.visualization.enable_animation = False
        prod_config.workflow.max_steps = 100
        prod_config.workflow.validation_level = "strict"
        
        prod_metadata = ProfileMetadata(
            name="production",
            profile_type=ProfileType.PRODUCTION,
            description="Production profile with strict validation and real hardware",
            version="1.0.0",
            author="PromptPlot"
        )
        
        self.register_profile(ConfigurationProfile(
            name="production",
            config=prod_config,
            metadata=prod_metadata
        ))
        
        # Testing profile
        test_config = PromptPlotConfig(
            debug=True,
            log_level="DEBUG",
            strict_mode=True
        )
        test_config.llm.default_provider = "ollama"
        test_config.plotter.default_type = "simulated"
        test_config.visualization.enable_animation = False
        test_config.workflow.max_steps = 10
        test_config.workflow.validation_level = "comprehensive"
        
        test_metadata = ProfileMetadata(
            name="testing",
            profile_type=ProfileType.TESTING,
            description="Testing profile with comprehensive validation and fast execution",
            version="1.0.0",
            author="PromptPlot"
        )
        
        self.register_profile(ConfigurationProfile(
            name="testing",
            config=test_config,
            metadata=test_metadata
        ))
        
        # Demo profile
        demo_config = PromptPlotConfig(
            debug=False,
            log_level="INFO",
            strict_mode=False
        )
        demo_config.llm.default_provider = "ollama"
        demo_config.plotter.default_type = "simulated"
        # Demo uses larger paper for impressive presentations
        demo_config.plotter.paper.paper_size = "A3"
        demo_config.plotter.paper.orientation = "landscape"
        demo_config.plotter.paper.margin_top = 20.0
        demo_config.plotter.paper.margin_bottom = 20.0
        demo_config.plotter.paper.margin_left = 20.0
        demo_config.plotter.paper.margin_right = 20.0
        demo_config.visualization.enable_animation = True
        demo_config.visualization.figure_width = 12.0
        demo_config.visualization.figure_height = 12.0
        demo_config.workflow.max_steps = 30
        
        demo_metadata = ProfileMetadata(
            name="demo",
            profile_type=ProfileType.DEMO,
            description="Demo profile with enhanced visualization for presentations",
            version="1.0.0",
            author="PromptPlot"
        )
        
        self.register_profile(ConfigurationProfile(
            name="demo",
            config=demo_config,
            metadata=demo_metadata
        ))
    
    def _load_profiles_from_directory(self) -> None:
        """Load profiles from profiles directory"""
        if not self.profiles_directory.exists():
            return
        
        for profile_file in self.profiles_directory.glob("*.json"):
            try:
                with open(profile_file, 'r') as f:
                    profile_data = json.load(f)
                
                profile = ConfigurationProfile.from_dict(profile_data)
                self.register_profile(profile)
                
                self.logger.info(f"Loaded profile: {profile.name}")
                
            except Exception as e:
                self.logger.error(f"Failed to load profile from {profile_file}: {str(e)}")
    
    def register_profile(self, profile: ConfigurationProfile) -> None:
        """
        Register a configuration profile
        
        Args:
            profile: Profile to register
        """
        self.profiles[profile.name] = profile
        self.logger.debug(f"Registered profile: {profile.name}")
    
    def get_profile(self, name: str) -> Optional[ConfigurationProfile]:
        """
        Get profile by name
        
        Args:
            name: Profile name
            
        Returns:
            Profile object or None if not found
        """
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[str]:
        """
        List all available profile names
        
        Returns:
            List of profile names
        """
        return list(self.profiles.keys())
    
    def get_profiles_by_type(self, profile_type: ProfileType) -> List[ConfigurationProfile]:
        """
        Get profiles by type
        
        Args:
            profile_type: Type of profiles to get
            
        Returns:
            List of profiles of the specified type
        """
        return [
            profile for profile in self.profiles.values()
            if profile.metadata.profile_type == profile_type
        ]
    
    def switch_profile(self, name: str) -> bool:
        """
        Switch to a different profile
        
        Args:
            name: Name of profile to switch to
            
        Returns:
            True if switch successful
        """
        if name not in self.profiles:
            self.logger.error(f"Profile not found: {name}")
            return False
        
        profile = self.profiles[name]
        
        # Validate profile before switching
        validation_result = profile.validate()
        if not validation_result.is_valid:
            self.logger.error(f"Cannot switch to invalid profile {name}: {validation_result.errors}")
            return False
        
        # Log warnings
        for warning in validation_result.warnings:
            self.logger.warning(f"Profile {name}: {warning}")
        
        # Log conflicts
        for conflict in validation_result.conflicts:
            self.logger.warning(f"Profile {name} conflict: {conflict}")
        
        self.active_profile = name
        
        # Update global configuration
        from .settings import _config_manager
        _config_manager._config = profile.config
        
        self.logger.info(f"Switched to profile: {name}")
        return True
    
    def get_active_profile(self) -> Optional[ConfigurationProfile]:
        """
        Get currently active profile
        
        Returns:
            Active profile or None if no profile is active
        """
        if self.active_profile:
            return self.profiles.get(self.active_profile)
        return None
    
    def create_profile(
        self,
        name: str,
        base_profile: Optional[str] = None,
        profile_type: ProfileType = ProfileType.CUSTOM,
        description: str = "",
        inheritance_mode: InheritanceMode = InheritanceMode.MERGE
    ) -> ConfigurationProfile:
        """
        Create new profile, optionally inheriting from existing profile
        
        Args:
            name: Name for new profile
            base_profile: Name of profile to inherit from
            profile_type: Type of profile
            description: Profile description
            inheritance_mode: How to handle inheritance
            
        Returns:
            New profile object
        """
        if base_profile:
            parent = self.get_profile(base_profile)
            if not parent:
                raise ValueError(f"Base profile not found: {base_profile}")
            
            # Create child profile with minimal config
            child_config = PromptPlotConfig()
            child_metadata = ProfileMetadata(
                name=name,
                profile_type=profile_type,
                description=description,
                parent_profile=base_profile,
                inheritance_mode=inheritance_mode
            )
            
            child_profile = ConfigurationProfile(
                name=name,
                config=child_config,
                metadata=child_metadata
            )
            
            # Inherit from parent
            new_profile = child_profile.inherit_from(parent, inheritance_mode)
        else:
            # Create profile from default config
            config = PromptPlotConfig()
            metadata = ProfileMetadata(
                name=name,
                profile_type=profile_type,
                description=description
            )
            
            new_profile = ConfigurationProfile(
                name=name,
                config=config,
                metadata=metadata
            )
        
        self.register_profile(new_profile)
        return new_profile
    
    def save_profile(self, name: str, overwrite: bool = False) -> bool:
        """
        Save profile to file
        
        Args:
            name: Name of profile to save
            overwrite: Whether to overwrite existing file
            
        Returns:
            True if save successful
        """
        profile = self.get_profile(name)
        if not profile:
            self.logger.error(f"Profile not found: {name}")
            return False
        
        try:
            # Ensure profiles directory exists
            self.profiles_directory.mkdir(parents=True, exist_ok=True)
            
            profile_file = self.profiles_directory / f"{name}.json"
            
            if profile_file.exists() and not overwrite:
                self.logger.error(f"Profile file already exists: {profile_file}")
                return False
            
            # Save profile
            with open(profile_file, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2, default=str)
            
            self.logger.info(f"Profile saved: {profile_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save profile {name}: {str(e)}")
            return False
    
    def delete_profile(self, name: str, delete_file: bool = False) -> bool:
        """
        Delete profile
        
        Args:
            name: Name of profile to delete
            delete_file: Whether to delete profile file
            
        Returns:
            True if delete successful
        """
        if name not in self.profiles:
            self.logger.error(f"Profile not found: {name}")
            return False
        
        # Don't allow deleting built-in profiles
        profile = self.profiles[name]
        if profile.metadata.profile_type in [ProfileType.DEVELOPMENT, ProfileType.PRODUCTION, 
                                           ProfileType.TESTING, ProfileType.DEMO]:
            self.logger.error(f"Cannot delete built-in profile: {name}")
            return False
        
        try:
            # Remove from memory
            del self.profiles[name]
            
            # Reset active profile if it was deleted
            if self.active_profile == name:
                self.active_profile = None
            
            # Delete file if requested
            if delete_file:
                profile_file = self.profiles_directory / f"{name}.json"
                if profile_file.exists():
                    profile_file.unlink()
            
            self.logger.info(f"Profile deleted: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete profile {name}: {str(e)}")
            return False
    
    def validate_all_profiles(self) -> Dict[str, ProfileValidationResult]:
        """
        Validate all registered profiles
        
        Returns:
            Dictionary mapping profile names to validation results
        """
        results = {}
        
        for name, profile in self.profiles.items():
            results[name] = profile.validate()
        
        return results
    
    def resolve_conflicts(self, profile_name: str) -> List[str]:
        """
        Attempt to resolve conflicts in a profile
        
        Args:
            profile_name: Name of profile to resolve conflicts for
            
        Returns:
            List of resolution actions taken
        """
        profile = self.get_profile(profile_name)
        if not profile:
            return []
        
        validation_result = profile.validate()
        if not validation_result.conflicts:
            return []
        
        actions = []
        
        for conflict in validation_result.conflicts:
            if "Azure OpenAI provider selected but no API key" in conflict:
                # Switch to Ollama provider
                profile.config.llm.default_provider = "ollama"
                actions.append("Switched LLM provider to Ollama due to missing Azure API key")
            
            elif "Production profile using default serial port" in conflict:
                # Clear serial port to force manual configuration
                profile.config.plotter.serial_port = ""
                actions.append("Cleared default serial port for production profile")
            
            elif "Animation enabled with high step count" in conflict:
                # Disable animation for performance
                profile.config.visualization.enable_animation = False
                actions.append("Disabled animation due to high step count")
        
        return actions


# Global profile manager instance
_profile_manager = ProfileManager()


def get_profile_manager() -> ProfileManager:
    """
    Get global profile manager instance
    
    Returns:
        Global profile manager
    """
    return _profile_manager


def switch_profile(name: str) -> bool:
    """
    Switch to a different profile
    
    Args:
        name: Name of profile to switch to
        
    Returns:
        True if switch successful
    """
    return _profile_manager.switch_profile(name)


def get_active_profile() -> Optional[ConfigurationProfile]:
    """
    Get currently active profile
    
    Returns:
        Active profile or None if no profile is active
    """
    return _profile_manager.get_active_profile()


def list_profiles() -> List[str]:
    """
    List all available profile names
    
    Returns:
        List of profile names
    """
    return _profile_manager.list_profiles()


def create_profile(
    name: str,
    base_profile: Optional[str] = None,
    profile_type: ProfileType = ProfileType.CUSTOM,
    description: str = "",
    inheritance_mode: InheritanceMode = InheritanceMode.MERGE
) -> ConfigurationProfile:
    """
    Create new profile
    
    Args:
        name: Name for new profile
        base_profile: Name of profile to inherit from
        profile_type: Type of profile
        description: Profile description
        inheritance_mode: How to handle inheritance
        
    Returns:
        New profile object
    """
    return _profile_manager.create_profile(
        name, base_profile, profile_type, description, inheritance_mode
    )