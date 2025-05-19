import platform
import asyncio
import nest_asyncio
import json
import os
import requests
import subprocess
import hashlib
from dotenv import load_dotenv
from quart import Quart, render_template, request, session, redirect, url_for, Response
from utils.helpers import random_uuid
from models.agent import create_agent, get_conversation_history
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langchain_core.runnables import RunnableConfig
from utils.astream import astream_graph
from pymongo import MongoClient
from quart.config import Config # Import Config

print("Starting app.py...")  # Debug

# Windows-specific asyncio configuration
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
nest_asyncio.apply()
print("Asyncio configuration applied.")  # Debug

# Load environment variables
load_dotenv(override=True)
print("Environment variables loaded:", {k: "****" if k.endswith("_KEY") or k.endswith("_PASSWORD") else v for k, v in os.environ.items() if k in ["USER_ID", "USER_PASSWORD", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "USE_LOGIN", "SECRET_KEY", "GITHUB_TOKEN"]})  # Debug


# --- Start of corrected modification ---
class CustomQuart(Quart):
    # Update the signature to accept 'instance_relative'
    def make_config(self, instance_relative: bool = False) -> Config:
        # Call the make_config method from the superclass,
        # passing along the instance_relative argument.
        config = super().make_config(instance_relative=instance_relative)
        
        # Ensure 'PROVIDE_AUTOMATIC_OPTIONS' is set.
        config.setdefault("PROVIDE_AUTOMATIC_OPTIONS", True)
        return config

app = CustomQuart(__name__) # Use CustomQuart instead of Quart
# --- End of corrected modification ---
#app = Quart(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['PROVIDE_AUTOMATIC_OPTIONS'] = True
print("Quart app initialized.")  # Debug

# MongoDB setup
mongo_client = MongoClient(os.environ.get('MONGO_URI', 'mongodb://localhost:27017'))
db = mongo_client['mcp_platform']
users_collection = db['users']
print("MongoDB initialized.")  # Debug

# GitHub setup for private repository
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required for private repository access")
GITHUB_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3.raw"
}
TOOL_MARKET_URL = "https://raw.githubusercontent.com/meghanshram/ToolMarket/main"

# Global variables
checkpointer = MemorySaver()
agent = None
SYSTEM_PROMPT = """<ROLE>You are a smart agent with an ability to use tools... (same as Streamlit app) ... </OUTPUT_FORMAT>"""
OUTPUT_TOKEN_INFO = {
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 64000},
    "gpt-4o": {"max_tokens": 16000},
    "gpt-4o-mini": {"max_tokens": 16000},
}

def load_user_config(user_id):
    """Load user configuration from MongoDB."""
    user_data = users_collection.find_one({"_id": user_id})
    if not user_data:
        # Default config for new users
        default_config = {
            "_id": user_id,
            "tool_config": {"tools": []},
            "instructions": "",
            "env_vars": {},
            "selected_model": "gpt-4o",
            "tool_versions": {}
        }
        users_collection.insert_one(default_config)
        return default_config
    return user_data

def save_user_config(user_id, config):
    """Save user configuration to MongoDB."""
    users_collection.update_one({"_id": user_id}, {"$set": config}, upsert=True)

async def fetch_tool_manifest(tool_name, github_url=TOOL_MARKET_URL):
    """Fetch the manifest.json for a tool from the GitHub tool market."""
    url = f"{github_url}/tools/{tool_name}/manifest.json"
    try:
        response = requests.get(url, headers=GITHUB_HEADERS, timeout=10)
        print(response.json())
        response.raise_for_status()
        if response.status_code == 200:
            print(response.json())  # Debug
            return response.json()
        else:
            raise Exception(f"Unexpected status code {response.status_code} when fetching manifest for {tool_name}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch manifest for {tool_name}: {str(e)}")

async def download_tool(tool_name, file_name, github_url=TOOL_MARKET_URL):
    """Download a tool's Python script from the GitHub tool market to temp directory."""
    url = f"{github_url}/tools/{tool_name}/{file_name}"
    temp_dir = f"temp_tools/{tool_name}"
    os.makedirs(temp_dir, exist_ok=True)
    try:
        response = requests.get(url, headers=GITHUB_HEADERS, timeout=10)
        response.raise_for_status()
        if response.status_code == 200:
            checksum = hashlib.sha256(response.content).hexdigest()
            with open(f"{temp_dir}/{file_name}", "wb") as f:
                f.write(response.content)
            return checksum
        else:
            raise Exception(f"Unexpected status code {response.status_code} when downloading {file_name} for {tool_name}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to download {file_name} for {tool_name}: {str(e)}")

