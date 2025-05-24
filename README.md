````markdown
# Quart Web Application for AI Agent Interaction

## Overview

This is a Quart-based web application designed to interact with an AI agent powered by tools fetched from a GitHub-based tool market. The application allows authenticated users to configure tools, manage settings, and interact with an AI agent that processes queries using a combination of natural language processing and tool execution. It integrates with MongoDB for user configuration storage, uses environment variables for sensitive data, and supports asynchronous operations for efficient handling of requests.

The application is built using Python with the Quart framework (an asynchronous alternative to Flask) and leverages libraries like `langchain` for AI agent functionality, `pymongo` for database interactions, and `requests` for fetching tool manifests and scripts from GitHub. It supports a login system, tool management, and a real-time chat interface using Server-Sent Events (SSE).

## Features

- **User Authentication**: Secure login system using environment variables for credentials.
- **AI Agent Interaction**: Users can send queries to an AI agent that processes them with configured tools.
- **Tool Management**: Dynamically fetch and install tools from a GitHub repository, including dependency installation and environment variable configuration.
- **MongoDB Integration**: Store and manage user configurations, including tool settings and environment variables.
- **Asynchronous Processing**: Uses `asyncio` for non-blocking operations, ensuring scalability and performance.
- **Real-Time Responses**: Implements Server-Sent Events (SSE) for streaming AI agent responses to the client.
- **Settings Management**: Allows users to configure the AI model, timeouts, recursion limits, and custom instructions.
- **Tool Versioning**: Tracks tool versions to avoid redundant downloads and ensure compatibility.

## Prerequisites

To run this application, you need the following:

