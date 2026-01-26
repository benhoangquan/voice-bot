"""LLM adapter implementations"""

from typing import AsyncIterator, Dict, Any, Optional, List
import asyncio
from anthropic import Anthropic
from anthropic.types import MessageStreamEvent

from .base import LLMAdapter


class AnthropicAdapter(LLMAdapter):
    """Anthropic Claude 3.5 Sonnet adapter"""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
    
    async def chat(self, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> Dict[str, Any]:
        """Chat with Claude and return response"""
        # Convert messages format
        system_message = None
        conversation_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content")
            else:
                # Handle Anthropic message format (can be string or list of content blocks)
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Already in Anthropic format
                    conversation_messages.append({
                        "role": msg.get("role", "user"),
                        "content": content
                    })
                else:
                    # Simple string format
                    conversation_messages.append({
                        "role": msg.get("role", "user"),
                        "content": content
                    })
        
        # Prepare tool definitions if provided
        tool_definitions = None
        if tools:
            tool_definitions = [self._convert_tool(tool) for tool in tools]
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_message,
            messages=conversation_messages,
            tools=tool_definitions if tool_definitions else None,
        )
        
        # Extract content and tool calls
        content = ""
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        
        return {
            "content": content,
            "tool_calls": tool_calls if tool_calls else None,
        }
    
    async def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> AsyncIterator[str]:
        """Chat with Claude and stream response"""
        # Convert messages format (same as chat method)
        system_message = None
        conversation_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content")
            else:
                # Handle Anthropic message format (can be string or list of content blocks)
                content = msg.get("content", "")
                if isinstance(content, list):
                    conversation_messages.append({
                        "role": msg.get("role", "user"),
                        "content": content
                    })
                else:
                    conversation_messages.append({
                        "role": msg.get("role", "user"),
                        "content": content
                    })
        
        # Prepare tool definitions if provided
        tool_definitions = None
        if tools:
            tool_definitions = [self._convert_tool(tool) for tool in tools]
        
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=system_message,
            messages=conversation_messages,
            tools=tool_definitions if tool_definitions else None,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield event.delta.text
                await asyncio.sleep(0.01)
    
    def _convert_tool(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tool definition to Anthropic format"""
        return {
            "name": tool.get("name"),
            "description": tool.get("description"),
            "input_schema": tool.get("parameters", {}),
        }
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool function (handled by caller)"""
        # Tool execution is handled by the caller
        return None


class OllamaAdapter(LLMAdapter):
    """Ollama adapter for open-source models (future implementation)"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1:7b"):
        self.base_url = base_url
        self.model = model
        # TODO: Initialize Ollama client
    
    async def chat(self, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> Dict[str, Any]:
        """Chat with Ollama model"""
        # TODO: Implement Ollama chat
        return {"content": "", "tool_calls": None}
    
    async def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List] = None) -> AsyncIterator[str]:
        """Chat with Ollama and stream response"""
        # TODO: Implement Ollama streaming
        yield ""
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool function"""
        # TODO: Implement tool calling
        return None