async def install_dependencies(dependencies):
    """Install Python dependencies for a tool."""
    if dependencies:
        subprocess.run(["pip", "install"] + dependencies, check=True)

# In app.py, inside initialize_agent
async def initialize_agent(user_id=None):
    global agent
    print("Initializing agent...")  # Debug
    try:
        if user_id is None:
            user_id = session.get('user_id')
        config = load_user_config(user_id)
        print(f"Loaded config: {config}")  # Debug
        
        mcp_config = config.get('tool_config', {})
        selected_model = config.get('selected_model', 'gpt-4o')
        user_instructions = config.get('instructions', '')
        updated_prompt = f"{SYSTEM_PROMPT}\n\n{user_instructions}" if user_instructions else SYSTEM_PROMPT
        print(f"Updated prompt with instructions: {updated_prompt}")  # Debug

        # Prepare temporary directory for tools
        temp_base_dir = "temp_tools"
        if os.path.exists(temp_base_dir):
            import shutil
            shutil.rmtree(temp_base_dir)  # Clear temp tools on each initialization
        os.makedirs(temp_base_dir, exist_ok=True)

        # Dynamically pull tools from GitHub
        tools = mcp_config.get('tools', [])
        updated_tools = []
        tool_versions = config.get('tool_versions', {})
        for tool in tools:
            tool_name = tool['name']
            github_url = tool.get('github_url', TOOL_MARKET_URL)
            try:
                # Fetch manifest
                manifest = await fetch_tool_manifest(tool_name, github_url)
                current_version = manifest['version']
                
                # Check if tool needs to be downloaded (version comparison)
                cached_version = tool_versions.get(tool_name, "0.0.0")
                if current_version != cached_version or not os.path.exists(f"temp_tools/{tool_name}/{manifest['file']}"):
                    if manifest['transport'] == "stdio":
                        # Download tool to temp directory
                        checksum = await download_tool(tool_name, manifest['file'], github_url)
                        # Install dependencies
                        await install_dependencies(manifest.get('dependencies', []))
                        # Update tool config with temp directory path
                        tool_config = {
                            "name": tool_name,
                            "transport": "stdio",
                            "command": "python",
                            "args": [f"temp_tools/{tool_name}/{manifest['file']}"],  # Revert to list
                            "env": config.get('env_vars', {}).get(tool_name, {})
                        }
                        # Update version tracking
                        tool_versions[tool_name] = current_version
                    elif manifest['transport'] == "sse":
                        tool_config = {
                            "name": tool_name,
                            "transport": "sse",
                            "url": tool.get('url', manifest.get('url'))
                        }
                        tool_versions[tool_name] = current_version
                else:
                    # Use cached tool from temp directory
                    if manifest['transport'] == "stdio":
                        tool_config = {
                            "name": tool_name,
                            "transport": "stdio",
                            "command": "python",
                            "args": [f"temp_tools/{tool_name}/{manifest['file']}"],  # Revert to list
                            "env": config.get('env_vars', {}).get(tool_name, {})
                        }
                    elif manifest['transport'] == "sse":
                        tool_config = {
                            "name": tool_name,
                            "transport": "sse",
                            "url": tool.get('url', manifest.get('url'))
                        }

                updated_tools.append(tool_config)
            except Exception as e:
                print(f"Failed to initialize tool {tool_name}: {str(e)}")  # Debug
                continue

        # Transform updated_tools into the format expected by MultiServerMCPClient
        connections = {}
        for tool_config in updated_tools:
            tool_name = tool_config["name"]
            # Remove 'name' from the config and use the rest as the connection parameters
            connection = {k: v for k, v in tool_config.items() if k != "name"}
            connections[tool_name] = connection

        # Update mcp_config with the connections dictionary
        mcp_config = connections  # Replace the entire mcp_config with the connections dict
        config['tool_versions'] = tool_versions
        save_user_config(user_id, config)
        print(f"Final mcp_config for agent: {mcp_config}")  # Debug

        # Initialize agent, bypassing MCP if no tools
        print(f"Debug: mcp_config before create_agent: {mcp_config}")  # Debug
        if not mcp_config:
            print("No tools configured, initializing agent without tools.")  # Debug
            agent_instance = await create_agent(mcp_config, selected_model, checkpointer, updated_prompt, use_mcp=False)
        else:
            print("Tools configured, initializing agent with MCP.")  # Debug
            agent_instance = await create_agent(mcp_config, selected_model, checkpointer, updated_prompt, use_mcp=True)
        print("Agent instance created")  # Debug
        app.config['tool_count'] = len(agent_instance.get_tools())
        print(f"Tool count: {app.config['tool_count']}")  # Debug
        agent = agent_instance
        print("Agent initialized.")  # Debug
    except Exception as e:
        print(f"Error during agent initialization: {str(e)}")  # Debug
        raise