- **Python**: Version 3.8 or higher.
- **MongoDB**: A running MongoDB instance (local or cloud-based).
- **GitHub Token**: A personal access token for accessing private GitHub repositories.
- **Environment Variables**: Set up in a `.env` file (see [Environment Variables](#environment-variables) section).
- **Dependencies**: Install required Python packages listed in the [Dependencies](#dependencies) section.

## Dependencies

The application relies on the following Python packages:

- `quart`: Asynchronous web framework (alternative to Flask).
- `pymongo`: MongoDB driver for Python.
- `requests`: For making HTTP requests to fetch tool manifests and scripts.
- `python-dotenv`: For loading environment variables from a `.env` file.
- `langchain-core`: Core components for AI agent functionality.
- `nest_asyncio`: To allow nested `asyncio` event loops (useful for development).
- `hashlib`: For computing checksums of downloaded tool scripts.
- `subprocess`: For installing Python dependencies via `pip`.
- `asyncio`: For asynchronous programming.

Additional dependencies may be required based on the tools fetched from the GitHub tool market.

Install dependencies using:

```bash
pip install quart pymongo requests python-dotenv langchain-core nest_asyncio
````

Additional dependencies for specific tools will be installed dynamically via the `install_dependencies` function.

## Environment Variables

Create a `.env` file in the project root with the following variables:

```plaintext
# User credentials for authentication
USER_ID=your_username
USER_PASSWORD=your_password

# API keys for AI models
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key

# Secret key for Quart session management
SECRET_KEY=your_secret_key

# GitHub token for accessing private repositories
GITHUB_TOKEN=your_github_token

# MongoDB connection URI
MONGO_URI=mongodb://localhost:27017

# Optional: Enable/disable login requirement
USE_LOGIN=true
```

  - `USER_ID` and `USER_PASSWORD`: Credentials for user authentication.
  - `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`: API keys for AI models (e.g., Claude, GPT-4o).
  - `SECRET_KEY`: A secret key for securing Quart sessions.
  - `GITHUB_TOKEN`: GitHub personal access token with repository read access.
  - `MONGO_URI`: MongoDB connection string (update for cloud-hosted MongoDB if needed).
  - `USE_LOGIN`: Set to `true` to enable authentication; set to `false` to bypass (useful for development).

## Project Structure

```
project_root/
├── app.py                  # Main application file
├── utils/
│   ├── helpers.py         # Utility functions (e.g., random_uuid)
│   └── astream.py         # Streaming functionality for AI agent responses
├── models/
│   └── agent.py           # AI agent creation and conversation history logic
├── templates/
│   ├── login.html         # Login page template
│   ├── main.html          # Main chat interface template
│   └── settings.html      # Settings page template
├── temp_tools/            # Temporary directory for downloaded tool scripts
├── .env                   # Environment variables (not tracked in version control)
└── README.md              # This documentation file
```

  - `app.py`: Core application logic, including routes, agent initialization, and tool management.
  - `utils/helpers.py`: Contains utility functions like `random_uuid` for generating unique thread IDs.
  - `utils/astream.py`: Implements `astream_graph` for streaming AI agent responses.
  - `models/agent.py`: Defines `create_agent` and `get_conversation_history` for AI agent interactions.
  - `templates/`: HTML templates for the web interface (using Jinja2).
  - `temp_tools/`: Temporary directory for storing downloaded tool scripts (created at runtime).
  - `.env`: Stores sensitive configuration (ensure this is not committed to version control).

## Setup Instructions

1.  **Clone the Repository:**

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    If a `requirements.txt` file does not exist, install the dependencies listed in the [Dependencies](https://www.google.com/search?q=%23dependencies) section.

3.  **Set Up MongoDB:**

    Ensure MongoDB is running locally or provide a valid `MONGO_URI` for a cloud instance.
    The application uses a database named `mcp_platform` with a `users` collection for storing user configurations.

4.  **Create .env File:**

    Create a `.env` file in the project root and populate it with the required environment variables (see [Environment Variables](https://www.google.com/search?q=%23environment-variables)).

5.  **Run the Application:**

    ```bash
    python app.py
    ```

    The server will start on `http://0.0.0.0:5000` in debug mode. Access it via a web browser at `http://localhost:5000`.

## Application Architecture

### Core Components

**Quart Application:**

The application is built using Quart, an asynchronous web framework compatible with Flask. A custom `CustomQuart` class overrides the `make_config` method to ensure `PROVIDE_AUTOMATIC_OPTIONS` is set to `True`, enabling CORS support for API routes.

**MongoDB Integration:**

User configurations are stored in a MongoDB database (`mcp_platform` database, `users` collection). The `load_user_config` and `save_user_config` functions handle reading and writing user settings, including tool configurations and environment variables.

**AI Agent:**

The AI agent is created using the `create_agent` function from `models/agent.py`. It supports multiple AI models (e.g., `gpt-4o`, `claude-3-5-sonnet-latest`) and integrates with tools fetched from a GitHub repository. The `MemorySaver` (checkpointer) from `langchain_core` persists conversation state.

**Tool Management:**

Tools are fetched from a GitHub repository (default: `https://raw.githubusercontent.com/<GITHUB_USERNAME>/ToolMarket/main`). The `fetch_tool_manifest` function retrieves the `manifest.json` for a tool, which includes metadata like version, file name, dependencies, and required environment variables. The `download_tool` function downloads tool scripts to a temporary directory (`temp_tools`). The `install_dependencies` function installs Python dependencies specified in the tool's manifest.

**Asynchronous Processing:**

The application uses `asyncio` for non-blocking operations, with `nest_asyncio` applied to support nested event loops (useful for development). Windows-specific `asyncio` configuration is applied to handle event loop policies.

**Server-Sent Events (SSE):**

The `/ask` route streams AI agent responses using SSE, allowing real-time updates in the client interface. Responses include text, tool calls, and tool responses, formatted as JSON and sent as SSE events.

### Key Routes

  - **/login (GET, POST):**
      - **GET**: Renders the login page (`login.html`).
      - **POST**: Authenticates users using `USER_ID` and `USER_PASSWORD` from environment variables. On success, initializes the AI agent and redirects to the main interface. Sets session variables: `authenticated`, `user_id`, `thread_id`, `timeout_seconds`, `recursion_limit`, and `selected_model`.
  - **/logout (GET):**
      - Clears the session and redirects to the login page.
  - **/** (GET):\*\*
      - The main chat interface (`main.html`), accessible only to authenticated users. Displays conversation history and the number of configured tools.
  - **/ask (POST):**
      - Handles user queries sent to the AI agent. Streams responses using SSE, including text, tool calls, and tool responses. Supports timeout and recursion limit configurations stored in the session.
  - **/settings (GET, POST):**
      - **GET**: Renders the settings page (`settings.html`), displaying current configuration and environment variable prompts (if any).
      - **POST**:
          - **Add Tool**: Adds a new tool by fetching its `manifest.json` from GitHub and prompting for required environment variables if needed.
          - **Submit Environment Variables**: Saves environment variables for a tool and adds it to the configuration.
          - **Remove Tool**: Removes a tool and its associated environment variables from the configuration.
          - **Apply Settings**: Updates the AI model, timeout, recursion limit, and custom instructions, then reinitializes the agent.
  - **/reset (POST):**
      - Resets the conversation by generating a new `thread_id` and redirects to the main interface.

### AI Agent Workflow

**Initialization**

The `initialize_agent` function is called during login or when settings are updated:

1.  Loads user configuration from MongoDB.
2.  Fetches tool manifests and scripts from GitHub, installs dependencies, and configures tools.
3.  Creates the AI agent using `create_agent` with the specified model, tools, and system prompt.

**Query Processing**

Queries are sent to the `/ask` route, which invokes the AI agent via `astream_graph`. Responses are streamed as SSE events, including:

  - Text: AI-generated text responses.
  - Tool Calls: JSON-formatted tool invocation details.
  - Tool Responses: Results from tool executions.
  - Errors: Timeout or processing errors.

**Conversation History**

  - Stored using `MemorySaver` and retrieved via `get_conversation_history`.
  - Displayed in the main interface (`main.html`).

### Tool Management Workflow

**Adding a Tool**

1.  User submits a tool name and optional GitHub URL via the settings page.
2.  The application fetches the tool's `manifest.json` to validate it and check for required environment variables.
3.  If environment variables are needed, the user is prompted to provide them.
4.  The tool script is downloaded to `temp_tools/<tool_name>` and dependencies are installed.
5.  The tool is added to the user's configuration and the agent is reinitialized.

**Removing a Tool**

1.  User selects a tool to remove via the settings page.
2.  The tool is removed from the configuration, along with its environment variables.
3.  The agent is reinitialized to reflect the updated configuration.

**Versioning**

  - Tool versions are tracked in the user's configuration (`tool_versions`).
  - If a tool's version matches the cached version and the script exists, it is not re-downloaded.

### Templates

The application uses Jinja2 templates for rendering HTML pages:

  - **login.html:**
      - A simple login form with fields for username and password. Displays error messages for invalid credentials.
  - **main.html:**
      - The main chat interface, displaying conversation history and a form to submit queries. Uses JavaScript to handle SSE responses from the `/ask` route and update the UI in real-time.
  - **settings.html:**
      - Displays current configuration (model, tools, instructions). Provides forms to:
          - Add a new tool.
          - Submit environment variables for a tool.
          - Remove a tool.
          - Update settings (model, timeout, recursion limit, instructions).

### Security Considerations

  - **Authentication:** User credentials are stored in environment variables, not hardcoded in the code.
  - **Session Management:** Uses Quart's session management with a secret key.
  - **GitHub Token:** Stored in an environment variable and used with minimal permissions (read access to repositories).
  - **MongoDB:** Ensure the MongoDB instance is secured with authentication and proper network access controls.
  - **Temporary Files:** Tool scripts are stored in a temporary directory (`temp_tools`), which is cleared on agent initialization to prevent stale files.

### Debugging

The application includes extensive debug logging to aid development:

  - Logs are printed at key points (e.g., route access, agent initialization, tool fetching).
  - To enable debug mode, the application runs with `debug=True` (set in `app.run`).
  - Check the console output for detailed information on errors or processing steps.

### Development Notes

  - **Asynchronous Code:** Ensure all I/O-bound operations (e.g., HTTP requests, database queries) are performed asynchronously using `await`.
  - **Error Handling:** Each route and function includes `try-except` blocks to handle errors gracefully and provide meaningful feedback.
  - **Tool Market:** The default tool market URL is `https://raw.githubusercontent.com/<GITHUB_USERNAME>/ToolMarket/main`. Ensure the repository structure matches the expected format (`tools/<tool_name>/manifest.json` and `tools/<tool_name>/`).
  - **MongoDB Schema:** The `users` collection stores documents with the following structure:

<!-- end list -->

```json
{
  "_id": "user_id",
  "tool_config": {
    "tools": [
      {
        "name": "tool_name",
        "github_url": "url"
      }
    ]
  },
  "instructions": "custom instructions",
  "env_vars": {
    "tool_name": {
      "env_var_name": "value"
    }
  },
  "selected_model": "model_name",
  "tool_versions": {
    "tool_name": "version"
  }
}
```

### Troubleshooting

  - **MongoDB Connection Issues:**
      - Verify the `MONGO_URI` in the `.env` file.
      - Ensure MongoDB is running and accessible.
  - **GitHub Token Errors:**
      - Check that the `GITHUB_TOKEN` has the necessary permissions (read access to the tool market repository).
      - Verify the repository URL and structure.
  - **Tool Download Failures:**
      - Ensure the tool market repository contains the expected `manifest.json` and script files.
      - Check network connectivity and GitHub API rate limits.
  - **Agent Initialization Errors:**
      - Verify that API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) are valid.
      - Check debug logs for specific error messages.
  - **SSE Issues:**
      - Ensure the client-side JavaScript correctly handles SSE events (check `main.html`).
      - Verify that the server is not behind a proxy that buffers SSE responses.

### Future Improvements

  - Input Validation: Add stricter validation for user inputs (e.g., tool names, environment variables).
  - Tool Caching: Implement a more robust caching mechanism for tools to reduce GitHub API calls.
  - Rate Limiting: Add rate limiting to prevent abuse of the `/ask` endpoint.
  - UI Enhancements: Improve the chat interface with better styling and real-time feedback.
  - Multi-User Support: Enhance the authentication system to support multiple users with unique configurations.
  - Error Recovery: Add mechanisms to retry failed tool downloads or agent initializations.

### Running in Production

  - Disable Debug Mode: Set `debug=False` in `app.run` for production.
  - Use a WSGI Server: Deploy with a production-ready server like `hypercorn` or `uvicorn`:

<!-- end list -->

```bash
hypercorn app:app --bind 0.0.0.0:5000
```

  - Secure MongoDB: Enable authentication and SSL for MongoDB.
  - HTTPS: Use a reverse proxy (e.g., Nginx) to enable HTTPS.
  - Logging: Implement structured logging to a file or service instead of console output.

<!-- end list -->

```
```
