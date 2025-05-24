
import os
from mcp.server.fastmcp import FastMCP
import json
import os
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from typing_extensions import TypedDict, Annotated


# Initialize FastMCP server
mcp = FastMCP(
    "DatabaseAgent",
    instructions="""
    You are a database expert tasked with answering natural language questions about a PostgreSQL database.
    Generate a syntactically correct PostgreSQL query to answer the question, execute it, and provide a natural language answer.
    - Limit results to 10 rows unless specified.
    - Select only relevant columns, avoiding `SELECT *`.
    - Use only existing table and column names from the schema.
    - Ensure proper table joins for multi-table queries.
    Return the final answer, SQL query, and results in JSON format.
    """,
    host="0.0.0.0",
    port=8007,  # Unique port for this tool
)

# Define state and output types (unchanged)
class State(TypedDict):
    question: str
    query: str
    result: str
    answer: str

class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: Annotated[str, ..., "Syntactically valid SQL query."]

@mcp.tool()
async def database_agent(question: str) -> str:
    """
    Answer a natural language question about a PostgreSQL database.

    Args:
        question (str): Natural language question about the database.

    Returns:
        str: JSON string containing the answer, SQL query, and results.
    """
    try:
        # Load environment variables (unchanged)
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not os.environ.get("POSTGRESQL_URL"):
            raise ValueError("POSTGRESQL_URL environment variable is required")

        # Initialize database (unchanged)
        db = SQLDatabase.from_uri(os.environ.get("POSTGRESQL_URL"))

        # Initialize LLM (unchanged)
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY"))

        # Define prompt template (unchanged)
        system_message = """
        Given an input question, create a syntactically correct {dialect} query to
        run to help find the answer. Unless the user specifies in his question a
        specific number of examples they wish to obtain, always limit your query to
        at most {top_k} results. You can order the results by a relevant column to
        return the most interesting examples in the database.

        Never query for all the columns from a specific table, only ask for a the
        few relevant columns given the question.

        Pay attention to use only the column names that you can see in the schema
        description. Be careful to not query for columns that do not exist. Also,
        pay attention to which column is in which table.

        Only use the following tables:
        {table_info}
        """

        user_prompt = "Question: {input}"

        query_prompt_template = ChatPromptTemplate(
            [("system", system_message), ("user", user_prompt)]
        )

        # Define query generation (unchanged)
        def write_query(state: State):
            """Generate SQL query to fetch information."""
            prompt = query_prompt_template.invoke(
                {
                    "dialect": db.dialect,
                    "top_k": 10,
                    "table_info": db.get_table_info(),
                    "input": state["question"],
                }
            )
            structured_llm = llm.with_structured_output(QueryOutput)
            result = structured_llm.invoke(prompt)
            return {"query": result["query"]}

        # Define query execution (unchanged)
        def execute_query(state: State):
            """Execute SQL query."""
            execute_query_tool = QuerySQLDatabaseTool(db=db)
            return {"result": execute_query_tool.invoke(state["query"])}

        # Define answer generation (unchanged)
        def generate_answer(state: State):
            """Answer question using retrieved information as context."""
            prompt = (
                "Given the following user question, corresponding SQL query, "
                "and SQL result, answer the user question.\n\n"
                f'Question: {state["question"]}\n'
                f'SQL Query: {state["query"]}\n'
                f'SQL Result: {state["result"]}'
            )
            response = llm.invoke(prompt)
            return {"answer": response.content}

        # Execute the workflow (adapted from langgraph to sequential execution)
        state = {"question": question, "query": "", "result": "", "answer": ""}
        
        # Step 1: Generate query
        state.update(write_query(state))
        
        # Step 2: Execute query
        state.update(execute_query(state))
        
        # Step 3: Generate answer
        state.update(generate_answer(state))

        # Format output as JSON
        return json.dumps({
            "answer": state["answer"],
            "query": state["query"],
            "result": state["result"],
            "error": None
        })

    except Exception as e:
        return json.dumps({
            "answer": "",
            "query": "",
            "result": "",
            "error": f"Error: {str(e)}"
        })

if __name__ == "__main__":
    mcp.run(transport="stdio")