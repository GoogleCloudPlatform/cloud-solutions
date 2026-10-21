# Interactive code reviews with Antigravity CLI

This guide provides a walkthrough for using the Antigravity CLI and a custom
`code-review` Agent Skill to perform a review of local code changes. This skill
offers a low-friction method for developers to receive immediate, AI-driven
feedback on their work-in-progress. Using progressive disclosure, the
Antigravity CLI loads and applies the skill on demand when prompted in natural
language, allowing developers to gain insights into their local changes,
identify potential issues, and receive concrete suggestions for improvement
without submitting a formal change request.

This workflow enhances the pre-submission review process, leading to
higher-quality code, faster iterations, and a more efficient development
workflow. Integrating a `code-review` skill into the Antigravity CLI streamlines
code development and review practices.

## Requirements

To follow this guide, you need:

- Antigravity CLI: Installed and configured. For installation instructions,
  visit [antigravity.google](https://antigravity.google/docs/cli/install/).
- Java Development Kit (JDK): Version 21 or higher.

## Clone Git repository and navigate to workspace

Open your local terminal or
[Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell) and
clone the demo repository:

```bash
git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
cd cloud-solutions
git sparse-checkout set --cone projects/build-with-gemini-demo/gemini-powered-development/menu-service
git checkout
cd projects/build-with-gemini-demo/gemini-powered-development/menu-service
```

## Create a code review skill

Run the following command in your terminal to create a workspace-scoped
`code-review` skill in `.agents/skills/code-review/SKILL.md`:

```bash
mkdir -p .agents/skills/code-review
cat <<'EOF' > .agents/skills/code-review/SKILL.md
---
name: code-review
description: Conduct a multi-pillar code review of local changes before merging.
---

# Code Review

Evaluate local changes using the following workflow. Approve changes that
improve overall code health and follow project conventions.

## 1. Context
- Inspect `git status` and `git diff` to summarize the scope and intent of the
  local modifications.

## 2. Multi-Pillar Review
Evaluate the changes across five pillars:
1. **Correctness:** Verify that the implementation matches requirements, handles
   edge cases (null, empty, boundary values) and error paths, and includes unit
   tests covering new behavior.
2. **Readability & Simplicity:** Check for clear naming matching project
   conventions, straightforward control flow, minimal diff size, and no dead
   code.
3. **Architecture:** Confirm adherence to existing design patterns, clean layer
   boundaries, appropriate data types, and no unnecessary dependencies.
4. **Security & Data Validation:** Check that inputs are validated at API and
   entity boundaries, queries are parameterized, and no secrets are exposed.
5. **Performance:** Check for N+1 queries, unbounded queries or missing
   pagination, blocking I/O, and unnecessary allocations.

## 3. Findings by Severity
Group actionable feedback ordered by impact using these prefixes:
- **Critical:** Security vulnerability, data loss, or broken functionality.
- **Required:** Must be addressed before merging.
- **Consider:** Optional suggestion worth evaluating.
- **Nit:** Minor style or polish feedback.

## 4. Verification
- Run the project's test suite (for example, `./mvnw test`) to verify that the
  project compiles and all tests pass.
- Provide a final verdict (`Approved` or `Request changes`).
EOF
```

Launch the Antigravity CLI:

```bash
agy
```

Verify the skill is loaded:

```text
/skills
```

The output displays the `code-review` skill and its description. Press `Esc` to
return to the prompt panel.

## Invoke skills in the Antigravity CLI

You can invoke skills in the Antigravity CLI in two ways:

1.  Autonomous invocation: The agent reads and follows relevant skills based on
    your prompt.
1.  Manual slash command: Type `/code-review` in the prompt panel to explicitly
    invoke a skill.

## Prepare and review code changes

Before running a code review, prompt the Antigravity CLI to implement a local
change in `menu-service`:

```text
Add description and rating fields to the Menu entity and update MenuResource to
support them.
```

Review and approve the suggested code changes. Once the local changes are
applied, send the following prompt to request a code review:

```text
Using available skills, review the local code changes in menu-service.
```

Below is sample code review output:

```text
## Code Review: Menu Service Changes

### 1. Context

• Scope: Added description (String) and rating (Double) fields to the Menu
Panache entity and updated MenuResource.update(...) to support updating them via
PUT requests, along with accompanying test assertions
in MenuResourceTest.
• Files Modified:
    • Menu.java
    • MenuResource.java
    • MenuResourceTest.java

──────
### 2. Multi-Pillar Review

1. Correctness:
    • The fields are appropriately defined in the entity with @Column mappings
    matching standard naming conventions (description and rating).
    • MenuResource.update(...) applies null checks before overwriting existing
    values, adhering to the partial-update convention used for other fields
    (tagLine, itemName, etc.).
    • MenuResourceTest was updated to test payload serialization and response
    verification for both new attributes.
2. Readability & Simplicity:
    • Clean, minimal diff.
    • Consistent formatting and field declaration style adhering to existing
    Panache entity conventions in the project.
3. Architecture:
    • Fits standard Quarkus Panache active-record / repository patterns used
    throughout the service.
    • No extra dependencies or architectural deviations introduced.
4. Security & Data Validation:
    • Input fields are currently unconstrained at the entity/DTO boundary (e.g.,
    rating could technically be negative or exceed typical rating ranges such as
    0.0 - 5.0). While this matches existing patterns in
    Menu (e.g. spiceLevel and itemPrice), adding Bean Validation constraints
    (@Min, @Max, @Size) is worth evaluating if boundaries are required.
5. Performance:
    • No N+1 queries, unindexed heavy relations, or blocking operations
    introduced.

──────
### 3. Findings by Severity

• Consider:
    • Rating Range Validation: Consider adding Bean Validation annotations on
    Menu.rating (e.g., @DecimalMin("0.0") and @DecimalMax("5.0")) to guard
    against invalid rating values.
    • PUT Endpoint Unit Test: Consider adding an explicit unit/integration test
    for the PUT /menu/{id} endpoint to explicitly verify update persistence
    behavior for description and rating.
• Nit:
    • Consider adding a short Javadoc comment on Menu.description and
    Menu.rating describing their intended format and range.

──────
### 4. Verification

• Test Execution: ./mvnw test
• Result: BUILD SUCCESS (1 test run, 0 failures, 0 errors, 0 skipped).
• Verdict: Approved
```

## Fix review findings

To address the findings, prompt the Antigravity CLI to plan and implement the
suggested changes:

```text
/plan changes to address the review findings
```

Sample output:

```text
I have prepared the implementation plan to address the review findings in
review_findings_plan.md.

### Summary of Proposed Changes:

1. Add PUT /menu/{id} unit test:
    • Add testUpdateMenu() to MenuResourceTest.java verifying selective updates
    of description and rating.
2. Validation Strategy:
    • The current codebase does not import quarkus-hibernate-validator and
    avoids Bean Validation across existing entity fields (itemName, itemPrice,
    etc.). Keeping Menu consistent avoids pulling in extra
    dependencies unless you want project-wide bean validation introduced.


Please review and confirm if you would like me to proceed with implementing
these test additions and verifying via ./mvnw test.
```

Review and approve the implementation plan using the `/artifact` command.

Run `/exit` to exit the Antigravity CLI:

```text
/exit
```

## Project-specific code review

The Antigravity CLI's customization system allows you to tailor its code review
to your project's specific needs. You can create custom Agent Skills or rules
that integrate your team's coding guidelines, style preferences, and best
practices directly into the local code review process.

This enables you to:

- **Enforce project-specific standards:** Develop custom checks for naming
  conventions, architectural patterns, or security policies relevant to your
  codebase.
- **Automate feedback:** Provide instant feedback on deviations from your
  guidelines, helping developers catch issues early.
- **Streamline onboarding:** Help new team members learn and adhere to project
  standards through custom code review skills.

To create a custom skill, consult the
[Antigravity Skills documentation](https://antigravity.google/docs/skills). You
can define `SKILL.md` instructions and helper scripts in `.agents/skills/` to
analyze your code against your defined guidelines.
