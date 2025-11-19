#!/usr/bin/env python3
"""
Port Manager for Friday Memory MCP Server

Handles intelligent port binding:
- Detects calling program (VS Code, LM Studio, Ollama, etc.)
- Checks port availability
- Falls back to backup ports if needed
- Stores port info for client discovery
"""

import asyncio
import json
import logging
import os
import psutil
import socket
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CallerProgram(Enum):
    """Known calling programs for the MCP server"""
    VSCODE = "vscode"
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"
    OPENWEBUI = "openwebui"
    UNKNOWN = "unknown"


class PortManager:
    """
    Manages port binding and fallback logic for the MCP server.
    
    Tries to bind to primary port, falls back to backup ports if unavailable.
    Stores active port info for client discovery.
    """
    
    # Primary and backup ports
    PRIMARY_PORT = 21434
    BACKUP_PORTS = [21435, 21436, 21437, 21438, 21439]  # Fallback range
    
    # Port info file for clients to discover which port we're on
    PORT_INFO_FILENAME = "mcp_server_port.json"
    
    def __init__(self, memory_data_path: str):
        """Initialize port manager
        
        Args:
            memory_data_path: Path to Friday's memory_data directory
        """
        self.memory_data_path = Path(memory_data_path)
        self.active_port: Optional[int] = None
        self.caller_program: CallerProgram = CallerProgram.UNKNOWN
        self.process_id = os.getpid()
        
        # Ensure memory_data exists
        self.memory_data_path.mkdir(parents=True, exist_ok=True)
    
    def detect_caller_program(self) -> CallerProgram:
        """
        Detect which program is running/importing the MCP server.
        
        Returns:
            CallerProgram enum indicating the calling program
        """
        try:
            current_process = psutil.Process(self.process_id)
            parent_process = current_process.parent()
            
            # Get parent process name
            parent_name = parent_process.name().lower()
            
            logger.info(f"Parent process: {parent_name} (PID: {parent_process.pid})")
            
            # Check for VS Code
            if 'code' in parent_name or 'electron' in parent_name:
                self.caller_program = CallerProgram.VSCODE
                logger.info("✓ Detected caller: VS Code")
                return CallerProgram.VSCODE
            
            # Check for LM Studio
            if 'lm-studio' in parent_name or 'lmstudio' in parent_name:
                self.caller_program = CallerProgram.LM_STUDIO
                logger.info("✓ Detected caller: LM Studio")
                return CallerProgram.LM_STUDIO
            
            # Check for Ollama
            if 'ollama' in parent_name:
                self.caller_program = CallerProgram.OLLAMA
                logger.info("✓ Detected caller: Ollama")
                return CallerProgram.OLLAMA
            
            # Check for OpenWebUI
            if 'open' in parent_name and 'ui' in parent_name:
                self.caller_program = CallerProgram.OPENWEBUI
                logger.info("✓ Detected caller: OpenWebUI")
                return CallerProgram.OPENWEBUI
            
            # Check command line for Python module names
            try:
                cmdline = ' '.join(current_process.cmdline()).lower()
                
                if 'lm-studio' in cmdline or 'lmstudio' in cmdline:
                    self.caller_program = CallerProgram.LM_STUDIO
                    logger.info("✓ Detected caller (from cmdline): LM Studio")
                    return CallerProgram.LM_STUDIO
                
                if 'ollama' in cmdline:
                    self.caller_program = CallerProgram.OLLAMA
                    logger.info("✓ Detected caller (from cmdline): Ollama")
                    return CallerProgram.OLLAMA
                
                if 'openwebui' in cmdline or 'open_webui' in cmdline:
                    self.caller_program = CallerProgram.OPENWEBUI
                    logger.info("✓ Detected caller (from cmdline): OpenWebUI")
                    return CallerProgram.OPENWEBUI
                    
            except (IndexError, psutil.AccessDenied):
                pass
            
            logger.info("⚠ Could not definitively detect caller program")
            self.caller_program = CallerProgram.UNKNOWN
            return CallerProgram.UNKNOWN
            
        except Exception as e:
            logger.warning(f"Error detecting caller program: {e}")
            return CallerProgram.UNKNOWN
    
    def is_port_available(self, port: int) -> bool:
        """
        Check if a port is available for binding.
        
        Args:
            port: Port number to check
        
        Returns:
            True if port is available, False otherwise
        """
        try:
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            # Result 0 = connected (port in use), non-zero = connection refused (port available)
            return result != 0
            
        except Exception as e:
            logger.warning(f"Error checking port {port}: {e}")
            return False
    
    def find_available_port(self) -> int:
        """
        Find an available port starting with primary, then trying backups.
        
        Returns:
            First available port number
            
        Raises:
            RuntimeError if no ports are available
        """
        ports_to_try = [self.PRIMARY_PORT] + self.BACKUP_PORTS
        
        for port in ports_to_try:
            if self.is_port_available(port):
                logger.info(f"✓ Port {port} is available")
                self.active_port = port
                return port
            else:
                logger.debug(f"  Port {port} is in use")
        
        raise RuntimeError(
            f"❌ No available ports found. Tried: {ports_to_try}. "
            "Please close other instances of the MCP server."
        )
    
    def save_port_info(self) -> bool:
        """
        Save active port info to a file for client discovery.
        
        Creates a JSON file with:
        - active_port: The port the server is listening on
        - caller_program: Program that called this server
        - process_id: PID of this server process
        - timestamp: When the server started
        
        Returns:
            True if saved successfully, False otherwise
        """
        if self.active_port is None:
            logger.error("Cannot save port info: active_port not set")
            return False
        
        try:
            port_info = {
                "active_port": self.active_port,
                "primary_port": self.PRIMARY_PORT,
                "caller_program": self.caller_program.value,
                "process_id": self.process_id,
                "timestamp": datetime.now().isoformat(),
                "http_url": f"http://127.0.0.1:{self.active_port}",
                "status": "active"
            }
            
            info_file = self.memory_data_path / self.PORT_INFO_FILENAME
            
            with open(info_file, 'w') as f:
                json.dump(port_info, f, indent=2)
            
            logger.info(f"✓ Saved port info to {info_file}")
            logger.info(f"  Active port: {self.active_port}")
            logger.info(f"  Caller: {self.caller_program.value}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save port info: {e}")
            return False
    
    @staticmethod
    def get_active_port(memory_data_path: str) -> Optional[int]:
        """
        Read the active port from the port info file.
        
        Used by clients to discover which port the server is listening on.
        
        Args:
            memory_data_path: Path to Friday's memory_data directory
        
        Returns:
            Active port number, or None if file doesn't exist/invalid
        """
        try:
            info_file = Path(memory_data_path) / PortManager.PORT_INFO_FILENAME
            
            if not info_file.exists():
                return None
            
            with open(info_file, 'r') as f:
                port_info = json.load(f)
            
            return port_info.get("active_port")
            
        except Exception as e:
            logger.debug(f"Could not read port info: {e}")
            return None
    
    def cleanup_port_info(self) -> bool:
        """
        Clean up port info file when server shuts down.
        
        Returns:
            True if cleaned up successfully
        """
        try:
            info_file = self.memory_data_path / self.PORT_INFO_FILENAME
            
            if info_file.exists():
                info_file.unlink()
                logger.info("✓ Cleaned up port info file")
            
            return True
            
        except Exception as e:
            logger.warning(f"Error cleaning up port info: {e}")
            return False
    
    async def get_process_info(self) -> Dict:
        """
        Get detailed info about the running process and caller.
        
        Returns:
            Dict with process and caller information
        """
        try:
            process = psutil.Process(self.process_id)
            
            return {
                "process_id": self.process_id,
                "caller_program": self.caller_program.value,
                "active_port": self.active_port,
                "process_name": process.name(),
                "cmdline": ' '.join(process.cmdline()),
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting process info: {e}")
            return {
                "error": str(e),
                "process_id": self.process_id,
                "caller_program": self.caller_program.value
            }
