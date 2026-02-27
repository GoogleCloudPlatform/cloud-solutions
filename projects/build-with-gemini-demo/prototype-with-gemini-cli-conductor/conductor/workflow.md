# Project Workflow

## Guiding Principles

1.  **The Plan is the Source of Truth:** All work must be tracked in `plan.md`.
1.  **The Tech Stack is Deliberate:** Changes to the tech stack must be
    documented in `tech-stack.md` before implementation.
1.  **User Experience First:** Every decision should prioritize user experience.
1.  **Rapid Prototyping:** Focus on quickly building functional prototypes to
    validate ideas. Speed over perfection.

## Project Organization

- **Source Code Folder:** When building the application, create a dedicated
  folder for the source code (e.g., `conference-app/`) to separate application
  logic from configuration and metadata, keeping the root directory clean.

## Task Workflow

All tasks follow a rapid prototyping lifecycle.

1.  **Select Task:** Choose the next available task from `plan.md`.
1.  **Mark as In Progress:** Update the task's status from `[ ]` to `[~]` in
    `plan.md`.
1.  **Implement:** Write the code to complete the task. Focus on getting it
    working.
1.  **Commit:** Commit your changes with a message that references the task.
1.  **Mark as Done:** Update the task's status from `[~]` to `[x]` in `plan.md`
    and commit the change (e.g., `conductor(plan): Complete task '...'`).

## Manual Verification

After implementing a feature or a set of tasks, always perform a manual check to
ensure it works as expected.

- **Start the server:** `flask run`
- **Open the app:** Open your browser to the local development URL.
- **Verify:** Click through the new feature and check for obvious bugs or UI
  issues.

## Development Commands

### Setup

```bash
# Install dependencies
pip install -r requirements.txt
```

### Daily Development

```bash
# Run the development server
flask run
```

### Before Committing

```bash
# Optional: Format the code
python -m black .
```

## Commit Guidelines

Use conventional commit messages to keep the history clean.

### Message Format

```text
<type>(<scope>): <description>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `chore`: Maintenance tasks

### Examples

```bash
git commit -m "feat(ui): Add user login form"
git commit -m "fix(api): Correct user data serialization"
```

## Definition of Done

A task is considered "done" when:

1.  The code has been implemented.
1.  The feature works as demonstrated in a manual verification.
1.  The changes are committed.
1.  The `plan.md` is updated.