@app.before_serving
async def startup():
    print("Running initial agent setup...")  # Debug
    try:
        print("Initial agent setup deferred until login.")  # Debug
    except Exception as e:
        print(f"Failed to initialize agent: {str(e)}")  # Debug
        raise

@app.after_serving
async def shutdown():
    print("Shutting down agent...")  # Debug
    global agent
    if agent:
        try:
            if hasattr(agent, '_client') and agent._client:
                await agent._client.__aexit__(None, None, None)
                print("MCP client closed")  # Debug
        except Exception as e:
            print(f"Error closing MCP client: {str(e)}")  # Debug
    agent = None
    print("Shutdown complete.")  # Debug

@app.route('/login', methods=['GET', 'POST'])
async def login():
    print("Accessing /login route...")  # Debug
    if request.method == 'POST':
        form = await request.form
        username = form['username']
        password = form['password']
        if (username == os.environ.get('USER_ID') and 
            password == os.environ.get('USER_PASSWORD')):
            session['authenticated'] = True
            session['user_id'] = username  # Store user_id in session
            session['thread_id'] = random_uuid()
            session['timeout_seconds'] = 120
            session['recursion_limit'] = 100
            session['selected_model'] = 'gpt-4o'
            print("Login successful, initializing agent")  # Debug
            await initialize_agent(session['user_id'])
            print("Redirecting to index")  # Debug
            return redirect(url_for('index'))
        print("Login failed: invalid credentials")  # Debug
        return await render_template('login.html', error='Invalid credentials')
    return await render_template('login.html')

@app.route('/logout')
async def logout():
    print("Accessing /logout route...")  # Debug
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
async def index():
    print("Accessing / route...")  # Debug
    if not session.get('authenticated'):
        print("Not authenticated, redirecting to login")  # Debug
        return redirect(url_for('login'))
    thread_id = session['thread_id']
    history = get_conversation_history(checkpointer, thread_id)
    print(f"Rendering index with history: {history}")  # Debug
    return await render_template('main.html', history=history, 
                                 tool_count=app.config.get('tool_count', 0))

