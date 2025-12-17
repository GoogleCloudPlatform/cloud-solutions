# Interactive code reviews with Gemini CLI

This guide provides a walkthrough for using the Gemini CLI Code Review extension
to perform a review of local code changes. This extension offers a powerful,
low-friction method for developers to receive immediate, Gemini-driven feedback
on their work-in-progress. By executing a simple `/code-review` command,
developers can gain insights into their local changes, identify potential
issues, and receive concrete suggestions for improvement without submitting a
formal change request.

This tool significantly enhances the pre-submission review process, leading to
higher-quality code, faster iterations, and a more efficient development
workflow. Integrating the Gemini CLI's Code Review extension is a vital step
toward leveraging Gemini to streamline code development and review practices.

This guide covers:

- **Prerequisites:** Ensuring you have Gemini CLI and the Code Review extension
  installed.
- **Workflow:** How to invoke the `/code-review` command in your terminal.
- **Review Process:** Understanding the output and implementing Gemini's
  suggestions and analysis of changes in your feature branch compared to the
  main branch.

## Requirements

To follow this guide, you need

- A Google Cloud project with the `Owner` role.
- Gemini CLI: Installed and configured. Installation instructions are available
  at [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

## Install Code Review extension

Open [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell)
and run the following command in your terminal to install the
[code review](https://github.com/gemini-cli-extensions/code-review) extension.

```bash
gemini extensions install https://github.com/gemini-cli-extensions/code-review
```

Launch the Gemini CLI:

```bash
gemini
```

Verify the installation:

```text
/code-review
```

The output will display the code review command and its description.

Press `Ctrl + C` twice to exit Gemini CLI.

## Reviewing local changes

Once you have the extension installed, you can use `/code-review` command to
review changes in your existing repository.

## Prepare and review changes

These instructions assume you have completed the
[Prototype with Gemini CLI](https://googlecloudplatform.github.io/cloud-solutions/build-with-gemini-demo/prototype-with-gemini-cli/)
demo guide.

After completing that demo guide, you will have unstaged changes in your
repository. You can then ask Gemini CLI to create a new feature branch and
commit these changes. This extension compares committed changes on your feature
branch against the main branch.

Open a new terminal window and configure your Git account details by customizing
these with your own email and name:

```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

Start a new Gemini CLI session or use an existing one to send the following
prompt to create a branch and commit the changes:

```text
Create feature branch and commit changes with descriptive message
```

Sample output:

```text
The feature branch feat/initial-conference-app has been created and all changes have been committed.
```

Send the following prompt to request code review:

```text
/code-review
```

Below is sample code review output for changes made in the
[Prototype with Gemini CLI](https://googlecloudplatform.github.io/cloud-solutions/build-with-gemini-demo/prototype-with-gemini-cli/)
demo guide.

```text
Change summary: This change introduces a prototype for a Flask-based conference event tracking application, allowing users to view, add, and see details for events using an in-memory data store.

  File: conference-app/app.py
  L34: [HIGH] Race condition on shared global variable.

  The next_id variable is read and incremented without a lock. In a multi-threaded server environment, concurrent requests to add_event could be assigned the same ID, leading to data corruption where one event overwrites another.

  L36: [HIGH] Missing server-side validation and error handling.

  The application does not validate the format of the incoming date_str. If a user submits a date in a format other than 'YYYY-MM-DD', the strptime call will raise a ValueError, causing a 500 Internal Server Error. The application should
  validate all user-provided inputs and handle potential errors gracefully.

  L58: [MEDIUM] Inefficient event lookup.

  The application retrieves an event by iterating through the entire events list, which is an O(n) operation. As the number of events grows, this will become a performance bottleneck. Using a dictionary (hash map) for the events data store,
  with the event_id as the key, would allow for a more efficient O(1) lookup.

  File: conference-app/templates/event_detail.html
  L12: [LOW] Missing rel="noopener noreferrer" with target="_blank".

  Using target="_blank" without rel="noopener noreferrer" creates a security vulnerability where the newly opened page can gain control of the originating page via the window.opener object.
```

## Fix review findings

To address the findings, request Gemini CLI to implement the suggested changes:

```text
Implement suggested changes
```

When all suggestions are resolved, request another code review to verify the
fixes. You can repeat this process as many times as needed to ensure your code
is ready for a formal team review.

```text
No issues found. Code looks clean and ready to merge.
```

## Project Specific Code Review

The Gemini CLI's extensibility allows you to tailor its code review to your
project's specific needs. You can create custom extensions or commands that
integrate your team's unique coding guidelines, style preferences, and best
practices directly into the local code review process.

This means you can

- **Enforce Project-Specific Standards:** Develop custom checks for naming
  conventions, architectural patterns, or security policies relevant to your
  codebase.
- **Automate Feedback:** Provide instant, automated feedback on deviations from
  your guidelines, helping developers catch issues early.
- **Streamline Onboarding:** New team members can quickly learn and adhere to
  project standards through custom code review commands.

To create a custom extension, consult the
[Gemini CLI Extensions Documentation](https://geminicli.com/docs/extensions/getting-started-extensions/).
You can define custom commands that execute scripts or external tools to analyze
your code against your defined guidelines.
