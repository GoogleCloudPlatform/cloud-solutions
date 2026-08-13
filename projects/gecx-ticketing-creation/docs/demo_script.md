# GECX demo script: Comprehensive turn-by-turn guide

This guide provides a copy-paste ready, turn-by-turn script for demonstrating
all use cases supported by the **Cymbal Support Agent** (GECX Virtual Agent) and
the **Live Agent Voice Escalation with Agent Assist (AI Coach)**.

---

## Prerequisites

1.  **Open the Client Portal**: Open the live web portal URL in your browser:
    `https://cymbal-bff-web-[hash]-uc.a.run.app/loopback` _(Replace `[hash]`
    with your actual deployed service hash)._
1.  **Locate the Chat Widget**: Look for the floating **Cymbal Support** chat
    bubble in the bottom-right corner of the page.

---

## Demo scenario 1: Virtual agent chat and authentication

Demonstrate how the virtual agent handles security authentication before
accessing account details.

**Action**: Click the **Cymbal Support** chat bubble to start.

| Speaker / Role | Copy-Paste Input / Expected Response                                                                                        | Notes / Actions                                           |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------- |
| **User**       | `Hello`                                                                                                                     | Initiates the chat conversation.                          |
| **Agent**      | _Greetings & request for username/password._                                                                                | The virtual agent introduces itself.                      |
| **User**       | `test, 123`                                                                                                                 | Submits mock credentials (username: test, password: 123). |
| **Agent**      | `"Thank you, you've been successfully authenticated. Do you want to create a new service ticket or check an existing one?"` | Authentication succeeds.                                  |

---

## Demo scenario 2: Ticket status check (BigQuery data dip)

Demonstrate how the agent queries the backend database to check an existing
ticket status.

| Speaker / Role | Copy-Paste Input / Expected Response                                                                                                                | Notes / Actions                             |
| :------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------ |
| **User**       | `I want to check an existing ticket.`                                                                                                               | Requests ticket status check.               |
| **Agent**      | _Request for a brief summary of the issue._                                                                                                         | The agent prompts for ticket context.       |
| **User**       | `It's about a settlement issue.`                                                                                                                    | Provides the search keyword.                |
| **Agent**      | `"I found an open ticket, ID TICKET789, for a settlement issue. It is currently assigned to John Doe. Is there anything else I can help you with?"` | Agent queries BigQuery and returns results. |

---

## Demo scenario 3: Create new support ticket (mock database entry)

Demonstrate how the virtual agent guides the user through gathering details and
creating a new service ticket.

| Speaker / Role | Copy-Paste Input / Expected Response                                                     | Notes / Actions                                        |
| :------------- | :--------------------------------------------------------------------------------------- | :----------------------------------------------------- |
| **User**       | `I want to create a new ticket.`                                                         | Requests new ticket creation.                          |
| **Agent**      | _Asks for a detailed description of the service request and the settlement status._      | Gathers issue details.                                 |
| **User**       | `The settlement for transaction ABC is stuck in pending status.`                         | Provides description.                                  |
| **Agent**      | _Asks if the user has an image to provide (e.g. screenshot)._                            | Gathers optional attachment.                           |
| **User**       | `No image.`                                                                              | Declines image upload.                                 |
| **Agent**      | _Summarizes details, assigns a team (Settlement Operations), and asks for confirmation._ | Agent triggers sentiment analysis and auto-assignment. |
| **User**       | `Yes, please create the ticket.`                                                         | Confirms ticket creation.                              |
| **Agent**      | _Provides a newly generated Ticket ID (e.g. `CSST-XXXX`) and confirms success._          | The ticket is created in the mock DB.                  |

---

## Demo scenario 4: Compliance trigger (silent human handoff)

Demonstrate how the agent detects compliance-sensitive queries and triggers an
immediate, silent transfer to a human specialist.

| Speaker / Role | Copy-Paste Input / Expected Response                                                                  | Notes / Actions                                                                         |
| :------------- | :---------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------- |
| **User**       | `Why is my custody asset blocked and under administrative review?`                                    | Triggers compliance policy.                                                             |
| **Agent**      | `"Let me loop in a Senior Settlement Specialist to pull up those exact transaction records for you."` | Agent detects high-risk intent, says the mask phrase, and silently calls `end_session`. |
| **System**     | _The GECX chat bubble closes. The **"Voice Escalation Ready"** card appears._                         | Handoff is silently triggered in the background.                                        |

---

## Demo scenario 5: Manual voice escalation and agent assist (AI coach)

Demonstrate seamless transition from virtual chat to a WebRTC voice call with a
human specialist, featuring real-time AI suggestions.

| Speaker / Role    | Copy-Paste Input / Expected Response / System Action                          | Notes / Actions                                                     |
| :---------------- | :---------------------------------------------------------------------------- | :------------------------------------------------------------------ |
| **User**          | `Please transfer me to a human.`                                              | Requests manual escalation.                                         |
| **Agent**         | `"I am transferring you to a live agent now. Please hold."`                   | GECX chat bubble automatically closes.                              |
| **System**        | _A **"Voice Escalation Ready"** card appears on the web page._                | Chat handoff complete.                                              |
| **User (Action)** | _Click the **"Dial Voice Line"** button on the card._                         | Connects WebRTC voice channel. Allow microphone access if prompted. |
| **User (Action)** | _Click the **"[Demo] Open Agent Workstation ↗"** link._                       | Opens the human agent interface in a **new tab**.                   |
| **User / Agent**  | _Speak into your microphone._                                                 | Simulate conversation. Real-time transcription starts.              |
| **Agent Assist**  | _Live **"Cymbal Demo"** AI Coach suggestions appear in the right-hand panel._ | Watch the panel update dynamically based on speech cues.            |

---

## Demo scenario 6: Ticket resolution

Demonstrate how the human agent resolves the ticket in the CRM.

| Speaker / Role     | Action / Expected Result                                                                                                  | Notes                                    |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------ | :--------------------------------------- |
| **Agent (Action)** | In the **Agent Workstation** tab, enter a resolution summary (e.g. `Settlement resolved by correcting SSI instructions`). | Preparing to close the ticket.           |
| **Agent (Action)** | Click **"Resolve"**.                                                                                                      | Commits resolution.                      |
| **System**         | The call disconnects, and the session is cleared.                                                                         | The demo flow is completed successfully. |
