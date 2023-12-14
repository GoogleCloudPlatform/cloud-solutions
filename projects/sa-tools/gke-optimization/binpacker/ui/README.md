# Binpacker UI

UI to interact with APIs to archive following capabilities

- Scrape running GKE standard clusters, node pools and pods in a Google Project
- Provide binpacking recommendations(custom machine size, number of nodes) for selected workloads

## Prerequisite

- Node.js and Yarn(1.x) is installed

## Tech stack

- React
- Typescript
- Vite

## Setup procedure

1. Install required packages

   ```bash
   yarn
   ```

1. Generate code from proto file

   ```bash
   yarn genproto
   ```

1. Run in development mode

   ```bash
   yarn dev
   ```

1. Access the UI

   Access `http://localhost:5173/`
