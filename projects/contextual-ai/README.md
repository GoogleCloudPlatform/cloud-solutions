# Contextual AI

Contextual AI is a solution that demonstrates how to build interactive,
AI-powered dashboards. It allows users to not only visualize data but also
interact with it conversationally to gain deeper insights. The solution
showcases how to integrate data APIs, AI agents, and dynamic query generation
(like Natural Language to SQL) to create a rich, contextual user experience.

## Architecture

The solution is composed of a frontend UI, a data access API, and an agent API
powered by generative AI. It supports different types of widgets for data
interaction.

### Key Features

- **Deterministic Widgets**: Widgets that fetch data using pre-defined SQL
  queries via a Data Access API.
- **Dynamic Widgets**: Widgets that use an Agent API to generate SQL queries
  from natural language, allowing for free-form data exploration.
- **AI-Powered Analysis**: Users can select data points and ask questions. An AI
  agent fetches relevant data, analyzes it, and provides answers.
- **Search Integration**: A search widget integrates with Vertex AI Search to
  provide search and summarization capabilities.

Update **2026-03-04**:

This project has been archived. You can still access the code by browsing the
repository at
[commit dd333d5](https://github.com/GoogleCloudPlatform/cloud-solutions/tree/dd333d52914b6b5df80ac45ee3086b8294af2df7/projects/contextual-ai)
