"""
MCP Commands

Register slash commands for MCP server management and interaction.
"""

import logging
from .tools import MCPTool, MCPResourceTool

logger = logging.getLogger(__name__)


def register_mcp_commands(tau, server_manager) -> None:
    """Register MCP commands with Tau.
    
    Args:
        tau: Tau extension API.
        server_manager: MCPServerManager instance.
    """
    
    async def cmd_mcp(ctx, args):
        """Main MCP command with subcommands."""
        if not args:
            await _show_mcp_help(ctx)
            return
        
        subcommand = args[0]
        sub_args = args[1:]
        
        if subcommand == "connect":
            await _cmd_connect(ctx, server_manager, sub_args)
        elif subcommand == "list":
            await _cmd_list(ctx, server_manager)
        elif subcommand == "resources":
            await _cmd_resources(ctx, server_manager)
        elif subcommand == "prompts":
            await _cmd_prompts(ctx, server_manager)
        elif subcommand == "disconnect":
            await _cmd_disconnect(ctx, server_manager, sub_args)
        elif subcommand == "config":
            await _cmd_config(ctx, server_manager)
        elif subcommand == "tools":
            await _cmd_tools(ctx, server_manager)
        elif subcommand == "call-tool":
            await _cmd_call_tool(ctx, server_manager, sub_args)
        elif subcommand == "read-resource":
            await _cmd_read_resource(ctx, server_manager, sub_args)
        elif subcommand == "get-prompt":
            await _cmd_get_prompt(ctx, server_manager, sub_args)
        else:
            ctx.ui.notify(f"Unknown MCP command: {subcommand}", "error")
            await _show_mcp_help(ctx)
    
    tau.register_command(
        "mcp",
        "Manage MCP servers and tools",
        cmd_mcp,
        aliases=["mcp-server"],
    )


async def _show_mcp_help(ctx) -> None:
    """Show help for MCP commands."""
    help_text = """MCP Commands:
    
/mcp connect <name> <path> [args...]  - Connect to an MCP server
/mcp list                              - List connected servers
/mcp tools                             - List all available tools
/mcp resources                         - List all available resources
/mcp prompts                           - List all available prompts
/mcp disconnect [name]                - Disconnect from a server
/mcp config                            - Show MCP configuration
/mcp call-tool <server> <tool> <args> - Call a specific tool
/mcp read-resource <server> <uri>     - Read a resource
/mcp get-prompt <server> <name> <args> - Get a prompt template
"""
    if ctx.ui:
        ctx.ui.notify(help_text)
    else:
        print(help_text)


async def _cmd_connect(ctx, server_manager, args: list[str]) -> None:
    """Connect to an MCP server."""
    if len(args) < 2:
        ctx.ui.notify("Usage: /mcp connect <name> <path> [args...]", "error")
        return
    
    server_name = args[0]
    path = args[1]
    extra_args = args[2:]
    
    if ctx.ui:
        ctx.ui.set_working_message(f"Connecting to {server_name}...")
    
    try:
        success = await server_manager.connect_server(server_name, path, extra_args)
        
        if success:
            server = server_manager.get_server(server_name)
            if ctx.ui:
                msg = f"Connected to {server_name}\n"
                if server.tools:
                    msg += f"  Tools: {len(server.tools)}\n"
                if server.resources:
                    msg += f"  Resources: {len(server.resources)}\n"
                if server.prompts:
                    msg += f"  Prompts: {len(server.prompts)}\n"
                ctx.ui.notify(msg)
            
            # Register tools from the server
            await _register_server_tools(tau=None, server_manager=server_manager, server_name=server_name)
        else:
            if ctx.ui:
                ctx.ui.notify(f"Failed to connect to {server_name}", "error")
    except Exception as e:
        if ctx.ui:
            ctx.ui.notify(f"Error connecting: {e}", "error")