@app.route('/ask', methods=['POST'])
async def ask():
    print("Accessing /ask route...")  # Debug
    if not session.get('authenticated'):
        print("Not authenticated, redirecting to login")  # Debug
        return redirect(url_for('login'))
    form = await request.form
    query = form['query']
    thread_id = session['thread_id']
    timeout_seconds = session.get('timeout_seconds', 120)
    recursion_limit = session.get('recursion_limit', 100)

    async def generate():
        print(f"Processing query: {query}")  # Debug
        if not agent:
            print("Agent not initialized")  # Debug
            yield f"data: {json.dumps({'error': 'Agent has not been initialized.'})}\n\n"
            return
        
        accumulated_text = []
        accumulated_tool = []

        try:
            async with asyncio.timeout(timeout_seconds):
                async for chunk in astream_graph(
                    agent,
                    {"messages": [HumanMessage(content=query)]},
                    config=RunnableConfig(
                        recursion_limit=recursion_limit,
                        thread_id=thread_id,
                    ),
                ):
                    print(f"Received chunk: {chunk}")  # Debug
                    if isinstance(chunk, dict) and 'agent' in chunk and 'messages' in chunk['agent']:
                        for message in chunk['agent']['messages']:
                            if isinstance(message, (AIMessage, AIMessageChunk)):
                                content = message.content
                                if isinstance(content, str) and content:
                                    accumulated_text.append(content)
                                    yield f"data: {json.dumps({'text': ''.join(accumulated_text)})}\n\n"
                                elif isinstance(content, list) and len(content) > 0:
                                    for item in content:
                                        if item.get("type") == "text":
                                            accumulated_text.append(item["text"])
                                            yield f"data: {json.dumps({'text': ''.join(accumulated_text)})}\n\n"
                                        elif item.get("type") == "tool_use":
                                            tool_data = item.get("partial_json", "")
                                            accumulated_tool.append(f"\n```json\n{str(tool_data)}\n```\n")
                                            yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
                                elif hasattr(message, "tool_calls") and message.tool_calls and len(message.tool_calls[0]["name"]) > 0:
                                    tool_call_info = message.tool_calls[0]
                                    accumulated_tool.append(f"\n```json\n{str(tool_call_info)}\n```\n")
                                    yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
                                elif hasattr(message, "invalid_tool_calls") and message.invalid_tool_calls:
                                    tool_call_info = message.invalid_tool_calls[0]
                                    accumulated_tool.append(f"\n```json\n{str(tool_call_info)}\n```\n")
                                    yield f"data: {json.dumps({'tool': ''.join(accumulated_tool), 'tool_label': 'Invalid Tool Call'})}\n\n"
                                elif hasattr(message, "tool_call_chunks") and message.tool_call_chunks:
                                    tool_call_chunk = message.tool_call_chunks[0]
                                    accumulated_tool.append(f"\n```json\n{str(tool_call_chunk)}\n```\n")
                                    yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
                                elif hasattr(message, "additional_kwargs") and "tool_calls" in message.additional_kwargs:
                                    tool_call_info = message.additional_kwargs["tool_calls"][0]
                                    accumulated_tool.append(f"\n```json\n{str(tool_call_info)}\n```\n")
                                    yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
                            elif isinstance(message, ToolMessage):
                                accumulated_tool.append(f"\n```json\n{str(message.content)}\n```\n")
                                yield f"data: {json.dumps({'tool': ''.join(accumulated_tool), 'tool_label': 'Tool Response'})}\n\n"

            final_text = "".join(accumulated_text)
            final_tool = "".join(accumulated_tool)
            history = get_conversation_history(checkpointer, thread_id)
            history.append({"role": "user", "content": query})
            if final_text:
                history.append({"role": "assistant", "content": final_text})
            if final_tool:
                history.append({"role": "assistant_tool", "content": final_tool})
            print(f"Query processed, final text: {final_text}, final tool: {final_tool}")  # Debug

        except asyncio.TimeoutError:
            print(f"Query timed out after {timeout_seconds} seconds")  # Debug
            yield f"data: {json.dumps({'error': f'Request timed out after {timeout_seconds} seconds'})}\n\n"
        except Exception as e:
            print(f"Error processing query: {str(e)}")  # Debug
            yield f"data: {json.dumps({'error': f'Error occurred during query processing: {str(e)}'})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

# @app.route('/settings', methods=['GET', 'POST'])
# async def settings():
#     print("Accessing /settings route...")  # Debug
#     if not session.get('authenticated'):
#         print("Not authenticated, redirecting to login")  # Debug
#         return redirect(url_for('login'))
    
#     user_id = session['user_id']
#     config = load_user_config(user_id)
#     env_prompts = session.get('env_prompts', {})

#     if request.method == 'POST':
#         form_data = await request.form
        
#         if 'add_tool' in form_data:
#             tool_name = form_data['tool_name']
#             github_url = form_data['github_url'] or TOOL_MARKET_URL
#             try:
#                 # Fetch manifest to validate tool and get metadata
#                 manifest = await fetch_tool_manifest(tool_name, github_url)
#                 new_tool = {
#                     "name": tool_name,
#                     "github_url": github_url
#                 }
#                 # Check for required environment variables
#                 required_env_vars = manifest.get('env_vars', [])
#                 env_vars_needed = []
#                 existing_env_vars = config.get('env_vars', {}).get(tool_name, {})
#                 for env_var in required_env_vars:
#                     if env_var['name'] not in existing_env_vars:
#                         env_vars_needed.append(env_var)
                
#                 if env_vars_needed:
#                     # Store prompts in session and re-render form
#                     session['env_prompts'] = {
#                         "tool_name": tool_name,
#                         "github_url": github_url,
#                         "env_vars_needed": env_vars_needed
#                     }
#                     return await render_template('settings.html', config=config, env_prompts=session['env_prompts'])
                
#                 # Add tool to config
#                 tools = config.get('tool_config', {}).get('tools', [])
#                 tools.append(new_tool)
#                 config['tool_config']['tools'] = tools
#                 save_user_config(user_id, config)
#                 print("Tool added successfully")  # Debug
#                 return await render_template('settings.html', config=config, success="Tool added successfully")
#             except Exception as e:
#                 print(f"Error adding tool: {str(e)}")  # Debug
#                 return await render_template('settings.html', config=config, error=f"Error adding tool: {str(e)}")
        
