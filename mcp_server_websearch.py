from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, List, Any
from langchain_community.tools.tavily_search import TavilySearchResults
import os

# Initialize FastMCP server with configuration
mcp = FastMCP(
    "SearchService",  # Name of the MCP server
    instructions="You are a search assistant that can query the internet using Tavily API and return relevant results.",
    host="0.0.0.0",  # Host address (0.0.0.0 allows connections from any IP)
    port=8008,  # Port number for the server
)

# Set the Tavily API key
os.environ["TAVILY_API_KEY"] = "tavily-api-key"

@mcp.tool()
async def search_internet(query: str, number_of_search_results: Optional[int] = 5) -> str:
    """
    Searches the internet using a query and returns the top results.

    This function queries the internet using Tavily API and returns relevant search results.

    Args:
        query (str): The search query string.
        number_of_search_results (int, optional): Number of search results to return. Defaults to 5.

    Returns:
        str: A string containing the search results or an error message
    """
    if not query.strip():
        return "Error: Query cannot be empty."
    
    try:
        # Create a TavilySearchResults tool instance with the specified number of results
        tavily_tool = TavilySearchResults(max_results=number_of_search_results)
        
        # Invoke the tool with the query
        search_results = tavily_tool.invoke(query)
    
        
        return search_results
    except Exception as e:
        return f"Error performing search: {str(e)}"

def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
    """Format the search results into a readable string."""
    if not results:
        return f"No results found for query: '{query}'"
    
    formatted_output = f"Search results for: '{query}'\n\n"
    
    for i, result in enumerate(results, 1):
        formatted_output += f"{i}. {result.get('title', 'No title')}\n"
        formatted_output += f"   URL: {result.get('url', 'No URL')}\n"
        
        # Add content if available
        if "content" in result and result["content"]:
            content = result["content"]
            # Truncate content if too long
            if len(content) > 300:
                content = content[:297] + "..."
            formatted_output += f"   Content: {content}\n"
        
        # Add a separator between results
        if i < len(results):
            formatted_output += "\n"
    
    return formatted_output

if __name__ == "__main__":
    # Start the MCP server with stdio transport
    mcp.run(transport="stdio")
