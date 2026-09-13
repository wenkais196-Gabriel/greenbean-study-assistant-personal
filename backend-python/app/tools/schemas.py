"""
三个检索工具在 OpenAI function calling 口径下的 JSON Schema。

工具本身（`app/tools/*.py`）保持 provider 无关；这些 schema 是"给 OpenAI 兼容端点的
工具描述"，属于接线层 —— 将来接别的协议（如 MCP）时再写它自己的工具描述。

参数口径与工具签名一一对应：`required` 只放 `run()` 的必填参数。
"""
CHUNK_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "chunk_search_tool",
        "description": "Searches for relevant text chunks in a workspace based on a query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query, in any language."},
                "workspace_id": {
                    "type": "string",
                    "description": "Only search chunks in this workspace; empty means no filter.",
                },
                "top_k": {"type": "integer", "description": "Maximum number of chunks to return."},
            },
            "required": ["query"],
        },
    },
}

DOCUMENT_RETRIEVAL_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "document_retrieval_tool",
        "description": "Retrieves document metadata by document ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "The document ID."},
            },
            "required": ["document_id"],
        },
    },
}

SECTION_CONTEXT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "section_context_tool",
        "description": "Retrieves section hierarchy and context metadata by section ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "section_id": {"type": "string", "description": "The section ID."},
            },
            "required": ["section_id"],
        },
    },
}

RETRIEVAL_TOOL_SCHEMAS = [
    CHUNK_SEARCH_TOOL_SCHEMA,
    DOCUMENT_RETRIEVAL_TOOL_SCHEMA,
    SECTION_CONTEXT_TOOL_SCHEMA,
]
