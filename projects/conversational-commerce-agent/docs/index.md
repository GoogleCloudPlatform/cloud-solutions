# Conversational Agent \- Apparel

The retail industry is undergoing a transformation,
driven by the demand for personalized experiences within
an increasingly digital world.
While online retailers strive for global reach,
replicating the individualized service of a dedicated personal
shopper remains a challenge.

Google Cloud's Generative AI offers a solution by empowering
retailers to build virtual agents
capable of engaging in natural, human-like conversations.

These AI agents can understand complex queries, contextual information
(like cultural events or local weather),
and offer personalized style advice at scale effectively acting as
AI stylists for every customer.

The Conversational Agent \- Apparel demonstrates:

*   Orchestrate end customer conversations with Generative AI powered
Google Cloud Vertex Conversational Agent.
*   Search products using Vertex AI Search for Retail API.
*   Recommend products based on user’s input via Vertex AI Search for Retail API.
*   Integrate with third party delivery services via Application Integration.

## Architecture

The following diagram illustrates the solution architecture.

*   A web application with Dialogflow Messenger embedded as the frontend user interface.
*   The Conversational Agent uses Cloud Functions tools to
search and recommend products to the end customer.
*   The Conversational Agent uses Application Integration tools
to fetch delivery status.

![Architecture](architecture.svg "Architecture")

## Use cases

This demo is intended to showcase “art of the possible”
with conversational shopping experiences to existing and prospective retail customers.

### This demo covers

*   Connection to Retail Search API and Recommendations AI:
The agent establishes a seamless connection to Retail Search API and
Recommendations AI,
enabling accurate product search and personalized recommendations based on user preferences.
*   Intuitive Search Results and Recommendations:
The AI-driven virtual fashion coordinator facilitates a more intuitive search experience,
understanding user needs text inputs and delivering relevant recommendations considering
various factors like size, color preferences and cultural norms.
*   Rich Content Display:
The agent incorporates rich content display to provide users with
comprehensive information about products,
including customer reviews, sizing details,
and related items, contributing to a more informed decision-making process.

## Third-party delivery service integration

In this demo, we integrate with the demo DHL environment to
simulate delivery tracking.
The integration is enabled by default, no additional configuration required.
You can integrate with other 3rd party delivery services as needed.
Please refer to the Application Integration document for details.

## Deploy the solution

Please refer to the [Deployment Guide](deployment.md) for step by step instructions.

## Known Limitations

*   Product reviews are currently hardcoded
