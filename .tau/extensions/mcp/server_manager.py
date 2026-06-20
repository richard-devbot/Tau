"""
MCP Server Manager

Manages connections to MCP servers, handles tool/resource/prompt discovery,
and bridges between Tau and MCP servers.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from .types import MCPServerConfig, MCPServerInfo

logger = logging.getLogger(__name__)


class MCPServerManager:
    """Manages MCP server connections and tool/resource discovery."""

    def __init__(self, tau):
        """Initialize the MCP server manager.
        
        Args:
            tau: The Tau extension API instance.
        """
        self.tau = tau
        self.servers: dict[str, MCPServerInfo] = {}
        self.config_path = Path.home() / ".tau" / "mcp_servers.json"
        self._load_server_configs()

    def _load_server_configs(self) -> None:
        """Load MCP server configurations from disk."""
        if not self.config_path.exists():
            return
        
        try:
            with open(self.config_path) as f:
                data = json.load(f)
            
            for server_name, config in data.get("servers", {}).items():
                cfg = MCPServerConfig(
                    name=server_name,
                    path=config.get("path", ""),
                    args=config.get("args", []),
                    env=config.get("env", {}),
                    enabled=config.get("enabled", True),
                )
                self.servers[server_name] = MCPServerInfo(config=cfg)
                logger.info(f"Loaded MCP server config: {server_name}")
        except Exception as e:
            logger.error(f"Failed to load MCP server configs: {e}")

    def _save_server_configs(self) -> None:
        """Save MCP server configurations to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "servers": {
                name: {
                    "path": info.config.path,
                    "args": info.config.args,
                    "env": info.config.env,
                    "enabled": info.config.enabled,
                }
                for name, info in self.servers.items()
            }
        }
        
        try:
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save MCP server configs: {e}")

    async def connect_server(self, server_name: str, path: str, args: list[str] | None = None) -> bool:
        """Connect to an MCP server.
        
        Args:
            server_name: Name/identifier for this server.
            path: Path or command to execute the MCP server.
            args: Optional arguments to pass to the server.
        
        Returns:
            True if connection was successful, False otherwise.
        """
        args = args or []
        
        config = MCPServerConfig(
            name=server_name,
            path=path,
            args=args,
        )
        
        server_info = MCPServerInfo(config=config)
        
        try:
            # Try to connect and discover capabilities
            connected = await self._connect_and_discover(server_info)
            
            if connected:
                self.servers[server_name] = server_info
                self._save_server_configs()
                logger.info(f"Successfully connected to MCP server: {server_name}")
                return True
            else:
                logger.warning(f"Failed to connect to MCP server: {server_name}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to MCP server {server_name}: {e}")
            return False

    async def _connect_and_discover(self, server_info: MCPServerInfo) -> bool:
        """Connect to server and discover its capabilities.
        
        Args:
            server_info: Server info object to populate.
        
        Returns:
            True if successfully connected and discovered, False otherwise.
        """
        try:
            # Import mcp dynamically
            from mcp import ClientSession, StdioClientTransport
            
            # Create transport
            transport = StdioClientTransport(
                command=server_info.config.path,
                args=server_info.config.args,
                env=server_info.config.env or None,
            )
            
            async with ClientSession(transport) as session:
                # Initialize and get capabilities
                await session.initialize()
                
                # Discover tools
                tools_response = await session.list_tools()
                server_info.tools = {
                    tool.name: {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in tools_response.tools
                }
                
                # Discover resources
                try:
                    resources_response = await session.list_resources()
                    server_info.resources = {
                        resource.uri: {
                            "uri": resource.uri,
                            "name": resource.name,
                            "mimeType": resource.mimeType,
                            "description": resource.description,
                        }
                        for resource in resources_response.resources
                    }
                except Exception:
                    logger.debug("Server does not support resources")
                
                # Discover prompts
                try:
                    prompts_response = await session.list_prompts()
                    server_info.prompts = {
                        prompt.name: {
                            "name": prompt.name,
                            "description": prompt.description,
                            "arguments": prompt.arguments or [],
                        }
                        for prompt in prompts_response.prompts
                    }
                except Exception:
                    logger.debug("Server does not support prompts")
                
                # Check for sampling and other client capabilities
                # These would be checked in the server's capabilities response
                server_info.supports_sampling = False
                server_info.supports_roots = False
                server_info.supports_elicitation = False
                
                server_info.connected = True
                return True
                
        except ImportError:
            logger.error("MCP library not installed. Install with: pip install mcp")
            return False
        except Exception as e:
            logger.error(f"Failed to connect and discover: {e}")
            return False

    async def disconnect_server(self, server_name: str) -> bool:
        """Disconnect from an MCP server.
        
        Args:
            server_name: Name of the server to disconnect from.
        
        Returns:
            True if successfully disconnected.
        """
        if server_name in self.servers:
            server_info = self.servers[server_name]
            server_info.connected = False
            logger.info(f"Disconnected from MCP server: {server_name}")
            return True
        return False

    def get_server(self, server_name: str) -> MCPServerInfo | None:
        """Get information about a server.
        
        Args:
            server_name: Name of the server.
        
        Returns:
            MCPServerInfo if found, None otherwise.
        """
        return self.servers.get(server_name)

    def list_servers(self) -> list[MCPServerInfo]:
        """List all configured servers.
        
        Returns:
            List of MCPServerInfo objects.
        """
        return list(self.servers.values())

    def list_all_tools(self) -> dict[str, dict[str, Any]]:
        """List all tools from all connected servers.
        
        Returns:
            Dict mapping 'server_name/tool_name' to tool metadata.
        """
        all_tools = {}
        for server_name, server_info in self.servers.items():
            if server_info.connected:
                for tool_name, tool_meta in server_info.tools.items():
                    key = f"{server_name}/{tool_name}"
                    all_tools[key] = tool_meta
        return all_tools

    def list_all_resources(self) -> dict[str, dict[str, Any]]:
        """List all resources from all connected servers.
        
        Returns:
            Dict mapping server names to their resources.
        """
        all_resources = {}
        for server_name, server_info in self.servers.items():
            if server_info.connected and server_info.resources:
                all_resources[server_name] = server_info.resources
        return all_resources

    def list_all_prompts(self) -> dict[str, dict[str, Any]]:
        """List all prompts from all connected servers.
        
        Returns:
            Dict mapping server names to their prompts.
        """
        all_prompts = {}
        for server_name, server_info in self.servers.items():
            if server_info.connected and server_info.prompts:
                all_prompts[server_name] = server_info.prompts
        return all_prompts

    async def call_tool(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool on an MCP server.
        
        Args:
            server_name: Name of the server.
            tool_name: Name of the tool to call.
            arguments: Tool arguments.
        
        Returns:
            Tool result as a dict.
        """
        try:
            from mcp import ClientSession, StdioClientTransport
            
            server_info = self.get_server(server_name)
            if not server_info:
                return {"error": f"Server not found: {server_name}"}
            
            transport = StdioClientTransport(
                command=server_info.config.path,
                args=server_info.config.args,
                env=server_info.config.env or None,
            )
            
            async with ClientSession(transport) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                
                # Convert result to dict
                return {
                    "success": True,
                    "content": result.content,
                    "isError": result.isError if hasattr(result, 'isError') else False,
                }
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {server_name}: {e}")
            return {"error": str(e)}

    async def get_resource(
        self, 
        server_name: str, 
        resource_uri: str
    ) -> dict[str, Any]:
        """Read a resource from an MCP server.
        
        Args:
            server_name: Name of the server.
            resource_uri: URI of the resource to read.
        
        Returns:
            Resource content as a dict.
        """
        try:
            from mcp import ClientSession, StdioClientTransport
            
            server_info = self.get_server(server_name)
            if not server_info:
                return {"error": f"Server not found: {server_name}"}
            
            transport = StdioClientTransport(
                command=server_info.config.path,
                args=server_info.config.args,
                env=server_info.config.env or None,
            )
            
            async with ClientSession(transport) as session:
                await session.initialize()
                result = await session.read_resource(resource_uri)
                
                return {
                    "success": True,
                    "uri": resource_uri,
                    "contents": [
                        {
                            "uri": c.uri,
                            "mimeType": c.mimeType,
                            "text": c.text,
                        }
                        for c in result.contents
                    ],
                }
        except Exception as e:
            logger.error(f"Failed to read resource {resource_uri} from {server_name}: {e}")
            return {"error": str(e)}

    async def get_prompt(
        self, 
        server_name: str, 
        prompt_name: str,
        arguments: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Get a prompt template from an MCP server.
        
        Args:
            server_name: Name of the server.
            prompt_name: Name of the prompt.
            arguments: Optional arguments for the prompt template.
        
        Returns:
            Prompt content as a dict.
        """
        try:
            from mcp import ClientSession, StdioClientTransport
            
            server_info = self.get_server(server_name)
            if not server_info:
                return {"error": f"Server not found: {server_name}"}
            
            transport = StdioClientTransport(
                command=server_info.config.path,
                args=server_info.config.args,
                env=server_info.config.env or None,
            )
            
            async with ClientSession(transport) as session:
                await session.initialize()
                result = await session.get_prompt(prompt_name, arguments or {})
                
                return {
                    "success": True,
                    "name": prompt_name,
                    "description": result.description if hasattr(result, 'description') else None,
                    "messages": [
                        {
                            "role": m.role,
                            "content": m.content,
                        }
                        for m in result.messages
                    ],
                }
        except Exception as e:
            logger.error(f"Failed to get prompt {prompt_name} from {server_name}: {e}")
            return {"error": str(e)}