#         elif 'submit_env_vars' in form_data:
#             tool_name = form_data['tool_name']
#             github_url = form_data['github_url']
#             env_vars = {}
#             for key in form_data:
#                 if key.startswith('env_'):
#                     env_name = key[4:]  # Remove 'env_' prefix
#                     env_vars[env_name] = form_data[key]
            
#             # Save environment variables to config
#             if 'env_vars' not in config:
#                 config['env_vars'] = {}
#             config['env_vars'][tool_name] = env_vars
#             tools = config.get('tool_config', {}).get('tools', [])
#             tools.append({"name": tool_name, "github_url": github_url})
#             config['tool_config']['tools'] = tools
#             save_user_config(user_id, config)
#             session.pop('env_prompts', None)  # Clear prompts
#             print("Environment variables saved, tool added")  # Debug
#             return await render_template('settings.html', config=config, success="Tool added successfully")
        
#         elif 'apply_settings' in form_data:
#             config['selected_model'] = form_data['model']
#             session['timeout_seconds'] = int(form_data['timeout'])
#             session['recursion_limit'] = int(form_data['recursion_limit'])
#             config['instructions'] = form_data.get('instructions', '')
#             save_user_config(user_id, config)
#             print("Applying new settings...")  # Debug
#             await initialize_agent(user_id)
#             print("Settings applied.")  # Debug
#             return redirect(url_for('index'))  # Redirect to chat window
    
#     return await render_template('settings.html', config=config, env_prompts=env_prompts)


@app.route('/settings', methods=['GET', 'POST'])
async def settings():
    print("Accessing /settings route...")  # Debug
    if not session.get('authenticated'):
        print("Not authenticated, redirecting to login")  # Debug
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    config = load_user_config(user_id)
    env_prompts = session.get('env_prompts', {})

    if request.method == 'POST':
        form_data = await request.form
        print(f"DEBUG: Form data: {form_data}")  # Debug
        
        if 'add_tool' in form_data:
            tool_name = form_data['tool_name']
            github_url = form_data['github_url'] or TOOL_MARKET_URL
            print(f"DEBUG: Adding tool: {tool_name}, GitHub URL: {github_url}")  # Debug
            try:
                # Fetch manifest to validate tool and get metadata
                manifest = await fetch_tool_manifest(tool_name, github_url)
                print(f"DEBUG: Manifest fetched successfully: {manifest}")  # Debug
                new_tool = {
                    "name": tool_name,
                    "github_url": github_url
                }
                # Check for required environment variables
                required_env_vars = manifest.get('env_vars', [])
                env_vars_needed = []
                existing_env_vars = config.get('env_vars', {}).get(tool_name, {})
                for env_var in required_env_vars:
                    if env_var['name'] not in existing_env_vars:
                        env_vars_needed.append(env_var)
                
                if env_vars_needed:
                    # Store prompts in session and re-render form
                    session['env_prompts'] = {
                        "tool_name": tool_name,
                        "github_url": github_url,
                        "env_vars_needed": env_vars_needed
                    }
                    print(f"DEBUG: Environment variables needed: {env_vars_needed}")  # Debug
                    return await render_template('settings.html', config=config, env_prompts=session['env_prompts'])
                
                # Add tool to config
                tools = config.get('tool_config', {}).get('tools', [])
                tools.append(new_tool)
                config['tool_config']['tools'] = tools
                save_user_config(user_id, config)
                print("Tool added successfully")  # Debug
                return await render_template('settings.html', config=config, success="Tool added successfully")
            except Exception as e:
                print(f"Error adding tool: {str(e)}")  # Debug
                return await render_template('settings.html', config=config, error=f"Error adding tool: {str(e)}")
        
        elif 'submit_env_vars' in form_data:
            tool_name = form_data['tool_name']
            github_url = form_data['github_url']
            env_vars = {}
            for key in form_data:
                if key.startswith('env_'):
                    env_name = key[4:]  # Remove 'env_' prefix
                    env_vars[env_name] = form_data[key]
            print(f"DEBUG: Submitting env vars for {tool_name}: {env_vars}")  # Debug
            
            # Save environment variables to config
            if 'env_vars' not in config:
                config['env_vars'] = {}
            config['env_vars'][tool_name] = env_vars
            tools = config.get('tool_config', {}).get('tools', [])
            tools.append({"name": tool_name, "github_url": github_url})
            config['tool_config']['tools'] = tools
            save_user_config(user_id, config)
            session.pop('env_prompts', None)  # Clear prompts
            print("Environment variables saved, tool added")  # Debug
            return await render_template('settings.html', config=config, success="Tool added successfully")
        
        elif 'remove_tool' in form_data:
            tool_name = form_data['tool_name']
            print(f"DEBUG: Removing tool: {tool_name}")  # Debug
            try:
                # Remove tool from tool_config
                tools = config.get('tool_config', {}).get('tools', [])
                if not any(tool['name'] == tool_name for tool in tools):
                    raise ValueError(f"Tool {tool_name} not found in configuration")
                config['tool_config']['tools'] = [tool for tool in tools if tool['name'] != tool_name]
                
                # Remove associated environment variables
                if 'env_vars' in config and tool_name in config['env_vars']:
                    del config['env_vars'][tool_name]
                
                save_user_config(user_id, config)
                print(f"Tool {tool_name} removed successfully")  # Debug
                return await render_template('settings.html', config=config, success=f"Tool {tool_name} removed successfully")
            except Exception as e:
                print(f"Error removing tool: {str(e)}")  # Debug
                return await render_template('settings.html', config=config, error=f"Error removing tool: {str(e)}")
        
        elif 'apply_settings' in form_data:
            config['selected_model'] = form_data['model']
            session['timeout_seconds'] = int(form_data['timeout'])
            session['recursion_limit'] = int(form_data['recursion_limit'])
            config['instructions'] = form_data.get('instructions', '')
            print(f"DEBUG: Applying settings: {config}")  # Debug
            save_user_config(user_id, config)
            print("Applying new settings...")  # Debug
            await initialize_agent(user_id)
            print("Settings applied.")  # Debug
            return redirect(url_for('index'))  # Redirect to chat window
    
    return await render_template('settings.html', config=config, env_prompts=env_prompts)

