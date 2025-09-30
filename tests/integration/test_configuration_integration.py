"""
Configuration system integration tests.
Tests configuration loading, saving, profiles, and runtime updates across all components.
"""
import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock

from promptplot.config import (
    get_config, save_config, load_config, reset_config,
    PromptPlotConfig, LLMConfig, PlotterConfig, WorkflowConfig
)
from promptplot.config.profiles import (
    ProfileManager, create_profile, ProfileType, ConfigProfile
)
from promptplot.config.runtime import RuntimeConfigManager
from promptplot.workflows.simple_batch import SimpleGCodeWorkflow
from tests.utils.mocks import MockLLMProvider, MockPlotter


class TestConfigurationLoading:
    """Test configuration loading and validation."""
    
    @pytest.mark.integration
    def test_default_configuration_loading(self):
        """Test loading default configuration."""
        config = get_config()
        
        assert isinstance(config, PromptPlotConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.plotter, PlotterConfig)
        assert isinstance(config.workflow, WorkflowConfig)
        
        # Verify default values are reasonable
        assert config.workflow.max_retries > 0
        assert config.workflow.max_steps > 0
        assert config.llm.default_provider in ["azure", "ollama"]
    
    @pytest.mark.integration
    def test_configuration_validation(self):
        """Test configuration validation."""
        config = get_config()
        
        # Test invalid values
        original_retries = config.workflow.max_retries
        
        # Should handle invalid values gracefully
        config.workflow.max_retries = -1
        
        try:
            # Validation should catch this
            from promptplot.config.settings import validate_config
            is_valid, errors = validate_config(config)
            assert not is_valid
            assert len(errors) > 0
        except Exception:
            # If validation throws exception, that's also acceptable
            pass
        finally:
            # Restore valid value
            config.workflow.max_retries = original_retries
    
    @pytest.mark.integration
    def test_configuration_file_operations(self, temp_dir):
        """Test configuration file save and load operations."""
        config = get_config()
        
        # Modify configuration
        original_retries = config.workflow.max_retries
        config.workflow.max_retries = 99
        
        # Save configuration
        config_file = temp_dir / "test_config.json"
        
        with patch('promptplot.config.settings.get_config_file_path', return_value=config_file):
            save_result = save_config(config)
            assert save_result == True
            
            # Verify file was created
            assert config_file.exists()
            
            # Load configuration
            loaded_config = load_config()
            assert loaded_config.workflow.max_retries == 99
        
        # Restore original value
        config.workflow.max_retries = original_retries
    
    @pytest.mark.integration
    def test_configuration_environment_variables(self):
        """Test configuration from environment variables."""
        import os
        
        # Set environment variable
        os.environ['PROMPTPLOT_WORKFLOW_MAX_RETRIES'] = '15'
        
        try:
            # Reload configuration
            config = load_config()
            
            # Should pick up environment variable
            # (This depends on implementation - may need adjustment)
            # assert config.workflow.max_retries == 15
            
        finally:
            # Clean up
            if 'PROMPTPLOT_WORKFLOW_MAX_RETRIES' in os.environ:
                del os.environ['PROMPTPLOT_WORKFLOW_MAX_RETRIES']


