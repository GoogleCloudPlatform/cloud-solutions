# Prototype with Gemini CLI

This project demonstrates how to use the Gemini CLI to create a prototype
application based on user ideas and specifications. It leverages custom commands
to streamline the workflow from idea to code.

## Custom Commands

The custom commands for this project are defined in the `.gemini/commands`
directory. These TOML files configure the prompts and behavior of the agent for
specific tasks.

### `idea-to-spec`

**Description:** Transforms a user's idea into a detailed specification for a
prototype. The prompt for this command is defined in
`.gemini/commands/idea-to-spec.toml`.

### `spec-to-code`

**Description:** Generates a running application from a detailed specification.
The prompt for this command is defined in `.gemini/commands/spec-to-code.toml`.