@app.route('/reset', methods=['POST'])
async def reset():
    print("Accessing /reset route...")  # Debug
    session['thread_id'] = random_uuid()
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("Starting Quart server...")  # Debug
    app.run(host='0.0.0.0', port=5000, debug=True,use_reloader=False)
    print("Quart server started.")  # Debug























# import platform
# import asyncio
# import nest_asyncio
# import json
# import os
# from dotenv import load_dotenv
# from quart import Quart, render_template, request, session, redirect, url_for, Response
# from utils.helpers import load_config, save_config, random_uuid
# from models.agent import create_agent, get_conversation_history
# from langgraph.checkpoint.memory import MemorySaver
# from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
# from langchain_core.runnables import RunnableConfig
# from utils.astream import astream_graph

# print("Starting app.py...")  # Debug

# # Windows-specific asyncio configuration
# if platform.system() == "Windows":
#     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# nest_asyncio.apply()
# print("Asyncio configuration applied.")  # Debug

# # Load environment variables
# load_dotenv(override=True)
# print("Environment variables loaded:", {k: "****" if k.endswith("_KEY") or k.endswith("_PASSWORD") else v for k, v in os.environ.items() if k in ["USER_ID", "USER_PASSWORD", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "USE_LOGIN", "SECRET_KEY"]})  # Debug

# app = Quart(__name__)
# app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
# print("Quart app initialized.")  # Debug

# # Global variables
# checkpointer = MemorySaver()
# agent = None
# SYSTEM_PROMPT = """<ROLE>You are a smart agent with an ability to use tools... (same as Streamlit app) ... </OUTPUT_FORMAT>"""
# OUTPUT_TOKEN_INFO = {
#     "claude-3-5-sonnet-latest": {"max_tokens": 8192},
#     "claude-3-5-haiku-latest": {"max_tokens": 8192},
#     "claude-3-7-sonnet-latest": {"max_tokens": 64000},
#     "gpt-4o": {"max_tokens": 16000},
#     "gpt-4o-mini": {"max_tokens": 16000},
# }

# async def initialize_agent(config=None):
#     global agent
#     print("Initializing agent...")  # Debug
#     try:
#         if config is None:
#             config = load_config()
#             print(f"Loaded config: {config}")  # Debug
#         mcp_config = config.get('mcp_config', {})
#         selected_model = config.get('selected_model', 'gpt-4o')
#         # Append user-provided instructions to SYSTEM_PROMPT
#         user_instructions = config.get('instructions', '')
#         updated_prompt = f"{SYSTEM_PROMPT}\n\n{user_instructions}" if user_instructions else SYSTEM_PROMPT
#         print(f"Updated prompt with instructions: {updated_prompt}")  # Debug
#         agent_instance = await create_agent(mcp_config, selected_model, checkpointer, updated_prompt)
#         print("Agent instance created")  # Debug
#         app.config['tool_count'] = len(agent_instance.get_tools())
#         print(f"Tool count: {app.config['tool_count']}")  # Debug
#         agent = agent_instance
#         print("Agent initialized.")  # Debug
#     except Exception as e:
#         print(f"Error during agent initialization: {str(e)}")  # Debug
#         raise