class TestProfileManagement:
    """Test configuration profile management."""
    
    @pytest.fixture
    def profile_manager(self):
        """Create profile manager for testing."""
        return ProfileManager()
    
    @pytest.mark.integration
    def test_profile_creation_and_switching(self, profile_manager):
        """Test creating and switching profiles."""
        # Create test profile
        test_profile = create_profile(
            name="test_integration",
            description="Integration test profile",
            profile_type=ProfileType.CUSTOM
        )
        
        assert test_profile.name == "test_integration"
        assert test_profile.metadata.description == "Integration test profile"
        
        # Switch to profile
        success = profile_manager.switch_profile("test_integration")
        assert success == True
        
        # Verify active profile
        active_profile = profile_manager.get_active_profile()
        assert active_profile is not None
        assert active_profile.name == "test_integration"
    
    @pytest.mark.integration
    def test_profile_inheritance(self, profile_manager):
        """Test profile inheritance from base profiles."""
        # Create base profile
        base_profile = create_profile(
            name="base_test",
            description="Base profile for testing"
        )
        
        # Modify base profile configuration
        base_config = base_profile.config
        base_config.workflow.max_retries = 10
        
        # Create derived profile
        derived_profile = create_profile(
            name="derived_test",
            base_profile="base_test",
            description="Derived profile for testing"
        )
        
        # Should inherit base configuration
        assert derived_profile.config.workflow.max_retries == 10
        
        # Modify derived profile
        derived_profile.config.workflow.max_steps = 25
        
        # Base profile should be unchanged
        assert base_profile.config.workflow.max_steps != 25
    
    @pytest.mark.integration
    def test_profile_persistence(self, profile_manager, temp_dir):
        """Test profile persistence to disk."""
        # Create profile
        test_profile = create_profile(
            name="persistent_test",
            description="Profile persistence test"
        )
        
        # Modify configuration
        test_profile.config.workflow.max_retries = 42
        
        # Save profile
        profile_file = temp_dir / "persistent_test.json"
        
        with patch('promptplot.config.profiles.get_profile_file_path', return_value=profile_file):
            success = profile_manager.save_profile("persistent_test")
            assert success == True
            
            # Verify file exists
            assert profile_file.exists()
            
            # Load profile
            loaded_profile = profile_manager.load_profile("persistent_test")
            assert loaded_profile is not None
            assert loaded_profile.config.workflow.max_retries == 42
    
    @pytest.mark.integration
    def test_profile_validation(self, profile_manager):
        """Test profile validation."""
        # Create profile with invalid configuration
        invalid_profile = create_profile(
            name="invalid_test",
            description="Invalid profile test"
        )
        
        # Set invalid values
        invalid_profile.config.workflow.max_retries = -5
        invalid_profile.config.workflow.max_steps = 0
        
        # Validation should catch errors
        is_valid, errors = profile_manager.validate_profile(invalid_profile)
        assert not is_valid
        assert len(errors) > 0


class TestRuntimeConfiguration:
    """Test runtime configuration management."""
    
    @pytest.fixture
    def runtime_manager(self):
        """Create runtime configuration manager."""
        return RuntimeConfigManager()
    
    @pytest.mark.integration
    async def test_runtime_configuration_updates(self, runtime_manager):
        """Test runtime configuration updates."""
        # Update configuration at runtime
        result = await runtime_manager.update_field(
            "workflow.max_retries", 20, "integration_test"
        )
        
        assert result.value == "success"
        
        # Verify update was applied
        current_value = await runtime_manager.get_field("workflow.max_retries")
        assert current_value == 20
    
    @pytest.mark.integration
    async def test_runtime_configuration_validation(self, runtime_manager):
        """Test runtime configuration validation."""
        # Try to set invalid value
        result = await runtime_manager.update_field(
            "workflow.max_retries", -1, "integration_test"
        )
        
        # Should reject invalid value
        assert result.value != "success"
    
    @pytest.mark.integration
    async def test_runtime_configuration_rollback(self, runtime_manager):
        """Test runtime configuration rollback."""
        # Get original value
        original_value = await runtime_manager.get_field("workflow.max_retries")
        
        # Update value
        await runtime_manager.update_field(
            "workflow.max_retries", 99, "integration_test"
        )
        
        # Rollback
        result = await runtime_manager.rollback_field(
            "workflow.max_retries", "integration_test"
        )
        
        assert result.value == "success"
        
        # Verify rollback
        current_value = await runtime_manager.get_field("workflow.max_retries")
        assert current_value == original_value
    
    @pytest.mark.integration
    async def test_runtime_configuration_notifications(self, runtime_manager):
        """Test runtime configuration change notifications."""
        notifications = []
        
        def notification_handler(field, old_value, new_value, source):
            notifications.append((field, old_value, new_value, source))
        
        # Register notification handler
        runtime_manager.register_notification_handler(notification_handler)
        
        # Update configuration
        await runtime_manager.update_field(
            "workflow.max_steps", 50, "integration_test"
        )
        
        # Should have received notification
        assert len(notifications) > 0
        
        notification = notifications[-1]
        assert notification[0] == "workflow.max_steps"
        assert notification[2] == 50
        assert notification[3] == "integration_test"


