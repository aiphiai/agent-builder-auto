from mcp.server.fastmcp import FastMCP
import logging
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastMCP server with configuration
mcp = FastMCP(
    "EscalationService",  # Name of the MCP server
    instructions="You are an escalation assistant that logs customer issues and notifies a supervisor.",  # Instructions for the LLM
    host="0.0.0.0",  # Host address
    port=8007,  # Port number
)

@mcp.tool()
async def escalate_issue(customer_id: str, issue_description: str, supervisor_email: str = "supervisor@example.com") -> str:
    """
    Escalate a customer issue to a supervisor.

    This function logs the issue and sends a notification (simulated via logging).
    In a real scenario, integrate with an email or messaging system.

    Args:
        customer_id (str): The unique identifier of the customer.
        issue_description (str): A description of the issue to escalate.
        supervisor_email (str, optional): The supervisor's email for notification. Defaults to "supervisor@example.com".

    Returns:
        str: A message confirming the escalation or indicating an error.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"Escalation at {timestamp}: Customer ID {customer_id} - Issue: {issue_description} - Notified: {supervisor_email}"
        logging.info(log_message)
        return f"Issue escalated for Customer ID {customer_id}. Notification sent to {supervisor_email}."
    except Exception as e:
        return f"Error escalating issue: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")