# @app.before_serving
# async def startup():
#     print("Running initial agent setup...")  # Debug
#     try:
#         await initialize_agent()
#         print("Initial agent setup complete.")  # Debug
#     except Exception as e:
#         print(f"Failed to initialize agent: {str(e)}")  # Debug
#         raise

# @app.after_serving
# async def shutdown():
#     print("Shutting down agent...")  # Debug
#     global agent
#     if agent:
#         try:
#             if hasattr(agent, '_client'):
#                 await agent._client.__aexit__(None, None, None)
#                 print("MCP client closed")  # Debug
#         except Exception as e:
#             print(f"Error closing MCP client: {str(e)}")  # Debug
#     agent = None
#     print("Shutdown complete.")  # Debug

# @app.route('/login', methods=['GET', 'POST'])
# async def login():
#     print("Accessing /login route...")  # Debug
#     if request.method == 'POST':
#         form = await request.form
#         username = form['username']
#         password = form['password']
#         if (username == os.environ.get('USER_ID') and 
#             password == os.environ.get('USER_PASSWORD')):
#             session['authenticated'] = True
#             session['thread_id'] = random_uuid()
#             session['timeout_seconds'] = 120
#             session['recursion_limit'] = 100
#             session['selected_model'] = 'gpt-4o'
#             print("Login successful, redirecting to index")  # Debug
#             return redirect(url_for('index'))
#         print("Login failed: invalid credentials")  # Debug
#         return await render_template('login.html', error='Invalid credentials')
#     return await render_template('login.html')

# @app.route('/logout')
# async def logout():
#     print("Accessing /logout route...")  # Debug
#     session.clear()
#     return redirect(url_for('login'))

# @app.route('/')
# async def index():
#     print("Accessing / route...")  # Debug
#     if not session.get('authenticated'):
#         print("Not authenticated, redirecting to login")  # Debug
#         return redirect(url_for('login'))
#     thread_id = session['thread_id']
#     history = get_conversation_history(checkpointer, thread_id)
#     print(f"Rendering index with history: {history}")  # Debug
#     return await render_template('main.html', history=history, 
#                                  tool_count=app.config.get('tool_count', 0))

# @app.route('/ask', methods=['POST'])
# async def ask():
#     print("Accessing /ask route...")  # Debug
#     if not session.get('authenticated'):
#         print("Not authenticated, redirecting to login")  # Debug
#         return redirect(url_for('login'))
#     form = await request.form
#     query = form['query']
#     thread_id = session['thread_id']
#     timeout_seconds = session.get('timeout_seconds', 120)
#     recursion_limit = session.get('recursion_limit', 100)

#     async def generate():
#         print(f"Processing query: {query}")  # Debug
#         if not agent:
#             print("Agent not initialized")  # Debug
#             yield f"data: {json.dumps({'error': 'Agent has not been initialized.'})}\n\n"
#             return
        
#         accumulated_text = []
#         accumulated_tool = []

