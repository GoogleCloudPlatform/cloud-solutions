---
name: idea-to-app
description: >-
  Converts raw application ideas into a product manager and software architect
  technical specification and scaffolds the prototype application. Use when
  designing and building a new application prototype from a user prompt. Don't
  use for modifying existing applications or single-file bug fixes.
---

# Convert idea to application

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

<!--
    Disabling markdownlint MD030 to allow the list overflowing to numbers
    >=10.
-->
<!-- markdownlint-disable MD030 -->

## Prerequisites

- **Host validation only:** Limit prerequisite checks strictly to host-level
  validation: verify Python 3.11 or higher (`python3 --version`), confirm the
  `venv` module is available (`python3 -m venv --help`), and verify `uv`
  (`uv --version`) or `pip-compile` (`pip-compile --version`) is installed.
- **Development standards:** Workspace rules defined in
  `.agents/rules/dev-rules.md`.
- **Separation of concerns:** Do not create the virtual environment or install
  packages during the specification and planning phases (Steps 1 and 2).
  Creating the virtual environment and installing dependencies occurs strictly
  in Step 3 (Scaffolding).
- **Failure handling:** If `python3`, the `venv` module, or both `uv` and
  `pip-compile` are unavailable on the host, halt execution before scaffolding
  and instruct the user how to install the missing packages for their operating
  system.

## Role

Adopt a dual-persona perspective throughout the specification and build process:

1.  **Product Manager:** Focus on user needs, value proposition, and scope
    control.
2.  **Software Architect:** Focus on system design, data integrity, and
    technical feasibility.

## Workflow

### 1. Generate prototype specification

Refactor the user's idea into a structured **Prototype Specification** covering
both perspectives:

1.  **Product strategy:**
    - **High-level summary:** Define the project's purpose and the primary pain
      point it addresses.
    - **Target audience:** Describe the target user persona.
    - **Core features:** List the essential minimum viable product (MVP)
      features required for a functional prototype.
    - **Out of scope:** Explicitly list excluded features to prevent scope creep
      during the build.
2.  **Technical blueprint:**
    - **Technical stack:** Recommend the default baseline stack unless the user
      prompt requires a different paradigm:
        - **Backend:** Python with Flask
        - **Frontend:** Clean UI with HTML and Bootstrap
        - **Database:** SQLite or in-memory store
    - **UI and UX design standards:**
        - **Component and layout structure:** Scaffold clean container cards, a
          responsive grid layout, and a clear typographic hierarchy.
        - **State handling and feedback:** Include informative empty-state
          placeholders with an action button when lists or tables have no
          records, visual alert or flash banners confirming user actions
          (success and error banners), and clear visual validation cues for
          required or invalid form inputs.
        - **Accessibility basics:** Use semantic HTML elements (`<nav>`,
          `<main>`, `<button>`) and accessible form labels.
    - **Data model:** Define the main entities, attributes, and relationships,
      such as `User -> Has Many -> Items`.
    - **User flow:** Provide a step-by-step logic path for the primary user
      goal.
3.  **Review gate:** Present the specification with a brief **Review** section
    asking the user whether to adjust the scope or technical stack before
    proceeding. Wait for user confirmation.

### 2. Present implementation plan

Once the user approves the specification:

1.  Outline the target folder structure, files to create, dependencies, database
    schema, and routes or views.
2.  Present the implementation plan and wait for the user to approve the plan
    before writing application code.

### 3. Scaffold environment and implement application

1.  **Create project directory:** Create a dedicated folder for the generated
    application source code.
2.  **Configure virtual environment and dependencies:** Follow the environment
    and dependency rules in `.agents/rules/dev-rules.md`:
    - Create the local virtual environment: `python3 -m venv venv`.
    - Define direct dependencies with major-version bounds in `requirements.in`.
    - Compile into a pinned `requirements.txt` with hashes using `pip-compile`
      or `uv pip compile` with `--generate-hashes` and
      `--output-file=requirements.txt requirements.in`.
    - Install dependencies using the virtual environment's executable:
      `./venv/bin/pip install --require-hashes -r requirements.txt`.
3.  **Implement source code:** Generate the backend, frontend templates, and
    data layer following `.agents/rules/dev-rules.md`, including PEP 8
    conventions, structured logging standards, environment variable resolution
    for secrets, and module, class, and function docstrings.

### 4. Verify and preview application

1.  **Start local server:** Run the application using the project virtual
    environment (`./venv/bin/python app.py`).
2.  **Verify endpoints:** Check startup logs and test the primary routes to
    confirm the server responds without runtime errors. If errors occur, resolve
    them and restart the server.
3.  **Open preview:** Open the running application in the browser for user
    inspection.
