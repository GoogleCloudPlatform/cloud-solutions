# Vertex AI Integration Setup

## ✅ System Successfully Switched to Vertex AI

The backend has been updated to use Google Cloud's Vertex AI with Gemini models
instead of mock responses.

## Current Status: Mock AI Mode

The system is currently running in **Mock AI mode** because Vertex AI
credentials are not configured. You'll see:

### Mock AI Indicators

-   🤖 **[MOCK AI]** prefix in all responses
-   ⚠️ **Orange warning banner** in chat UI: "Mock AI Response - Add Vertex AI
    access for real AI analysis"
-   **Mock AI badge** on chat messages
-   **Conversation tags** include "mock-ai"
-   **Metadata indicators**: `"isMockAI": true, "aiProvider": "mock"`

## To Enable Live Vertex AI Calls

### 1. Authentication Setup

#### Option A: For Local Development

```bash
# Install Google Cloud CLI if not already installed
# Then authenticate with your Google Cloud account
gcloud auth application-default login
```

#### Option B: For Cloud Run (Automatic)

Cloud Run instances automatically have access to Vertex AI when deployed with
proper service account permissions.

### 2. Configure Project Settings

Create a `.env` file in the `/api` directory:

```bash
cd /Users/cgrant/dev/contextual-ai/api
cp .env.example .env
```

Edit the `.env` file with your project details:

```toml
GOOGLE_CLOUD_PROJECT=kalschi-npc-001
VERTEX_AI_LOCATION=us-central1
```

### 3. Restart the Server

```bash
# Stop the current server
pkill -f "test_server.py"

# Start with the new API key
source venv/bin/activate
python test_server.py
```

## What Changes When API Key is Added

### Current Mock AI Responses

-   🤖 **[MOCK AI]** prefix in all responses
-   Context-aware responses based on widget data
-   Predefined action suggestions
-   Clear visual indicators in chat UI
-   Orange warning banners and badges

### With Live Vertex AI

-   **Enterprise-grade AI** powered by Gemini models on Google Cloud
-   **Default credential authentication** - no API keys to manage
-   **Dynamic AI-generated insights** based on actual data patterns
-   **Contextual analysis** that adapts to different scenarios
-   **Intelligent action recommendations** tailored to specific issues
-   **Follow-up conversations** that understand context
-   **Green "Vertex AI" badges** instead of orange "Mock AI" badges
-   **No mock AI indicators** - clean professional responses

## Example API Behavior

### Widget Analysis with Vertex AI

```json
{
  "response": "The 580ms response time spike at 2:00 PM correlates with a $400 revenue drop, indicating payment timeout issues during peak traffic. This suggests your payment gateway is struggling under load, causing transaction failures.",
  "actionSuggestions": [
    "Implement payment retry mechanisms with exponential backoff",
    "Scale payment gateway instances horizontally",
    "Add payment processing queue to handle spikes",
    "Set up alerting for response times >400ms"
  ],
  "confidence": 0.92,
  "analysisType": "vertex-chart-analysis"
}
```

### Follow-up Chat with Vertex AI

-   User:How can we prevent this in the future?|
-   Vertex AI:To prevent payment timeout issues, implement,implement
    auto-scaling for your payment service based on transaction volume, add
    circuit breakers to gracefully handle failures, and consider using a
    distributed payment queue system to buffer high-traffic periods.

## Architecture

```text
Widget Click → Backend API → Vertex AI (Gemini) → Contextual Analysis → Chat Display
```

## API Endpoints Using Vertex AI

-   `POST /api/chat/analyze-widget` - Widget analysis with Vertex AI Gemini
    models
-   `POST /api/chat/message` - Follow-up conversations with Vertex AI
-   `GET /api/chat/conversations` - Retrieve AI-generated conversations

## Benefits of Vertex AI

### Enterprise Features

-   **Default Credentials** - Uses Google Cloud service accounts, no API keys
-   **Enterprise Security** - Integrated with IAM and VPC controls
-   **Scalability** - Automatically handles scaling and load balancing
-   **Compliance** - SOC 2, ISO 27001, HIPAA compliant
-   **Cost Control** - Integrated with Google Cloud billing and quotas

### Technical Advantages

-   **Lower Latency** - Regional deployment reduces response times
-   **Better Integration** - Native integration with Google Cloud services
-   **Advanced Models** - Access to latest Gemini models and features
-   **Monitoring** - Built-in logging and monitoring via Cloud Console

## Cost Considerations

-   Vertex AI has usage-based pricing (typically more cost-effective than API)
-   Regional deployment can reduce data egress costs
-   Integrated with Google Cloud billing and budgets
-   Fallback mode ensures system works even without credentials

## Security & Authentication

### For Local Development

```bash
gcloud auth application-default login
```

### For Cloud Run

-   Uses service account attached to Cloud Run instance
-   No credentials stored in code or environment variables
-   Follows Google Cloud security best practices
-   IAM permissions control access to Vertex AI

### Required Permissions

-   `aiplatform.endpoints.predict`
-   `aiplatform.models.predict`