async def _cmd_list(ctx, server_manager) -> None:
    """List connected servers."""
    servers = server_manager.list_servers()
    
    if not servers:
        if ctx.ui:
            ctx.ui.notify("No MCP servers configured.")
        return
    
    output = "Connected MCP Servers:\n"
    for server in servers:
        status = "✓" if server.connected else "✗"
        output += f"\n  {status} {server.config.name}\n"
        output += f"     Path: {server.config.path}\n"
        if server.tools:
            output += f"     Tools: {len(server.tools)}\n"
        if server.resources:
            output += f"     Resources: {len(server.resources)}\n"
        if server.prompts:
            output += f"     Prompts: {len(server.prompts)}\n"
    
    if ctx.ui:
        ctx.ui.notify(output)
    else:
        print(output)


async def _cmd_tools(ctx, server_manager) -> None:
    """List all available tools from all servers."""
    all_tools = server_manager.list_all_tools()
    
    if not all_tools:
        if ctx.ui:
            ctx.ui.notify("No MCP tools available.")
        return
    
    output = "Available MCP Tools:\n"
    for tool_name, tool_meta in all_tools.items():
        description = tool_meta.get("description", "")
        output += f"\n  • {tool_name}\n"
        if description:
            output += f"    {description}\n"
    
    if ctx.ui:
        ctx.ui.notify(output)
    else:
        print(output)


async def _cmd_resources(ctx, server_manager) -> None:
    """List all available resources from all servers."""
    all_resources = server_manager.list_all_resources()
    
    if not all_resources:
        if ctx.ui:
            ctx.ui.notify("No MCP resources available.")
        return
    
    output = "Available MCP Resources:\n"
    for server_name, resources in all_resources.items():
        output += f"\n  [{server_name}]\n"
        for uri, resource_meta in resources.items():
            description = resource_meta.get("description", "")
            mime_type = resource_meta.get("mimeType", "")
            output += f"    • {uri}\n"
            if mime_type:
                output += f"      Type: {mime_type}\n"
            if description:
                output += f"      {description}\n"
    
    if ctx.ui:
        ctx.ui.notify(output)
    else:
        print(output)


async def _cmd_prompts(ctx, server_manager) -> None:
    """List all available prompts from all servers."""
    all_prompts = server_manager.list_all_prompts()
    
    if not all_prompts:
        if ctx.ui:
            ctx.ui.notify("No MCP prompts available.")
        return
    
    output = "Available MCP Prompts:\n"
    for server_name, prompts in all_prompts.items():
        output += f"\n  [{server_name}]\n"
        for prompt_name, prompt_meta in prompts.items():
            description = prompt_meta.get("description", "")
            arguments = prompt_meta.get("arguments", [])
            output += f"    • {prompt_name}\n"
            if description:
                output += f"      {description}\n"
            if arguments:
                args_str = ", ".join(arg.get("name", "?") for arg in arguments)
                output += f"      Args: {args_str}\n"
    
    if ctx.ui:
        ctx.ui.notify(output)
    else:
        print(output)


async def _cmd_disconnect(ctx, server_manager, args: list[str]) -> None:
    """Disconnect from a server."""
    if not args:
        ctx.ui.notify("Usage: /mcp disconnect <name>", "error")
        return
    
    server_name = args[0]
    success = await server_manager.disconnect_server(server_name)
    
    if success:
        if ctx.ui:
            ctx.ui.notify(f"Disconnected from {server_name}")
    else:
        if ctx.ui:
            ctx.ui.notify(f"Server not found: {server_name}", "error")


async def _cmd_config(ctx, server_manager) -> None:
    """Show MCP configuration."""
    config_path = server_manager.config_path
    
    output = f"MCP Configuration:\n"
    output += f"  Config file: {config_path}\n"
    output += f"  Configured servers: {len(server_manager.servers)}\n"
    
    for server_name, server in server_manager.servers.items():
        output += f"\n  [{server_name}]\n"
        output += f"    Path: {server.config.path}\n"
        output += f"    Connected: {'Yes' if server.connected else 'No'}\n"
    
    if ctx.ui:
        ctx.ui.notify(output)
    else:
        print(output)


