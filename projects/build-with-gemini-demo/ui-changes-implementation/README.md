# Implementing UI changes with Gemini CLI

This demonstration highlights Gemini's powerful multimodal capabilities in
analyzing visual differences between UI versions (V1 and V2) and precisely
identifying necessary code modifications. Gemini effectively locates relevant
source files within the codebase and applies the required changes, showcasing
its ability to streamline the process of implementing UI updates and reduce
manual effort.

## Requirements

To follow this guide, you need

- A Google Cloud project with the `Owner` role.
- Gemini CLI: Installed and configured. Installation instructions are available
  at [geminicli.com](https://geminicli.com/docs/get-started/deployment/).

## Clone the codebase

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Clone the sample repository:

    ```bash
    git clone https://github.com/gitrey/cymbal-eats.git && \
    cd cymbal-eats/employee-ui
    ```

## Identify the new UI changes

Start Gemini CLI:

```bash
gemini
```

Send the following prompt to compare two images:

```text
Compare two images @current-ui.png and @updated-ui.png, find what has changed and provide the details.
```

Sample output:

```text
Based on the images you provided, here are the differences between the current and updated UI:

   * The checkbox label "Display only Ready items" has been shortened to "Ready only items".
   * The "CREATE A NEW MENU ITEM" button has been renamed to "NEW MENU ITEM".
   * The "ADJUST INVENTORY" button on each menu item card has been changed to "UPDATE INVENTORY".
   * Two new fields, "Rating" and "Description", have been added to each menu item card.
```

## Implement the changes

Send the following prompt to implement the changes:

```text
Locate the source files and make required changes based on the updated UI. Don't try to run the application.
```

Sample output:

```text
Code changes are complete; I've updated both ViewMenuPage.vue and Server.js.
```