#         try:
#             async with asyncio.timeout(timeout_seconds):
#                 async for chunk in astream_graph(
#                     agent,
#                     {"messages": [HumanMessage(content=query)]},
#                     config=RunnableConfig(
#                         recursion_limit=recursion_limit,
#                         thread_id=thread_id,
#                     ),
#                 ):
#                     print(f"Received chunk: {chunk}")  # Debug
#                     if isinstance(chunk, dict) and 'agent' in chunk and 'messages' in chunk['agent']:
#                         for message in chunk['agent']['messages']:
#                             if isinstance(message, (AIMessage, AIMessageChunk)):
#                                 content = message.content
#                                 if isinstance(content, str) and content:
#                                     accumulated_text.append(content)
#                                     yield f"data: {json.dumps({'text': ''.join(accumulated_text)})}\n\n"
#                                 elif isinstance(content, list) and len(content) > 0:
#                                     for item in content:
#                                         if item.get("type") == "text":
#                                             accumulated_text.append(item["text"])
#                                             yield f"data: {json.dumps({'text': ''.join(accumulated_text)})}\n\n"
#                                         elif item.get("type") == "tool_use":
#                                             tool_data = item.get("partial_json", "")
#                                             accumulated_tool.append(f"\n```json\n{str(tool_data)}\n```\n")
#                                             yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
#                                 elif hasattr(message, "tool_calls") and message.tool_calls and len(message.tool_calls[0]["name"]) > 0:
#                                     tool_call_info = message.tool_calls[0]
#                                     accumulated_tool.append(f"\n```json\n{str(tool_call_info)}\n```\n")
#                                     yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
#                                 elif hasattr(message, "invalid_tool_calls") and message.invalid_tool_calls:
#                                     tool_call_info = message.invalid_tool_calls[0]
#                                     accumulated_tool.append(f"\n```json\n{str(tool_call_info)}\n```\n")
#                                     yield f"data: {json.dumps({'tool': ''.join(accumulated_tool), 'tool_label': 'Invalid Tool Call'})}\n\n"
#                                 elif hasattr(message, "tool_call_chunks") and message.tool_call_chunks:
#                                     tool_call_chunk = message.tool_call_chunks[0]
#                                     accumulated_tool.append(f"\n```json\n{str(tool_call_chunk)}\n```\n")
#                                     yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
#                                 elif hasattr(message, "additional_kwargs") and "tool_calls" in message.additional_kwargs:
#                                     tool_call_info = message.additional_kwargs["tool_calls"][0]
#                                     accumulated_tool.append(f"\n```json\n{str(tool_call_info)}\n```\n")
#                                     yield f"data: {json.dumps({'tool': ''.join(accumulated_tool)})}\n\n"
#                             elif isinstance(message, ToolMessage):
#                                 accumulated_tool.append(f"\n```json\n{str(message.content)}\n```\n")
#                                 yield f"data: {json.dumps({'tool': ''.join(accumulated_tool), 'tool_label': 'Tool Response'})}\n\n"

#             final_text = "".join(accumulated_text)
#             final_tool = "".join(accumulated_tool)
#             history = get_conversation_history(checkpointer, thread_id)
#             history.append({"role": "user", "content": query})
#             if final_text:
#                 history.append({"role": "assistant", "content": final_text})
#             if final_tool:
#                 history.append({"role": "assistant_tool", "content": final_tool})
#             print(f"Query processed, final text: {final_text}, final tool: {final_tool}")  # Debug

#         except asyncio.TimeoutError:
#             print(f"Query timed out after {timeout_seconds} seconds")  # Debug
#             yield f"data: {json.dumps({'error': f'Request timed out after {timeout_seconds} seconds'})}\n\n"
#         except Exception as e:
#             print(f"Error processing query: {str(e)}")  # Debug
#             yield f"data: {json.dumps({'error': f'Error occurred during query processing: {str(e)}'})}\n\n"

#     return Response(generate(), mimetype='text/event-stream')

# @app.route('/settings', methods=['GET', 'POST'])
# async def settings():
#     print("Accessing /settings route...")  # Debug
#     if not session.get('authenticated'):
#         print("Not authenticated, redirecting to login")  # Debug
#         return redirect(url_for('login'))
#     config = load_config()
#     if request.method == 'POST':
#         form_data = await request.form
#         if 'add_tool' in form_data:
#             try:
#                 new_tool = json.loads(form_data['new_tool'])
#                 config['mcp_config'].update(new_tool)
#                 save_config(config)
#                 print("Tool added successfully")  # Debug
#                 return await render_template('settings.html', config=config, success="Tool added successfully")
#             except json.JSONDecodeError as e:
#                 print(f"Invalid JSON in tool config: {str(e)}")  # Debug
#                 return await render_template('settings.html', config=config, error=f"Invalid JSON: {str(e)}")
#         elif 'apply_settings' in form_data:
#             config['selected_model'] = form_data['model']
#             session['timeout_seconds'] = int(form_data['timeout'])
#             session['recursion_limit'] = int(form_data['recursion_limit'])
#             # Add or update instructions
#             config['instructions'] = form_data.get('instructions', '')
#             save_config(config)
#             print("Applying new settings...")  # Debug
#             await initialize_agent(config)
#             print("Settings applied.")  # Debug
#             return redirect(url_for('index'))  # Redirect to chat window
#     return await render_template('settings.html', config=config)

# @app.route('/reset', methods=['POST'])
# async def reset():
#     print("Accessing /reset route...")  # Debug
#     session['thread_id'] = random_uuid()
#     return redirect(url_for('index'))

# if __name__ == '__main__':
#     print("Starting Quart server...")  # Debug
#     app.run(host='0.0.0.0', port=5000, debug=True)
#     print("Quart server started.")  # Debug

