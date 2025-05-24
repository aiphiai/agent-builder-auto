# DatabaseAgent - Intelligent Database Querying Tool

This tool, named "DatabaseAgent," is designed to answer natural language questions about a PostgreSQL database. It leverages the power of Large Language Models (LLMs) to understand user queries, generate appropriate SQL, execute it against the database, and then provide a natural language answer based on the results.

## Overview

The `DatabaseAgent` operates as a Model Context Protocol (MCP) server, allowing it to be easily integrated into larger systems. It exposes a single tool, `database_agent`, which takes a natural language question as input and returns a JSON string containing the answer, the executed SQL query, the raw query results, and any error encountered.

**Key Features:**

* **Natural Language to SQL:** Understands natural language questions and translates them into syntactically correct PostgreSQL queries.
* **Intelligent Query Generation:**
    * Limits results to a maximum of 10 rows by default (unless the user specifies otherwise).
    * Selects only the relevant columns necessary to answer the question, avoiding unnecessary `SELECT *`.
    * Uses only existing table and column names present in the database schema.
    * Ensures proper table joins when querying data from multiple tables.
* **SQL Execution:** Executes the generated SQL query against the connected PostgreSQL database.
* **Natural Language Answers:** Formulates clear and concise natural language answers based on the executed query results.
* **Error Handling:** Provides informative error messages in case of issues during any stage of the process.
* **JSON Output:** Returns all relevant information (answer, query, results, error) in a structured JSON format for easy parsing and utilization by other applications.

## Architecture

The `DatabaseAgent` follows a sequential workflow to process user questions:

1.  **Initialization:** The `FastMCP` server is initialized with the tool's name and instructions.
2.  **Environment Variable Loading:** The tool checks for the presence of `OPENAI_API_KEY` and `POSTGRESQL_URL` environment variables, which are crucial for accessing the LLM and the database, respectively.
3.  **Database Connection:** A connection to the PostgreSQL database is established using the provided `POSTGRESQL_URL` via Langchain's `SQLDatabase` utility.
4.  **LLM Initialization:** An instance of OpenAI's `ChatOpenAI` model (specifically `gpt-4o-mini`) is initialized using the `OPENAI_API_KEY`.
5.  **Query Generation:**
    * A prompt template is used to instruct the LLM to generate a SQL query based on the user's question and the database schema.
    * The prompt includes constraints on the number of results, column selection, and the use of existing table and column names.
    * Langchain's structured output parsing is used to ensure the LLM returns a valid SQL query.
6.  **Query Execution:** The generated SQL query is executed against the PostgreSQL database using Langchain's `QuerySQLDatabaseTool`.
7.  **Answer Generation:**
    * A prompt template is used to instruct the LLM to generate a natural language answer based on the original question, the generated SQL query, and the results obtained from executing the query.
8.  **JSON Output:** The final answer, the SQL query, the query results, and any potential error are formatted into a JSON string and returned.
9.  **Error Handling:** A `try-except` block is used to catch any exceptions that might occur during the process. In case of an error, a JSON response containing an error message is returned.

## Setup and Installation

To use the `DatabaseAgent`, you need to perform the following steps:

1.  **Install Dependencies:**
    ```bash
    pip install mcp langchain langchain-community openai typing-extensions psycopg2-binary # or your preferred PostgreSQL driver
    ```
2.  **Set Environment Variables:** You need to set the following environment variables:
    * `OPENAI_API_KEY`: Your OpenAI API key. You can obtain this from the OpenAI platform.
    * `POSTGRESQL_URL`: The connection string for your PostgreSQL database. The format typically looks like: `postgresql://user:password@host:port/database`. Replace the placeholders with your actual database credentials and connection details.

3.  **Ensure Database Access:** Make sure that the user specified in the `POSTGRESQL_URL` has the necessary permissions to query the tables you intend to interact with.

## Usage

The `DatabaseAgent` runs as an MCP server. You can interact with it by sending requests to the `database_agent` tool.

**Running the Server:**

To start the `DatabaseAgent` server, execute the Python script:

```bash
python your_script_name.py
