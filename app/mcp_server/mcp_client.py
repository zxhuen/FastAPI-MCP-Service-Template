import sys
from pathlib import Path

from fastapi import Depends
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pytest import Session

from app.ai.providers.gemini import client

from app.core.database import get_db

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

SYSTEM_PROMPT = (BASE_DIR / "app/mcp_server/prompts/inventory_assistant.md").read_text(
    encoding="utf-8"
)


ALLOWED_INVENTORY_TOOLS = [
    "add_product",
    "list_products",
    "edit_product",
    "delete_product",
    "lookup_product_by_name",
]


server_params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "app.mcp_server.server"],
    cwd=str(BASE_DIR),
)


MAX_TOOL_ROUNDS = 5


# --------------------------------------------------
# Gemini configuration
# --------------------------------------------------


def build_tool_config() -> types.ToolConfig:
    return types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.AUTO,
        )
    )


def convert_mcp_tools_to_gemini(mcp_tools) -> list[types.Tool]:
    declarations = []

    for tool in mcp_tools:
        if tool.name not in ALLOWED_INVENTORY_TOOLS:
            continue

        declarations.append(
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters_json_schema=tool.inputSchema,
            )
        )

    return [types.Tool(function_declarations=declarations)]


# --------------------------------------------------
# MCP result handling
# --------------------------------------------------


def mcp_result_to_text(result) -> str:
    text_parts = []

    for content in result.content:
        text = getattr(content, "text", None)

        if text:
            text_parts.append(text)

    return "\n".join(text_parts)


# --------------------------------------------------
# Gemini response handling
# --------------------------------------------------


def get_function_calls(response):
    return response.function_calls or []


# --------------------------------------------------
# Tool execution
# --------------------------------------------------


async def execute_tool(
    session: ClientSession,
    tool_name: str,
    tool_args: dict,
) -> dict:

    if tool_name not in ALLOWED_INVENTORY_TOOLS:
        return {"error": f"Tool '{tool_name}' is not allowed."}

    try:
        result = await session.call_tool(
            tool_name,
            arguments=tool_args,
        )

        result_text = mcp_result_to_text(result)

        print(f"[MCP] Tool: {tool_name}", file=sys.stderr)
        print(f"[MCP] Args: {tool_args}", file=sys.stderr)
        print(f"[MCP] Result: {result_text}", file=sys.stderr)

        return {"result": result_text}

    except Exception as exc:
        print(
            f"[MCP] Tool '{tool_name}' failed: {exc}",
            file=sys.stderr,
        )

        return {"error": str(exc)}


# --------------------------------------------------
# Send tool result back to Gemini
# --------------------------------------------------


def append_tool_result(
    contents: list,
    tool_name: str,
    tool_result: dict,
) -> None:

    contents.append(
        types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=tool_name,
                    response=tool_result,
                )
            ],
        )
    )


# --------------------------------------------------
# Main chat function
# --------------------------------------------------


async def chat(prompt: str, db: Session = Depends(get_db)) -> str:

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Initialize MCP
            await session.initialize()

            # Get MCP tools
            mcp_response = await session.list_tools()

            # Convert MCP tools → Gemini tools
            gemini_tools = convert_mcp_tools_to_gemini(mcp_response.tools)

            print(
                "[MCP] Available tools:",
                [tool.name for tool in mcp_response.tools],
            )

            # Initial user message
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                )
            ]

            # Gemini ↔ MCP loop
            for round_number in range(1, MAX_TOOL_ROUNDS + 1):

                print(f"[Gemini] Tool round {round_number}")

                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        tools=gemini_tools,
                        system_instruction=SYSTEM_PROMPT,
                        tool_config=build_tool_config(),
                    ),
                )

                function_calls = get_function_calls(response)

                # ------------------------------------------
                # Gemini produced final text
                # ------------------------------------------

                if not function_calls:

                    text = response.text

                    if text:
                        return text

                    return "Gemini returned an empty response."

                # ------------------------------------------
                # Gemini requested tools
                # ------------------------------------------

                if not response.candidates:
                    return "Gemini returned no candidates."

                assistant_content = response.candidates[0].content

                contents.append(assistant_content)

                # ------------------------------------------
                # Execute tools
                # ------------------------------------------

                for function_call in function_calls:

                    tool_name = function_call.name

                    tool_args = function_call.args or {}

                    tool_result = await execute_tool(
                        session=session,
                        tool_name=tool_name,
                        tool_args=tool_args,
                    )

                    append_tool_result(
                        contents=contents,
                        tool_name=tool_name,
                        tool_result=tool_result,
                    )

            return (
                "I couldn't complete the requested "
                f"operation within {MAX_TOOL_ROUNDS} "
                "tool rounds."
            )