async def _cmd_call_tool(ctx, server_manager, args: list[str]) -> None:
    """Call a specific tool."""
    if len(args) < 2:
        ctx.ui.notify("Usage: /mcp call-tool <server> <tool> [json_args]", "error")
        return
    
    server_name = args[0]
    tool_name = args[1]
    json_args = " ".join(args[2:])
    
    # Parse JSON arguments
    try:
        import json
        arguments = json.loads(json_args) if json_args else {}
    except json.JSONDecodeError:
        ctx.ui.notify(f"Invalid JSON arguments: {json_args}", "error")
        return
    
    if ctx.ui:
        ctx.ui.set_working_message(f"Calling {tool_name}...")
    
    try:
        result = await server_manager.call_tool(server_name, tool_name, arguments)
        
        if "error" in result:
            if ctx.ui:
                ctx.ui.notify(f"Tool error: {result['error']}", "error")
        else:
            if ctx.ui:
                ctx.ui.notify(f"Tool result:\n{result.get('content', '')}")
    except Exception as e:
        if ctx.ui:
            ctx.ui.notify(f"Error calling tool: {e}", "error")


async def _cmd_read_resource(ctx, server_manager, args: list[str]) -> None:
    """Read a resource."""
    if len(args) < 2:
        ctx.ui.notify("Usage: /mcp read-resource <server> <uri>", "error")
        return
    
    server_name = args[0]
    resource_uri = args[1]
    
    if ctx.ui:
        ctx.ui.set_working_message(f"Reading {resource_uri}...")
    
    try:
        result = await server_manager.get_resource(server_name, resource_uri)
        
        if "error" in result:
            if ctx.ui:
                ctx.ui.notify(f"Resource error: {result['error']}", "error")
        else:
            content = "\n".join(
                c.get("text", str(c)) for c in result.get("contents", [])
            )
            if ctx.ui:
                ctx.ui.notify(f"Resource content:\n{content}")
    except Exception as e:
        if ctx.ui:
            ctx.ui.notify(f"Error reading resource: {e}", "error")


async def _cmd_get_prompt(ctx, server_manager, args: list[str]) -> None:
    """Get a prompt template."""
    if len(args) < 2:
        ctx.ui.notify("Usage: /mcp get-prompt <server> <name> [json_args]", "error")
        return
    
    server_name = args[0]
    prompt_name = args[1]
    json_args = " ".join(args[2:])
    
    # Parse JSON arguments
    try:
        import json
        arguments = json.loads(json_args) if json_args else {}
    except json.JSONDecodeError:
        ctx.ui.notify(f"Invalid JSON arguments: {json_args}", "error")
        return
    
    if ctx.ui:
        ctx.ui.set_working_message(f"Getting prompt {prompt_name}...")
    
    try:
        result = await server_manager.get_prompt(server_name, prompt_name, arguments)
        
        if "error" in result:
            if ctx.ui:
                ctx.ui.notify(f"Prompt error: {result['error']}", "error")
        else:
            messages = result.get("messages", [])
            content = "\n".join(
                f"[{m.get('role')}]: {m.get('content', '')}"
                for m in messages
            )
            if ctx.ui:
                ctx.ui.notify(f"Prompt content:\n{content}")
    except Exception as e:
        if ctx.ui:
            ctx.ui.notify(f"Error getting prompt: {e}", "error")


async def _register_server_tools(tau, server_manager, server_name: str) -> None:
    """Dynamically register tools from a connected server.
    
    Args:
        tau: Tau extension API (may be None in command handlers).
        server_manager: MCPServerManager instance.
        server_name: Name of the server to register tools from.
    """
    server = server_manager.get_server(server_name)
    if not server or not server.connected:
        return
    
    # Register regular tools
    for tool_name, tool_meta in server.tools.items():
        tool = MCPTool(server_name, tool_name, tool_meta, server_manager)
        if tau:
            tau.register_tool(tool)
    
    # Register resource tools
    for resource_uri, resource_meta in server.resources.items():
        tool = MCPResourceTool(server_name, resource_uri, resource_meta, server_manager)
        if tau:
            tau.register_tool(tool)
