"""
MCP Tool Integration

Bridges MCP server tools with Tau's tool system by creating Tool instances
that wrap MCP tool calls.
"""

import json
import logging
from typing import Any, Type
from pydantic import BaseModel, Field, create_model
from tau.tool.types import Tool, ToolKind, ToolInvocation, ToolResult, ToolExecutionMode

logger = logging.getLogger(__name__)


def create_dynamic_schema(tool_meta: dict[str, Any]) -> Type[BaseModel]:
    """Create a Pydantic model from an MCP tool's input schema.
    
    Args:
        tool_meta: Tool metadata containing inputSchema.
    
    Returns:
        A Pydantic BaseModel class.
    """
    input_schema = tool_meta.get("inputSchema", {})
    
    # Extract properties and required fields
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    
    fields = {}
    for prop_name, prop_schema in properties.items():
        # Determine field type and default
        field_type = _schema_type_to_python(prop_schema.get("type", "string"))
        
        if prop_name in required:
            fields[prop_name] = (field_type, Field(..., description=prop_schema.get("description", "")))
        else:
            default = prop_schema.get("default", None)
            fields[prop_name] = (field_type, Field(default=default, description=prop_schema.get("description", "")))
    
    # Create model dynamically
    if not fields:
        # If no fields, create a minimal schema
        fields["_dummy"] = (str, Field(default="", description="Placeholder field"))
    
    return create_model(f"MCPToolSchema", **fields)  # type: ignore


def _schema_type_to_python(schema_type: str) -> Type:
    """Convert JSON schema type to Python type.
    
    Args:
        schema_type: JSON schema type string.
    
    Returns:
        Corresponding Python type.
    """
    type_map = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(schema_type, str)


class MCPTool(Tool):
    """Tau Tool wrapper for MCP server tools."""
    
    def __init__(
        self,
        server_name: str,
        tool_name: str,
        tool_meta: dict[str, Any],
        server_manager,
    ):
        """Initialize an MCP tool wrapper.
        
        Args:
            server_name: Name of the MCP server.
            tool_name: Name of the tool on the server.
            tool_meta: Tool metadata from server.
            server_manager: Reference to the MCPServerManager.
        """
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_meta = tool_meta
        self.server_manager = server_manager
        
        # Create schema from tool metadata
        schema = create_dynamic_schema(tool_meta)
        
        # Determine tool kind (default to Execute)
        kind = ToolKind.Execute
        if "read" in tool_name.lower():
            kind = ToolKind.Read
        elif "write" in tool_name.lower() or "create" in tool_name.lower():
            kind = ToolKind.Write
        elif "edit" in tool_name.lower() or "modify" in tool_name.lower():
            kind = ToolKind.Edit
        
        super().__init__(
            name=f"mcp_{server_name}_{tool_name}",
            description=f"[{server_name}] {tool_meta.get('description', 'MCP Tool')}",
            schema=schema,
            kind=kind,
            execution_mode=ToolExecutionMode.Sequential,
        )
    
    async def execute(
        self,
        invocation: ToolInvocation,
        tool_execution_update_callback=None,
        signal=None,
        context=None,
    ) -> ToolResult:
        """Execute the MCP tool.
        
        Args:
            invocation: Tool invocation with parameters.
            tool_execution_update_callback: Optional callback for streaming updates.
            signal: Optional abort signal.
            context: Optional tool context.
        
        Returns:
            ToolResult with the tool output.
        """
        try:
            # Extract parameters
            params = invocation.params
            
            # Call the MCP server's tool
            result = await self.server_manager.call_tool(
                self.server_name,
                self.tool_name,
                params,
            )
            
            if "error" in result:
                return ToolResult.error(invocation.id, result["error"])
            
            if result.get("success"):
                content = result.get("content", "")
                if isinstance(content, list):
                    # Format content array
                    content_str = "\n".join(
                        c.get("text", str(c))
                        for c in content
                        if isinstance(c, dict)
                    ) or str(content)
                else:
                    content_str = str(content)
                
                return ToolResult.ok(
                    invocation.id,
                    content_str,
                    metadata={
                        "server": self.server_name,
                        "tool": self.tool_name,
                    },
                )
            
            return ToolResult.error(invocation.id, "Tool execution failed")
            
        except Exception as e:
            logger.error(f"Error executing MCP tool {self.tool_name}: {e}")
            return ToolResult.error(invocation.id, str(e))


class MCPResourceTool(Tool):
    """Tau Tool wrapper for reading MCP resources."""
    
    def __init__(
        self,
        server_name: str,
        resource_uri: str,
        resource_meta: dict[str, Any],
        server_manager,
    ):
        """Initialize an MCP resource reader tool.
        
        Args:
            server_name: Name of the MCP server.
            resource_uri: URI of the resource.
            resource_meta: Resource metadata from server.
            server_manager: Reference to the MCPServerManager.
        """
        self.server_name = server_name
        self.resource_uri = resource_uri
        self.resource_meta = resource_meta
        self.server_manager = server_manager
        
        # Simple schema for resource reading
        class ResourceSchema(BaseModel):
            _resource: str = Field(default="", description="Internal resource URI")
        
        super().__init__(
            name=f"mcp_resource_{server_name}_{resource_uri.replace('://', '_').replace('/', '_')}",
            description=f"[{server_name}] Read resource: {resource_meta.get('description', resource_uri)}",
            schema=ResourceSchema,
            kind=ToolKind.Read,
            execution_mode=ToolExecutionMode.Parallel,
        )
    
    async def execute(
        self,
        invocation: ToolInvocation,
        tool_execution_update_callback=None,
        signal=None,
        context=None,
    ) -> ToolResult:
        """Execute the resource read.
        
        Args:
            invocation: Tool invocation.
            tool_execution_update_callback: Optional callback for streaming updates.
            signal: Optional abort signal.
            context: Optional tool context.
        
        Returns:
            ToolResult with the resource content.
        """
        try:
            result = await self.server_manager.get_resource(
                self.server_name,
                self.resource_uri,
            )
            
            if "error" in result:
                return ToolResult.error(invocation.id, result["error"])
            
            if result.get("success"):
                # Format resource contents
                contents = result.get("contents", [])
                content_str = "\n".join(
                    c.get("text", str(c))
                    for c in contents
                    if isinstance(c, dict) and "text" in c
                ) or str(contents)
                
                return ToolResult.ok(
                    invocation.id,
                    content_str,
                    metadata={
                        "server": self.server_name,
                        "resource": self.resource_uri,
                        "mime_type": self.resource_meta.get("mimeType"),
                    },
                )
            
            return ToolResult.error(invocation.id, "Resource read failed")
            
        except Exception as e:
            logger.error(f"Error reading MCP resource {self.resource_uri}: {e}")
            return ToolResult.error(invocation.id, str(e))