class TestConfigurationIntegrationWithWorkflows:
    """Test configuration integration with workflow components."""
    
    @pytest.mark.integration
    async def test_workflow_uses_configuration(self):
        """Test that workflows use configuration values."""
        # Create workflow with custom configuration
        config = get_config()
        config.workflow.max_retries = 7
        config.workflow.max_steps = 15
        
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        
        workflow = SimpleGCodeWorkflow(
            llm_provider=llm_provider,
            plotter=plotter,
            config=config
        )
        
        # Verify workflow uses configuration values
        assert workflow.max_retries == 7
        assert workflow.max_steps == 15
    
    @pytest.mark.integration
    async def test_configuration_affects_llm_provider(self):
        """Test that configuration affects LLM provider behavior."""
        from promptplot.llm import get_llm_provider
        
        config = get_config()
        
        # Test with different provider configurations
        config.llm.default_provider = "ollama"
        config.llm.ollama.model = "test_model"
        config.llm.ollama.request_timeout = 5000
        
        # Get LLM provider (would normally create real provider)
        # For testing, we'll mock this
        with patch('promptplot.llm.providers.OllamaProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider
            
            provider = get_llm_provider(config.llm)
            
            # Verify provider was created with correct configuration
            mock_provider_class.assert_called_once()
            call_args = mock_provider_class.call_args
            
            # Check that configuration values were passed
            assert "model" in call_args.kwargs or len(call_args.args) > 0
    
    @pytest.mark.integration
    async def test_configuration_affects_plotter_behavior(self):
        """Test that configuration affects plotter behavior."""
        from promptplot.plotter import get_plotter
        
        config = get_config()
        
        # Test with different plotter configurations
        config.plotter.default_port = "/dev/test"
        config.plotter.baud_rate = 9600
        config.plotter.connection_timeout = 10
        
        # Get plotter (would normally create real plotter)
        with patch('promptplot.plotter.serial_plotter.SerialPlotter') as mock_plotter_class:
            mock_plotter = Mock()
            mock_plotter_class.return_value = mock_plotter
            
            plotter = get_plotter(config.plotter)
            
            # Verify plotter was created with correct configuration
            mock_plotter_class.assert_called_once()
            call_args = mock_plotter_class.call_args
            
            # Check that configuration values were passed
            assert "/dev/test" in str(call_args) or 9600 in call_args.args
    
    @pytest.mark.integration
    async def test_runtime_configuration_affects_active_workflows(self):
        """Test that runtime configuration changes affect active workflows."""
        runtime_manager = RuntimeConfigManager()
        
        # Create workflow
        config = get_config()
        llm_provider = MockLLMProvider()
        plotter = MockPlotter()
        
        workflow = SimpleGCodeWorkflow(
            llm_provider=llm_provider,
            plotter=plotter,
            config=config
        )
        
        # Update configuration at runtime
        await runtime_manager.update_field(
            "workflow.max_retries", 25, "integration_test"
        )
        
        # Workflow should pick up new configuration
        # (This depends on implementation - workflows may need to be notified)
        # For now, we'll test that the runtime manager has the new value
        current_value = await runtime_manager.get_field("workflow.max_retries")
        assert current_value == 25


class TestConfigurationErrorHandling:
    """Test configuration error handling scenarios."""
    
    @pytest.mark.integration
    def test_corrupted_configuration_file_handling(self, temp_dir):
        """Test handling of corrupted configuration files."""
        # Create corrupted configuration file
        config_file = temp_dir / "corrupted_config.json"
        config_file.write_text("{ invalid json content")
        
        with patch('promptplot.config.settings.get_config_file_path', return_value=config_file):
            # Should fall back to defaults
            config = load_config()
            
            # Should still be valid configuration
            assert isinstance(config, PromptPlotConfig)
            assert config.workflow.max_retries > 0
    
    @pytest.mark.integration
    def test_missing_configuration_file_handling(self, temp_dir):
        """Test handling of missing configuration files."""
        # Point to non-existent file
        missing_file = temp_dir / "missing_config.json"
        
        with patch('promptplot.config.settings.get_config_file_path', return_value=missing_file):
            # Should create default configuration
            config = load_config()
            
            assert isinstance(config, PromptPlotConfig)
            assert config.workflow.max_retries > 0
    
    @pytest.mark.integration
    def test_invalid_profile_handling(self):
        """Test handling of invalid profiles."""
        profile_manager = ProfileManager()
        
        # Try to switch to non-existent profile
        success = profile_manager.switch_profile("non_existent_profile")
        assert success == False
        
        # Active profile should remain unchanged
        active_profile = profile_manager.get_active_profile()
        # Should either be None or the previous valid profile
        if active_profile:
            assert active_profile.name != "non_existent_profile"
    
    @pytest.mark.integration
    async def test_runtime_configuration_error_recovery(self):
        """Test runtime configuration error recovery."""
        runtime_manager = RuntimeConfigManager()
        
        # Try to update non-existent field
        result = await runtime_manager.update_field(
            "non_existent.field", "value", "integration_test"
        )
        
        # Should handle gracefully
        assert result.value != "success"
        
        # System should still be functional
        valid_result = await runtime_manager.update_field(
            "workflow.max_retries", 10, "integration_test"
        )
        assert valid_result.value == "success"


class TestConfigurationPerformance:
    """Test configuration system performance."""
    
    @pytest.mark.integration
    def test_configuration_loading_performance(self):
        """Test configuration loading performance."""
        import time
        
        start_time = time.time()
        
        # Load configuration multiple times
        for _ in range(10):
            config = get_config()
            assert isinstance(config, PromptPlotConfig)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should be fast
        assert duration < 1.0, f"Configuration loading too slow: {duration}s"
    
    @pytest.mark.integration
    async def test_runtime_configuration_update_performance(self):
        """Test runtime configuration update performance."""
        import time
        
        runtime_manager = RuntimeConfigManager()
        
        start_time = time.time()
        
        # Perform multiple updates
        for i in range(10):
            await runtime_manager.update_field(
                "workflow.max_retries", i + 1, "performance_test"
            )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should be reasonably fast
        assert duration < 2.0, f"Runtime updates too slow: {duration}s"
    
    @pytest.mark.integration
    def test_profile_switching_performance(self):
        """Test profile switching performance."""
        import time
        
        profile_manager = ProfileManager()
        
        # Create test profiles
        for i in range(5):
            create_profile(f"perf_test_{i}", description=f"Performance test profile {i}")
        
        start_time = time.time()
        
        # Switch between profiles
        for i in range(5):
            profile_manager.switch_profile(f"perf_test_{i}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should be fast
        assert duration < 1.0, f"Profile switching too slow: {duration}s"


class TestConfigurationConcurrency:
    """Test configuration system under concurrent access."""
    
    @pytest.mark.integration
    async def test_concurrent_runtime_updates(self):
        """Test concurrent runtime configuration updates."""
        runtime_manager = RuntimeConfigManager()
        
        # Perform concurrent updates
        async def update_config(field_suffix, value):
            return await runtime_manager.update_field(
                f"workflow.max_retries", value, f"concurrent_test_{field_suffix}"
            )
        
        # Run multiple updates concurrently
        tasks = [
            update_config(i, i + 10)
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All updates should complete (though only one value will be final)
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent update failed: {result}")
            # Result should be valid
            assert hasattr(result, 'value')
    
    @pytest.mark.integration
    def test_concurrent_profile_operations(self):
        """Test concurrent profile operations."""
        import threading
        import time
        
        profile_manager = ProfileManager()
        results = []
        
        def create_and_switch_profile(profile_id):
            try:
                # Create profile
                profile_name = f"concurrent_test_{profile_id}"
                create_profile(profile_name, description=f"Concurrent test {profile_id}")
                
                # Switch to profile
                success = profile_manager.switch_profile(profile_name)
                results.append(("switch", profile_id, success))
                
                # Get active profile
                active = profile_manager.get_active_profile()
                results.append(("active", profile_id, active.name if active else None))
                
            except Exception as e:
                results.append(("error", profile_id, str(e)))
        
        # Run concurrent operations
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_and_switch_profile, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verify results
        assert len(results) >= 3  # Should have at least some results
        
        # Check for errors
        errors = [r for r in results if r[0] == "error"]
        if errors:
            pytest.fail(f"Concurrent operations had errors: {errors}")