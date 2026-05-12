"""MCP prompt templates."""

from __future__ import annotations

from mcp.server import Server
from mcp.types import Prompt, PromptArgument, PromptMessage, TextContent


def register_prompts(server: Server) -> None:

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="medication_safety_analysis",
                description="Full interaction analysis for a list of medications",
                arguments=[
                    PromptArgument(
                        name="medications",
                        description="Comma-separated list of drug names",
                        required=True,
                    )
                ],
            ),
            Prompt(
                name="symptom_check",
                description="Attribute reported symptoms to current medications",
                arguments=[
                    PromptArgument(
                        name="medications",
                        description="Comma-separated list of current drug names",
                        required=True,
                    ),
                    PromptArgument(
                        name="symptoms",
                        description="Symptoms the user is experiencing",
                        required=True,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None) -> list[PromptMessage]:
        args = arguments or {}

        if name == "medication_safety_analysis":
            meds = args.get("medications", "")
            return [PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"Please analyse my medications for drug interactions and safety concerns.\n\n"
                        f"My medications: {meds}\n\n"
                        "Use the medsafe tools to:\n"
                        "1. Normalize the drug names\n"
                        "2. Check all pairwise interactions\n"
                        "3. Generate a safety briefing with questions I should ask my doctor"
                    ),
                ),
            )]

        if name == "symptom_check":
            meds = args.get("medications", "")
            symptoms = args.get("symptoms", "")
            return [PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        f"I'm taking the following medications: {meds}\n\n"
                        f"I've been experiencing: {symptoms}\n\n"
                        "Could any of these symptoms be related to my medications or their interactions? "
                        "Please use the medsafe tools to investigate."
                    ),
                ),
            )]

        return [PromptMessage(
            role="user",
            content=TextContent(type="text", text=f"Unknown prompt: {name}"),
        )]
