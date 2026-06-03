import json
from google.adk.agents import Agent

# In-memory ticket database
TICKETS = [
    {"id": 1, "title": "Cannot Login", "description": "User reports they are unable to log into their account since the last update."},
    {"id": 2, "title": "Website Down", "description": "The main corporate website appears to be offline for several users."},
    {"id": 3, "title": "Password Reset Fail", "description": "Password reset link sends user to a 404 page."},
    {"id": 4, "title": "Feature Request: Dark Mode", "description": "User is requesting a dark mode option for the dashboard."},
    {"id": 5, "title": "Billing Discrepancy", "description": "User's latest invoice shows a charge for a service they cancelled."},
    {"id": 6, "title": "Mobile App Crash", "description": "The iOS app crashes on startup for users on the latest iOS version."},
    {"id": 7, "title": "Slow Performance", "description": "The application has been running very slowly for the past hour."},
    {"id": 8, "title": "Data Export Error", "description": "Exporting data to CSV format results in a corrupted file."},
    {"id": 9, "title": "Email Notifications Not Received", "description": "User is not receiving any email notifications for mentions."},
    {"id": 10, "title": "Typo in Documentation", "description": "Found a spelling error in the 'Getting Started' guide."},
    {"id": 11, "title": "API Rate Limit Too Low", "description": "The API rate limit is too restrictive for our integration needs."},
    {"id": 12, "title": "Video Upload Failure", "description": "Uploading video files larger than 100MB fails with a generic error."},
    {"id": 13, "title": "UI Glitch on Firefox", "description": "The main navigation bar is misaligned when using Mozilla Firefox."},
    {"id": 14, "title": "Two-Factor Authentication (2FA) Setup", "description": "User needs assistance setting up 2FA for their account."},
    {"id": 15, "title": "Subscription Cancellation", "description": "User wants to cancel their monthly subscription immediately."},
    {"id": 16, "title": "Incorrect User Permissions", "description": "A user with 'read-only' access is able to edit documents."},
    {"id": 17, "title": "Search Function Not Working", "description": "The search bar does not return any results for any query."},
    {"id": 18, "title": "Request for Integration with Slack", "description": "Our team would like to see a native Slack integration."},
    {"id": 19, "title": "Image Rendering Issue", "description": "Uploaded JPG images are appearing distorted and discolored."},
    {"id": 20, "title": "Account Deletion Request", "description": "User requests that their account and all associated data be permanently deleted."}
]

def get_ticket_details(ticket_id: int) -> str:
    """Retrieves the full details of a specific ticket by its ID."""
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            return json.dumps(ticket)
    return f"Ticket with ID {ticket_id} not found."

def get_ticket_summary(ticket_id: int) -> str:
    """Retrieves a summary (the description) of a specific ticket by its ID."""
    for ticket in TICKETS:
        if ticket["id"] == ticket_id:
            return ticket["description"]
    return f"Ticket with ID {ticket_id} not found."

root_agent = Agent(
    name="customer_support",
    model="gemini-2.5-flash",
    description="A customer support agent that can look up ticket details and summaries.",
    instruction="""You are a customer support agent.
    - When a user asks for the 'details' or 'full details' of a ticket, use the `get_ticket_details` tool.
    - When a user asks for a 'summary' of a ticket, use the `get_ticket_summary` tool.
    - The user will provide the ticket ID. Identify it and pass it to the correct tool.
    - If a tool returns a 'not found' message, relay that information to the user.
    - Present the information clearly. If details are in JSON format, you can present them in a readable way.
    """,
    tools=[get_ticket_details, get_ticket_summary]
)
