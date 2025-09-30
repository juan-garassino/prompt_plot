"""
Command-line interface for PromptPlot v2.0

Complete CLI implementation with full workflow execution capabilities,
configuration management, plotter connection and testing, file plotting,
and interactive mode support.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from colorama import Fore, Style, init

from .config import (
    PromptPlotConfig, get_config, load_config, save_config,
    get_profile_manager, list_profiles, switch_profile,
    get_runtime_manager
)
from .workflows import (
    SimpleGCodeWorkflow, SequentialGCodeWorkflow, 
    SimplePlotterStreamWorkflow, AdvancedPlotterStreamWorkflow
)
from .workflows.plot_enhanced import PlotEnhancedWorkflow
from .workflows.file_plotting import FilePlottingWorkflow
from .plotter import BasePlotter, SerialPlotter, SimulatedPlotter
from .llm import get_llm_provider
from .converters import FileFormatDetector, SupportedFormat
from .strategies import StrategySelector
from .core.exceptions import PromptPlotException

# Initialize colorama for cross-platform color support
init(autoreset=True)


class PromptPlotCLI:
    """Main CLI application class"""
    
    def __init__(self):
        """Initialize CLI application"""
        self.profile_manager = get_profile_manager()
        self.runtime_manager = get_runtime_manager()
        self.strategy_selector = StrategySelector()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load configuration
        self.config = get_config()
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        from .utils.logging import configure_logging, LogLevel
        
        # Configure logging using the new system
        log_level = LogLevel(self.config.log_level.upper())
        configure_logging(level=log_level)
    
    async def run(self, args: Optional[List[str]] = None) -> int:
        """Run CLI application"""
        try:
            parser = self._create_parser()
            
            if args is None:
                args = sys.argv[1:]
            
            parsed_args = parser.parse_args(args)
            
            if not parsed_args.command:
                parser.print_help()
                return 1
            
            # Handle commands
            if parsed_args.command == "workflow":
                return await self._handle_workflow_command(parsed_args)
            elif parsed_args.command == "config":
                return await self._handle_config_command(parsed_args)
            elif parsed_args.command == "plotter":
                return await self._handle_plotter_command(parsed_args)
            elif parsed_args.command == "file":
                return await self._handle_file_command(parsed_args)
            elif parsed_args.command == "interactive":
                return await self._handle_interactive_mode(parsed_args)
            else:
                print(f"{Fore.RED}Unknown command: {parsed_args.command}")
                return 1
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Operation cancelled by user")
            return 130
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}")
            if self.config.debug:
                import traceback
                traceback.print_exc()
            return 1
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with all commands"""
        parser = argparse.ArgumentParser(
            description="PromptPlot v2.0 - LLM-controlled pen plotter system",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  promptplot workflow simple "Draw a circle"
  promptplot workflow advanced "Draw a house with windows" --steps 20
  promptplot file plot drawing.svg --preview
  promptplot config show
  promptplot config set llm.default_provider ollama
  promptplot plotter connect --port /dev/ttyUSB0
  promptplot interactive
            """
        )
        
        parser.add_argument(
            "--version", 
            action="version", 
            version="PromptPlot v2.0.0"
        )
        
        parser.add_argument(
            "--profile",
            help="Configuration profile to use",
            default=None
        )
        
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode"
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Workflow commands
        self._add_workflow_commands(subparsers)
        
        # Configuration commands
        self._add_config_commands(subparsers)
        
        # Plotter commands
        self._add_plotter_commands(subparsers)
        
        # File commands
        self._add_file_commands(subparsers)
        
        # Interactive mode
        self._add_interactive_commands(subparsers)
        
        return parser
    
    def _add_workflow_commands(self, subparsers):
        """Add workflow execution commands"""
        workflow_parser = subparsers.add_parser(
            "workflow", 
            help="Execute drawing workflows",
            description="Execute different types of drawing workflows"
        )
        
        workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_type", help="Workflow types")
        
        # Simple batch workflow
        simple_parser = workflow_subparsers.add_parser("simple", help="Simple batch workflow")
        simple_parser.add_argument("prompt", help="Drawing prompt")
        simple_parser.add_argument("--output", "-o", help="Output file path")
        simple_parser.add_argument("--visualize", action="store_true", help="Show visualization")
        
        # Advanced sequential workflow
        advanced_parser = workflow_subparsers.add_parser("advanced", help="Advanced sequential workflow")
        advanced_parser.add_argument("prompt", help="Drawing prompt")
        advanced_parser.add_argument("--steps", type=int, help="Maximum steps")
        advanced_parser.add_argument("--output", "-o", help="Output file path")
        advanced_parser.add_argument("--visualize", action="store_true", help="Show visualization")
        
        # Simple streaming workflow
        streaming_parser = workflow_subparsers.add_parser("streaming", help="Simple streaming workflow")
        streaming_parser.add_argument("prompt", help="Drawing prompt")
        streaming_parser.add_argument("--port", help="Plotter port")
        streaming_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        
        # Advanced streaming workflow
        advanced_streaming_parser = workflow_subparsers.add_parser("advanced-streaming", help="Advanced streaming workflow")
        advanced_streaming_parser.add_argument("prompt", help="Drawing prompt")
        advanced_streaming_parser.add_argument("--port", help="Plotter port")
        advanced_streaming_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        advanced_streaming_parser.add_argument("--steps", type=int, help="Maximum steps")
        
        # Plot-enhanced workflow
        enhanced_parser = workflow_subparsers.add_parser("enhanced", help="Plot-enhanced workflow with vision")
        enhanced_parser.add_argument("prompt", help="Drawing prompt")
        enhanced_parser.add_argument("--port", help="Plotter port")
        enhanced_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        enhanced_parser.add_argument("--vision", action="store_true", help="Enable vision feedback")
    
    def _add_config_commands(self, subparsers):
        """Add configuration management commands"""
        config_parser = subparsers.add_parser(
            "config", 
            help="Manage configuration",
            description="Show, set, or reset configuration settings"
        )
        
        config_subparsers = config_parser.add_subparsers(dest="config_action", help="Configuration actions")
        
        # Show configuration
        show_parser = config_subparsers.add_parser("show", help="Show current configuration")
        show_parser.add_argument("--section", help="Show specific section (llm, plotter, etc.)")
        show_parser.add_argument("--format", choices=["json", "yaml", "table"], default="table", help="Output format")
        
        # Set configuration
        set_parser = config_subparsers.add_parser("set", help="Set configuration value")
        set_parser.add_argument("key", help="Configuration key (dot notation, e.g., llm.default_provider)")
        set_parser.add_argument("value", help="Configuration value")
        set_parser.add_argument("--runtime", action="store_true", help="Update at runtime")
        
        # Reset configuration
        reset_parser = config_subparsers.add_parser("reset", help="Reset configuration to defaults")
        reset_parser.add_argument("--confirm", action="store_true", help="Confirm reset")
        
        # Profile management
        profile_parser = config_subparsers.add_parser("profile", help="Manage configuration profiles")
        profile_subparsers = profile_parser.add_subparsers(dest="profile_action", help="Profile actions")
        
        profile_subparsers.add_parser("list", help="List available profiles")
        
        switch_parser = profile_subparsers.add_parser("switch", help="Switch to profile")
        switch_parser.add_argument("name", help="Profile name")
        
        create_parser = profile_subparsers.add_parser("create", help="Create new profile")
        create_parser.add_argument("name", help="Profile name")
        create_parser.add_argument("--base", help="Base profile to inherit from")
        create_parser.add_argument("--description", help="Profile description")
        
        save_parser = profile_subparsers.add_parser("save", help="Save profile to file")
        save_parser.add_argument("name", help="Profile name")
        save_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing file")
    
    def _add_plotter_commands(self, subparsers):
        """Add plotter management commands"""
        plotter_parser = subparsers.add_parser(
            "plotter", 
            help="Plotter operations",
            description="Connect, test, and manage plotter connections"
        )
        
        plotter_subparsers = plotter_parser.add_subparsers(dest="plotter_action", help="Plotter actions")
        
        # Connect to plotter
        connect_parser = plotter_subparsers.add_parser("connect", help="Connect to plotter")
        connect_parser.add_argument("--port", help="Serial port (e.g., /dev/ttyUSB0)")
        connect_parser.add_argument("--baud", type=int, help="Baud rate")
        connect_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        
        # Test plotter
        test_parser = plotter_subparsers.add_parser("test", help="Test plotter connection")
        test_parser.add_argument("--port", help="Serial port")
        test_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        test_parser.add_argument("--commands", nargs="+", help="Test commands to send")
        
        # Show plotter status
        status_parser = plotter_subparsers.add_parser("status", help="Show plotter status")
        status_parser.add_argument("--port", help="Serial port")
        
        # List available ports
        plotter_subparsers.add_parser("list-ports", help="List available serial ports")
    
    def _add_file_commands(self, subparsers):
        """Add file plotting commands"""
        file_parser = subparsers.add_parser(
            "file", 
            help="File plotting operations",
            description="Plot files directly (G-code, SVG, DXF, etc.)"
        )
        
        file_subparsers = file_parser.add_subparsers(dest="file_action", help="File actions")
        
        # Plot file
        plot_parser = file_subparsers.add_parser("plot", help="Plot a file")
        plot_parser.add_argument("file", help="File to plot")
        plot_parser.add_argument("--preview", action="store_true", help="Preview only, don't plot")
        plot_parser.add_argument("--port", help="Plotter port")
        plot_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        plot_parser.add_argument("--scale", type=float, nargs=3, help="Scale factors (x y z)")
        plot_parser.add_argument("--offset", type=float, nargs=3, help="Offset values (x y z)")
        plot_parser.add_argument("--speed", type=int, help="Feed rate override")
        
        # Convert file
        convert_parser = file_subparsers.add_parser("convert", help="Convert file to G-code")
        convert_parser.add_argument("input", help="Input file")
        convert_parser.add_argument("output", help="Output G-code file")
        convert_parser.add_argument("--format", help="Force input format")
        
        # Validate file
        validate_parser = file_subparsers.add_parser("validate", help="Validate file format")
        validate_parser.add_argument("file", help="File to validate")
        
        # Batch plot
        batch_parser = file_subparsers.add_parser("batch", help="Plot multiple files")
        batch_parser.add_argument("files", nargs="+", help="Files to plot")
        batch_parser.add_argument("--port", help="Plotter port")
        batch_parser.add_argument("--simulate", action="store_true", help="Use simulated plotter")
        batch_parser.add_argument("--delay", type=float, help="Delay between files")
    
    def _add_interactive_commands(self, subparsers):
        """Add interactive mode command"""
        interactive_parser = subparsers.add_parser(
            "interactive", 
            help="Interactive mode",
            description="Start interactive mode for workflow selection and execution"
        )
        interactive_parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    
    async def _handle_workflow_command(self, args) -> int:
        """Handle workflow execution commands"""
        if not args.workflow_type:
            print(f"{Fore.RED}No workflow type specified")
            return 1
        
        # Switch profile if specified
        if args.profile:
            if not switch_profile(args.profile):
                print(f"{Fore.RED}Failed to switch to profile: {args.profile}")
                return 1
            print(f"{Fore.GREEN}Switched to profile: {args.profile}")
        
        # Enable debug if requested
        if args.debug:
            self.config.debug = True
            logging.getLogger().setLevel(logging.DEBUG)
        
        try:
            # Get LLM provider
            llm_provider = get_llm_provider(self.config.llm)
            
            # Determine plotter
            plotter = await self._get_plotter(args)
            
            # Execute workflow based on type
            if args.workflow_type == "simple":
                return await self._execute_simple_workflow(args, llm_provider, plotter)
            elif args.workflow_type == "advanced":
                return await self._execute_advanced_workflow(args, llm_provider, plotter)
            elif args.workflow_type == "streaming":
                return await self._execute_streaming_workflow(args, llm_provider, plotter)
            elif args.workflow_type == "advanced-streaming":
                return await self._execute_advanced_streaming_workflow(args, llm_provider, plotter)
            elif args.workflow_type == "enhanced":
                return await self._execute_enhanced_workflow(args, llm_provider, plotter)
            else:
                print(f"{Fore.RED}Unknown workflow type: {args.workflow_type}")
                return 1
                
        except Exception as e:
            print(f"{Fore.RED}Workflow execution failed: {str(e)}")
            if self.config.debug:
                import traceback
                traceback.print_exc()
            return 1
    
    async def _execute_simple_workflow(self, args, llm_provider, plotter) -> int:
        """Execute simple batch workflow"""
        print(f"{Fore.CYAN}Executing simple batch workflow...")
        print(f"Prompt: {args.prompt}")
        
        # Analyze prompt and select strategy
        strategy = self.strategy_selector.select_strategy(args.prompt)
        print(f"Selected strategy: {strategy.__class__.__name__}")
        
        # Show progress
        print(f"{Fore.YELLOW}Initializing workflow...")
        
        # Create and run workflow
        workflow = SimpleGCodeWorkflow(
            llm=llm_provider,
            max_retries=self.config.workflow.max_retries,
            max_steps=self.config.workflow.max_steps
        )
        
        print(f"{Fore.YELLOW}Generating G-code...")
        start_time = time.time()
        
        result = await workflow.run(prompt=args.prompt)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Show completion status
        print(f"{Fore.GREEN}✓ G-code generation completed in {duration:.2f} seconds")
        
        if hasattr(result, 'gcode_program') and result.gcode_program:
            command_count = len(result.gcode_program.commands)
            print(f"Generated {command_count} G-code commands")
        
        # Handle output
        if args.output:
            self._save_result(result, args.output)
        
        if args.visualize:
            await self._visualize_result(result)
        
        print(f"{Fore.GREEN}Simple workflow completed successfully")
        return 0
    
    async def _execute_advanced_workflow(self, args, llm_provider, plotter) -> int:
        """Execute advanced sequential workflow"""
        print(f"{Fore.CYAN}Executing advanced sequential workflow...")
        print(f"Prompt: {args.prompt}")
        
        max_steps = args.steps or self.config.workflow.max_steps
        print(f"Maximum steps: {max_steps}")
        
        # Show progress
        print(f"{Fore.YELLOW}Initializing sequential workflow...")
        
        # Create and run workflow
        workflow = SequentialGCodeWorkflow(
            llm=llm_provider,
            max_retries=self.config.workflow.max_retries,
            max_steps=max_steps
        )
        
        print(f"{Fore.YELLOW}Generating G-code step by step...")
        start_time = time.time()
        
        result = await workflow.run(prompt=args.prompt)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Show completion status
        print(f"{Fore.GREEN}✓ Sequential generation completed in {duration:.2f} seconds")
        
        if hasattr(result, 'gcode_program') and result.gcode_program:
            command_count = len(result.gcode_program.commands)
            print(f"Generated {command_count} G-code commands")
        
        # Handle output
        if args.output:
            self._save_result(result, args.output)
        
        if args.visualize:
            await self._visualize_result(result)
        
        print(f"{Fore.GREEN}Advanced workflow completed successfully")
        return 0
    
    async def _execute_streaming_workflow(self, args, llm_provider, plotter) -> int:
        """Execute simple streaming workflow"""
        print(f"{Fore.CYAN}Executing simple streaming workflow...")
        print(f"Prompt: {args.prompt}")
        print(f"Plotter: {plotter.__class__.__name__} on {plotter.port}")
        
        # Show progress
        print(f"{Fore.YELLOW}Initializing streaming workflow...")
        print(f"{Fore.YELLOW}Connecting to plotter...")
        
        # Create and run workflow
        workflow = SimplePlotterStreamWorkflow(
            llm=llm_provider,
            plotter=plotter,
            max_retries=self.config.workflow.max_retries,
            max_steps=self.config.workflow.max_steps
        )
        
        print(f"{Fore.YELLOW}Starting real-time G-code generation and plotting...")
        start_time = time.time()
        
        result = await workflow.run(prompt=args.prompt)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Show completion status
        print(f"{Fore.GREEN}✓ Streaming workflow completed in {duration:.2f} seconds")
        
        print(f"{Fore.GREEN}Streaming workflow completed successfully")
        return 0
    
    async def _execute_advanced_streaming_workflow(self, args, llm_provider, plotter) -> int:
        """Execute advanced streaming workflow"""
        print(f"{Fore.CYAN}Executing advanced streaming workflow...")
        print(f"Prompt: {args.prompt}")
        print(f"Plotter: {plotter.__class__.__name__} on {plotter.port}")
        
        max_steps = args.steps or self.config.workflow.max_steps
        print(f"Maximum steps: {max_steps}")
        
        # Show progress
        print(f"{Fore.YELLOW}Initializing advanced streaming workflow...")
        print(f"{Fore.YELLOW}Connecting to plotter with enhanced features...")
        
        # Create and run workflow
        workflow = AdvancedPlotterStreamWorkflow(
            llm=llm_provider,
            plotter=plotter,
            max_retries=self.config.workflow.max_retries,
            max_steps=max_steps
        )
        
        print(f"{Fore.YELLOW}Starting advanced real-time generation with visualization...")
        start_time = time.time()
        
        result = await workflow.run(prompt=args.prompt)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Show completion status
        print(f"{Fore.GREEN}✓ Advanced streaming completed in {duration:.2f} seconds")
        
        print(f"{Fore.GREEN}Advanced streaming workflow completed successfully")
        return 0
    
    async def _execute_enhanced_workflow(self, args, llm_provider, plotter) -> int:
        """Execute plot-enhanced workflow with vision"""
        print(f"{Fore.CYAN}Executing plot-enhanced workflow...")
        print(f"Prompt: {args.prompt}")
        print(f"Vision enabled: {args.vision}")
        
        if not self.config.vision.enable_plot_analysis:
            print(f"{Fore.YELLOW}Warning: Plot analysis is disabled in configuration")
        
        # Show progress
        print(f"{Fore.YELLOW}Initializing plot-enhanced workflow with vision capabilities...")
        
        # Create and run workflow
        workflow = PlotEnhancedWorkflow(
            llm=llm_provider,
            plotter=plotter,
            max_retries=self.config.workflow.max_retries,
            max_steps=self.config.workflow.max_steps,
            enable_vision=args.vision
        )
        
        print(f"{Fore.YELLOW}Starting intelligent drawing with visual feedback...")
        start_time = time.time()
        
        result = await workflow.run(prompt=args.prompt)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Show completion status
        print(f"{Fore.GREEN}✓ Enhanced workflow completed in {duration:.2f} seconds")
        
        if args.vision:
            print(f"{Fore.GREEN}Visual feedback analysis completed")
        
        print(f"{Fore.GREEN}Enhanced workflow completed successfully")
        return 0
    
    async def _handle_config_command(self, args) -> int:
        """Handle configuration management commands"""
        if not args.config_action:
            print(f"{Fore.RED}No configuration action specified")
            return 1
        
        try:
            if args.config_action == "show":
                return await self._show_config(args)
            elif args.config_action == "set":
                return await self._set_config(args)
            elif args.config_action == "reset":
                return await self._reset_config(args)
            elif args.config_action == "profile":
                return await self._handle_profile_command(args)
            else:
                print(f"{Fore.RED}Unknown config action: {args.config_action}")
                return 1
                
        except Exception as e:
            print(f"{Fore.RED}Configuration command failed: {str(e)}")
            return 1
    
    async def _show_config(self, args) -> int:
        """Show current configuration"""
        config = get_config()
        
        if args.section:
            # Show specific section
            section_data = getattr(config, args.section, None)
            if section_data is None:
                print(f"{Fore.RED}Unknown configuration section: {args.section}")
                return 1
            
            if args.format == "json":
                print(json.dumps(self._dataclass_to_dict(section_data), indent=2))
            elif args.format == "yaml":
                import yaml
                print(yaml.dump(self._dataclass_to_dict(section_data), default_flow_style=False))
            else:
                self._print_config_table(args.section, section_data)
        else:
            # Show all configuration
            if args.format == "json":
                # Convert config to dict for JSON serialization
                import dataclasses
                config_dict = dataclasses.asdict(config)
                print(json.dumps(config_dict, indent=2))
            elif args.format == "yaml":
                import yaml
                import dataclasses
                config_dict = dataclasses.asdict(config)
                print(yaml.dump(config_dict, default_flow_style=False))
            else:
                self._print_full_config_table(config)
        
        return 0
    
    async def _set_config(self, args) -> int:
        """Set configuration value"""
        try:
            # Convert value to appropriate type
            value = self._convert_config_value(args.value)
            
            if args.runtime:
                # Update at runtime
                result = await self.runtime_manager.update_field(args.key, value, "cli")
                if result.value == "success":
                    print(f"{Fore.GREEN}Configuration updated at runtime: {args.key} = {value}")
                    return 0
                else:
                    print(f"{Fore.RED}Runtime update failed: {result.value}")
                    return 1
            else:
                # Update configuration and save
                config = get_config()
                self._set_nested_value(config, args.key, value)
                
                # Save configuration
                try:
                    save_config(config)
                    print(f"{Fore.GREEN}Configuration saved: {args.key} = {value}")
                    return 0
                except Exception as e:
                    print(f"{Fore.RED}Failed to save configuration: {e}")
                    return 1
                else:
                    print(f"{Fore.RED}Failed to save configuration")
                    return 1
                    
        except Exception as e:
            print(f"{Fore.RED}Failed to set configuration: {str(e)}")
            return 1
    
    async def _reset_config(self, args) -> int:
        """Reset configuration to defaults"""
        if not args.confirm:
            print(f"{Fore.YELLOW}This will reset all configuration to defaults.")
            response = input("Are you sure? (y/N): ")
            if response.lower() != 'y':
                print("Reset cancelled")
                return 0
        
        try:
            from .config import reset_config
            reset_config()
            print(f"{Fore.GREEN}Configuration reset to defaults")
            return 0
        except Exception as e:
            print(f"{Fore.RED}Failed to reset configuration: {e}")
            return 1
    
    async def _handle_profile_command(self, args) -> int:
        """Handle profile management commands"""
        if not args.profile_action:
            print(f"{Fore.RED}No profile action specified")
            return 1
        
        if args.profile_action == "list":
            profiles = list_profiles()
            active_profile = self.profile_manager.get_active_profile()
            
            print(f"{Fore.CYAN}Available profiles:")
            for profile_name in profiles:
                profile = self.profile_manager.get_profile(profile_name)
                marker = f"{Fore.GREEN}*" if active_profile and active_profile.name == profile_name else " "
                print(f"{marker} {profile_name} ({profile.metadata.profile_type.value})")
                if profile.metadata.description:
                    print(f"    {profile.metadata.description}")
            
            return 0
        
        elif args.profile_action == "switch":
            if switch_profile(args.name):
                print(f"{Fore.GREEN}Switched to profile: {args.name}")
                return 0
            else:
                print(f"{Fore.RED}Failed to switch to profile: {args.name}")
                return 1
        
        elif args.profile_action == "create":
            from .config.profiles import create_profile, ProfileType
            
            try:
                profile = create_profile(
                    name=args.name,
                    base_profile=args.base,
                    description=args.description or ""
                )
                print(f"{Fore.GREEN}Created profile: {args.name}")
                return 0
            except Exception as e:
                print(f"{Fore.RED}Failed to create profile: {str(e)}")
                return 1
        
        elif args.profile_action == "save":
            if self.profile_manager.save_profile(args.name, args.overwrite):
                print(f"{Fore.GREEN}Saved profile: {args.name}")
                return 0
            else:
                print(f"{Fore.RED}Failed to save profile: {args.name}")
                return 1
        
        else:
            print(f"{Fore.RED}Unknown profile action: {args.profile_action}")
            return 1
    
    async def _handle_plotter_command(self, args) -> int:
        """Handle plotter management commands"""
        if not args.plotter_action:
            print(f"{Fore.RED}No plotter action specified")
            return 1
        
        try:
            if args.plotter_action == "connect":
                return await self._connect_plotter(args)
            elif args.plotter_action == "test":
                return await self._test_plotter(args)
            elif args.plotter_action == "status":
                return await self._show_plotter_status(args)
            elif args.plotter_action == "list-ports":
                return await self._list_serial_ports()
            else:
                print(f"{Fore.RED}Unknown plotter action: {args.plotter_action}")
                return 1
                
        except Exception as e:
            print(f"{Fore.RED}Plotter command failed: {str(e)}")
            return 1
    
    async def _connect_plotter(self, args) -> int:
        """Connect to plotter"""
        plotter = await self._get_plotter(args)
        
        print(f"{Fore.CYAN}Connecting to plotter...")
        
        try:
            async with plotter:
                print(f"{Fore.GREEN}Successfully connected to plotter")
                status = plotter.get_status()
                print(f"Status: {status}")
                return 0
        except Exception as e:
            print(f"{Fore.RED}Failed to connect: {str(e)}")
            return 1
    
    async def _test_plotter(self, args) -> int:
        """Test plotter connection"""
        plotter = await self._get_plotter(args)
        
        test_commands = args.commands or ["G0 X0 Y0", "G1 X10 Y10 F1000", "G0 X0 Y0"]
        
        print(f"{Fore.CYAN}Testing plotter with commands: {test_commands}")
        
        try:
            async with plotter:
                for command in test_commands:
                    print(f"Sending: {command}")
                    success = await plotter.send_command(command)
                    if success:
                        print(f"{Fore.GREEN}✓ Command successful")
                    else:
                        print(f"{Fore.RED}✗ Command failed")
                        return 1
                
                print(f"{Fore.GREEN}All test commands successful")
                return 0
                
        except Exception as e:
            print(f"{Fore.RED}Test failed: {str(e)}")
            return 1
    
    async def _show_plotter_status(self, args) -> int:
        """Show plotter status"""
        plotter = await self._get_plotter(args)
        
        try:
            status = plotter.get_status()
            print(f"{Fore.CYAN}Plotter Status:")
            print(f"  Port: {plotter.port}")
            print(f"  Connected: {plotter.is_connected}")
            print(f"  Busy: {status.is_busy}")
            print(f"  Last Command: {status.current_command}")
            print(f"  Queue Size: {status.queue_size}")
            print(f"  Last Update: {status.last_update}")
            
            if hasattr(status, 'baud_rate'):
                print(f"  Baud Rate: {status.baud_rate}")
                print(f"  Bytes Sent: {status.bytes_sent}")
                print(f"  Bytes Received: {status.bytes_received}")
            
            return 0
            
        except Exception as e:
            print(f"{Fore.RED}Failed to get status: {str(e)}")
            return 1
    
    async def _list_serial_ports(self) -> int:
        """List available serial ports"""
        try:
            import serial.tools.list_ports
            
            ports = serial.tools.list_ports.comports()
            
            if not ports:
                print(f"{Fore.YELLOW}No serial ports found")
                return 0
            
            print(f"{Fore.CYAN}Available serial ports:")
            for port in ports:
                print(f"  {port.device} - {port.description}")
                if port.manufacturer:
                    print(f"    Manufacturer: {port.manufacturer}")
            
            return 0
            
        except ImportError:
            print(f"{Fore.RED}pyserial not installed. Install with: pip install pyserial")
            return 1
        except Exception as e:
            print(f"{Fore.RED}Failed to list ports: {str(e)}")
            return 1
    
    async def _handle_file_command(self, args) -> int:
        """Handle file plotting commands"""
        if not args.file_action:
            print(f"{Fore.RED}No file action specified")
            return 1
        
        try:
            if args.file_action == "plot":
                return await self._plot_file(args)
            elif args.file_action == "convert":
                return await self._convert_file(args)
            elif args.file_action == "validate":
                return await self._validate_file(args)
            elif args.file_action == "batch":
                return await self._batch_plot_files(args)
            else:
                print(f"{Fore.RED}Unknown file action: {args.file_action}")
                return 1
                
        except Exception as e:
            print(f"{Fore.RED}File command failed: {str(e)}")
            return 1
    
    async def _plot_file(self, args) -> int:
        """Plot a file"""
        file_path = Path(args.file)
        
        if not file_path.exists():
            print(f"{Fore.RED}File not found: {file_path}")
            return 1
        
        try:
            # Detect file format
            detector = FileFormatDetector()
            file_format = detector.detect_format(file_path)
            
            if file_format == SupportedFormat.UNKNOWN:
                print(f"{Fore.RED}Unsupported file format: {file_path}")
                return 1
            
            print(f"{Fore.CYAN}Plotting file: {file_path}")
            print(f"Detected format: {file_format.value}")
            
            # Create plotting parameters
            from .workflows.file_plotting import PlottingParameters
            
            params = PlottingParameters()
            if args.scale:
                params.scale = tuple(args.scale)
            if args.offset:
                params.offset = tuple(args.offset)
            if args.speed:
                params.speed = args.speed
            
            # Get plotter
            plotter = await self._get_plotter(args) if not args.preview else None
            
            # Create and run file plotting workflow
            workflow = FilePlottingWorkflow(plotter=plotter)
            
            mode = "preview" if args.preview else "execute"
            result = await workflow.plot_file(file_path, params, mode)
            
            if args.preview:
                print(f"{Fore.GREEN}File preview completed")
                # Show preview visualization
                await self._visualize_result(result)
            else:
                print(f"{Fore.GREEN}File plotting completed")
            
            return 0
            
        except ImportError as e:
            print(f"{Fore.RED}File plotting dependencies not available: {str(e)}")
            print(f"{Fore.YELLOW}File plotting functionality requires additional components to be implemented")
            return 1
        except Exception as e:
            print(f"{Fore.RED}File plotting failed: {str(e)}")
            return 1
    
    async def _convert_file(self, args) -> int:
        """Convert file to G-code"""
        try:
            input_path = Path(args.input)
            output_path = Path(args.output)
            
            if not input_path.exists():
                print(f"{Fore.RED}Input file not found: {input_path}")
                return 1
            
            # Detect or use specified format
            detector = FileFormatDetector()
            file_format = SupportedFormat(args.format) if args.format else detector.detect_format(input_path)
            
            if file_format == SupportedFormat.UNKNOWN:
                print(f"{Fore.RED}Unsupported file format: {input_path}")
                return 1
            
            print(f"{Fore.CYAN}Converting {input_path} to {output_path}")
            print(f"Input format: {file_format.value}")
            
            # Create file plotting workflow for conversion
            workflow = FilePlottingWorkflow()
            result = await workflow.convert_file(input_path, output_path, file_format)
            
            if result.success:
                print(f"{Fore.GREEN}Conversion completed successfully")
                return 0
            else:
                print(f"{Fore.RED}Conversion failed: {result.error}")
                return 1
                
        except ImportError as e:
            print(f"{Fore.RED}File conversion dependencies not available: {str(e)}")
            print(f"{Fore.YELLOW}File conversion functionality requires additional components to be implemented")
            return 1
        except Exception as e:
            print(f"{Fore.RED}File conversion failed: {str(e)}")
            return 1
    
    async def _validate_file(self, args) -> int:
        """Validate file format"""
        try:
            file_path = Path(args.file)
            
            if not file_path.exists():
                print(f"{Fore.RED}File not found: {file_path}")
                return 1
            
            # Detect file format
            detector = FileFormatDetector()
            file_format = detector.detect_format(file_path)
            
            print(f"{Fore.CYAN}Validating file: {file_path}")
            print(f"Detected format: {file_format.value}")
            
            if file_format == SupportedFormat.UNKNOWN:
                print(f"{Fore.RED}Unsupported or invalid file format")
                return 1
            
            # Perform format-specific validation
            workflow = FilePlottingWorkflow()
            validation_result = await workflow.validate_file(file_path, file_format)
            
            if validation_result.is_valid:
                print(f"{Fore.GREEN}File is valid")
                if validation_result.metadata:
                    print("File metadata:")
                    for key, value in validation_result.metadata.items():
                        print(f"  {key}: {value}")
                return 0
            else:
                print(f"{Fore.RED}File validation failed:")
                for error in validation_result.errors:
                    print(f"  - {error}")
                return 1
                
        except ImportError as e:
            print(f"{Fore.RED}File validation dependencies not available: {str(e)}")
            print(f"{Fore.YELLOW}File validation functionality requires additional components to be implemented")
            return 1
        except Exception as e:
            print(f"{Fore.RED}Validation error: {str(e)}")
            return 1
    
    async def _batch_plot_files(self, args) -> int:
        """Plot multiple files in batch"""
        try:
            files = [Path(f) for f in args.files]
            
            # Check all files exist
            missing_files = [f for f in files if not f.exists()]
            if missing_files:
                print(f"{Fore.RED}Missing files:")
                for f in missing_files:
                    print(f"  - {f}")
                return 1
            
            print(f"{Fore.CYAN}Batch plotting {len(files)} files...")
            
            # Get plotter
            plotter = await self._get_plotter(args)
            
            # Create file plotting workflow
            workflow = FilePlottingWorkflow(plotter=plotter)
            
            success_count = 0
            
            for i, file_path in enumerate(files, 1):
                print(f"\n{Fore.CYAN}[{i}/{len(files)}] Plotting: {file_path}")
                
                try:
                    result = await workflow.plot_file(file_path)
                    if result.success:
                        print(f"{Fore.GREEN}✓ Completed successfully")
                        success_count += 1
                    else:
                        print(f"{Fore.RED}✗ Failed: {result.error}")
                    
                    # Delay between files if specified
                    if args.delay and i < len(files):
                        print(f"Waiting {args.delay} seconds...")
                        await asyncio.sleep(args.delay)
                        
                except Exception as e:
                    print(f"{Fore.RED}✗ Error: {str(e)}")
            
            print(f"\n{Fore.CYAN}Batch plotting completed: {success_count}/{len(files)} successful")
            return 0 if success_count == len(files) else 1
            
        except ImportError as e:
            print(f"{Fore.RED}Batch plotting dependencies not available: {str(e)}")
            print(f"{Fore.YELLOW}Batch plotting functionality requires additional components to be implemented")
            return 1
        except Exception as e:
            print(f"{Fore.RED}Batch plotting failed: {str(e)}")
            return 1
    
    async def _handle_interactive_mode(self, args) -> int:
        """Handle interactive mode"""
        print(f"{Fore.CYAN}PromptPlot v2.0 Interactive Mode")
        print("Type 'help' for available commands, 'quit' to exit")
        
        while True:
            try:
                command = input(f"\n{Fore.GREEN}promptplot> {Style.RESET_ALL}").strip()
                
                if not command:
                    continue
                
                if command.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if command.lower() == 'help':
                    self._show_interactive_help()
                    continue
                
                # Parse and execute command
                try:
                    # Split command into arguments
                    cmd_args = command.split()
                    result = await self.run(cmd_args)
                    
                    if result != 0:
                        print(f"{Fore.YELLOW}Command completed with status: {result}")
                        
                except SystemExit:
                    # Ignore SystemExit from argparse
                    pass
                except Exception as e:
                    print(f"{Fore.RED}Command error: {str(e)}")
                    
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Use 'quit' to exit")
            except EOFError:
                print("\nGoodbye!")
                break
        
        return 0
    
    def _show_interactive_help(self):
        """Show interactive mode help"""
        print(f"""
{Fore.CYAN}Available commands:

Workflows:
  workflow simple "prompt"              - Execute simple batch workflow
  workflow advanced "prompt"            - Execute advanced sequential workflow
  workflow streaming "prompt"           - Execute streaming workflow
  workflow enhanced "prompt" --vision   - Execute vision-enhanced workflow

Configuration:
  config show                          - Show current configuration
  config show --section llm            - Show specific section
  config set key value                 - Set configuration value
  config profile list                  - List available profiles
  config profile switch name           - Switch to profile

Plotter:
  plotter connect --port /dev/ttyUSB0  - Connect to plotter
  plotter test                         - Test plotter connection
  plotter status                       - Show plotter status
  plotter list-ports                   - List available ports

Files:
  file plot drawing.svg --preview      - Preview file plotting
  file plot drawing.gcode              - Plot G-code file
  file convert input.svg output.gcode  - Convert file to G-code
  file validate drawing.svg            - Validate file format

General:
  help                                 - Show this help
  quit                                 - Exit interactive mode
        """)
    
    async def _get_plotter(self, args) -> BasePlotter:
        """Get plotter instance based on arguments and configuration"""
        if hasattr(args, 'simulate') and args.simulate:
            return SimulatedPlotter(
                port="SIMULATED",
                visualize=self.config.plotter.simulated_visualization
            )
        
        port = getattr(args, 'port', None) or self.config.plotter.serial_port
        
        if not port or port == "SIMULATED":
            return SimulatedPlotter(
                port="SIMULATED",
                visualize=self.config.plotter.simulated_visualization
            )
        
        return SerialPlotter(
            port=port,
            baud_rate=getattr(args, 'baud', None) or self.config.plotter.serial_baud_rate,
            timeout=self.config.plotter.serial_timeout
        )
    
    def _save_result(self, result, output_path: str):
        """Save workflow result to file"""
        output_file = Path(output_path)
        
        try:
            if hasattr(result, 'gcode_program'):
                # Save G-code
                with open(output_file, 'w') as f:
                    for command in result.gcode_program.commands:
                        f.write(f"{command.to_gcode()}\n")
                print(f"{Fore.GREEN}Result saved to: {output_file}")
            else:
                # Save as JSON
                with open(output_file, 'w') as f:
                    json.dump(result.__dict__, f, indent=2, default=str)
                print(f"{Fore.GREEN}Result saved to: {output_file}")
                
        except Exception as e:
            print(f"{Fore.RED}Failed to save result: {str(e)}")
    
    async def _visualize_result(self, result):
        """Visualize workflow result"""
        try:
            from .plotter.visualizer import PlotterVisualizer
            
            visualizer = PlotterVisualizer(
                width=self.config.visualization.figure_width,
                height=self.config.visualization.figure_height,
                dpi=self.config.visualization.figure_dpi
            )
            
            if hasattr(result, 'gcode_program'):
                visualizer.visualize_gcode_program(result.gcode_program)
            
            visualizer.show()
            
        except Exception as e:
            print(f"{Fore.YELLOW}Visualization failed: {str(e)}")
    
    def _convert_config_value(self, value_str: str):
        """Convert string value to appropriate type"""
        # Try boolean
        if value_str.lower() in ['true', 'yes', '1']:
            return True
        elif value_str.lower() in ['false', 'no', '0']:
            return False
        
        # Try number
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Return as string
        return value_str
    
    def _set_nested_value(self, obj, key_path: str, value):
        """Set nested object value using dot notation"""
        keys = key_path.split('.')
        current = obj
        
        for key in keys[:-1]:
            current = getattr(current, key)
        
        setattr(current, keys[-1], value)
    
    def _dataclass_to_dict(self, obj) -> Dict[str, Any]:
        """Convert dataclass to dictionary"""
        from dataclasses import fields, is_dataclass
        
        if not is_dataclass(obj):
            return obj
        
        result = {}
        for field in fields(obj):
            value = getattr(obj, field.name)
            if is_dataclass(value):
                result[field.name] = self._dataclass_to_dict(value)
            else:
                result[field.name] = value
        
        return result
    
    def _print_config_table(self, section_name: str, section_data):
        """Print configuration section as table"""
        print(f"\n{Fore.CYAN}{section_name.upper()} Configuration:")
        print("-" * 50)
        
        from dataclasses import fields
        
        for field in fields(section_data):
            value = getattr(section_data, field.name)
            print(f"{field.name:30} : {value}")
    
    def _print_full_config_table(self, config):
        """Print full configuration as table"""
        sections = ['llm', 'plotter', 'visualization', 'workflow', 'vision']
        
        for section in sections:
            section_data = getattr(config, section)
            self._print_config_table(section, section_data)
            print()
        
        # Print top-level settings
        print(f"{Fore.CYAN}GLOBAL Configuration:")
        print("-" * 50)
        print(f"{'debug':30} : {config.debug}")
        print(f"{'log_level':30} : {config.log_level}")
        print(f"{'log_file':30} : {config.log_file}")
        print(f"{'validation_level':30} : {config.validation_level}")
        print(f"{'strict_mode':30} : {config.strict_mode}")


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entry point"""
    try:
        cli = PromptPlotCLI()
        return asyncio.run(cli.run(args))
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user")
        return 130
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())