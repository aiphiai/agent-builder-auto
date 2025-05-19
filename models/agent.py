from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async def create_agent(mcp_config, selected_model, checkpointer, prompt, use_mcp=True):
    print(f"Creating agent with config: {mcp_config}, use_mcp={use_mcp}")  # Debug
    try:
        if not use_mcp:
            # Skip MCP client if no tools are configured
            print("Skipping MCP client initialization, creating agent with no tools.")  # Debug
            tools = []
        else:
            # Initialize MCP client if tools are present
            print(f"Creating MCP client with config: {mcp_config}")  # Debug
            client = MultiServerMCPClient(mcp_config)
            print("MCP client created")  # Debug
            print("Entering MCP client context...")  # Debug
            await client.__aenter__()
            print("MCP client context entered")  # Debug
            tools = client.get_tools()
            print(f"Tools loaded: {tools}")  # Debug

        # Initialize the model based on selected_model
        if selected_model.startswith('claude'):
            print("Initializing ChatAnthropic model...")  # Debug
            model = ChatAnthropic(model=selected_model, temperature=0.1, max_tokens=8192)
            print("ChatAnthropic model initialized")  # Debug
        else:
            print("Initializing ChatOpenAI model...")  # Debug
            model = ChatOpenAI(model=selected_model, temperature=0.1, max_tokens=16000)
            print("ChatOpenAI model initialized")  # Debug

        # Create the agent
        print("Creating react agent...")  # Debug
        agent = create_react_agent(model, tools, checkpointer=checkpointer, state_modifier=prompt)
        agent.get_tools = lambda: tools  # Ensure tools are accessible
        if use_mcp:
            agent._client = client  # Store client for cleanup if MCP was used
        else:
            agent._client = None  # No client to clean up
        print("React agent created")  # Debug
        return agent
    except Exception as e:
        print(f"Error in create_agent: {str(e)}")  # Debug
        raise

def get_conversation_history(checkpointer, thread_id):
    print(f"Fetching conversation history for thread_id: {thread_id}")  # Debug
    try:
        state = checkpointer.get({"configurable": {"thread_id": thread_id}})
        if not state:
            print("No conversation history found")  # Debug
            return []
        messages = []
        for msg in state.get("messages", []):
            role = "user" if msg.type == "human" else "assistant"
            content = msg.content
            if isinstance(content, list):
                content = "".join(item["text"] for item in content if item["type"] == "text")
            messages.append({"role": role, "content": content})
        print(f"Conversation history: {messages}")  # Debug
        return messages
    except Exception as e:
        print(f"Error fetching conversation history: {str(e)}")  # Debug
        return []








# from langchain_anthropic import ChatAnthropic
# from langchain_openai import ChatOpenAI
# from langgraph.prebuilt import create_react_agent
# from langchain_mcp_adapters.client import MultiServerMCPClient

# async def create_agent(mcp_config, selected_model, checkpointer, prompt):
#     print(f"Creating MCP client with config: {mcp_config}")  # Debug
#     try:
#         client = MultiServerMCPClient(mcp_config)
#         print("MCP client created")  # Debug
#         print("Entering MCP client context...")  # Debug
#         await client.__aenter__()
#         print("MCP client context entered")  # Debug
#         tools = client.get_tools()
#         print(f"Tools loaded: {tools}")  # Debug
#         if selected_model.startswith('claude'):
#             print("Initializing ChatAnthropic model...")  # Debug
#             model = ChatAnthropic(model=selected_model, temperature=0.1, max_tokens=8192)
#             print("ChatAnthropic model initialized")  # Debug
#         else:
#             print("Initializing ChatOpenAI model...")  # Debug
#             model = ChatOpenAI(model=selected_model, temperature=0.1, max_tokens=16000)
#             print("ChatOpenAI model initialized")  # Debug
#         print("Creating react agent...")  # Debug
#         agent = create_react_agent(model, tools, checkpointer=checkpointer, state_modifier=prompt)
#         agent.get_tools = lambda: tools  # Ensure tools are accessible
#         agent._client = client  # Store client for cleanup
#         print("React agent created")  # Debug
#         return agent
#     except Exception as e:
#         print(f"Error in create_agent: {str(e)}")  # Debug
#         raise

# def get_conversation_history(checkpointer, thread_id):
#     print(f"Fetching conversation history for thread_id: {thread_id}")  # Debug
#     try:
#         state = checkpointer.get({"configurable": {"thread_id": thread_id}})
#         if not state:
#             print("No conversation history found")  # Debug
#             return []
#         messages = []
#         for msg in state.get("messages", []):
#             role = "user" if msg.type == "human" else "assistant"
#             content = msg.content
#             if isinstance(content, list):
#                 content = "".join(item["text"] for item in content if item["type"] == "text")
#             messages.append({"role": role, "content": content})
#         print(f"Conversation history: {messages}")  # Debug
#         return messages
#     except Exception as e:
#         print(f"Error fetching conversation history: {str(e)}")  # Debug
#         return []