# Gemini CLI ADK Agent Prototype

This repository serves as a prototype for building ADK (Agent Development Kit)
agents using the Gemini CLI. It demonstrates how to leverage existing context
files and custom commands to streamline the agent development process.

## Key Files

- **`GEMINI.md`**: Provides instructions on how to use the reference
  documentation to build ADK agents.
- **`AGENTS.txt`**: Contains detailed information and best practices for agent
  development.

## Custom Commands

The custom commands for this project are defined in the `.gemini/commands`
directory. These TOML files configure the prompts and behavior of the agent for
specific tasks.

### `/plan:new`

**Description:** Generates a plan for a feature based on a description. The
prompt for this command is defined in `.gemini/commands/plan/new.toml`.

### `/plan:impl`

**Description:** Implements a plan for a feature based on a description. The
prompt for this command is defined in `.gemini/commands/plan/impl.toml`.
