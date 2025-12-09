import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import MessageRole, FilePurpose, FunctionTool, FileSearchTool, ToolSet, ToolResources, FileSearchToolResource
from dotenv import load_dotenv
from pathlib import Path

def estimate_pizza_quantity(num_people: int, appetite_level: str) -> str:
    """
    Estimates the number of large pizzas needed based on number of people and appetite level.
    A large pizza is suitable for 2 adults and 2 children (4 people total).
    """
    # Base: 1 large pizza per 4 people
    base_pizzas = num_people / 4
    
    appetite_multiplier = {
        "light": 0.75,
        "normal": 1.0,
        "hungry": 1.5,
        "very hungry": 2.0
    }
    multiplier = appetite_multiplier.get(appetite_level.lower(), 1.0)
    
    total_pizzas = base_pizzas * multiplier
    recommended = max(int(total_pizzas + 0.5), 1)  # Round to nearest integer, minimum 1
    
    return f"For {num_people} people with {appetite_level} appetite, I recommend {recommended} large pizza(s)."

user_functions = {estimate_pizza_quantity}
functions = FunctionTool(functions=user_functions)

load_dotenv(override=True)

# create project instance
project_client = AIProjectClient(
    endpoint=os.environ["PROJECT_CONNECTION_STRING"],
    credential=DefaultAzureCredential(),
)

# Upload file and create vector store
directory_path = "C:\\Users\\demouser\\Downloads\\contoso-stores"
file_ids = []

for file_path in Path(directory_path).glob("*"):
    if file_path.is_file():
        try:
            file = project_client.agents.files.upload(
                file_path=str(file_path), 
                purpose=FilePurpose.AGENTS
            )
            file_ids.append(file.id)
            print(f"Uploaded: {file_path.name}")
        except Exception as e:
            print(f"Failed to upload {file_path.name}: {e}")

# Create vector store with all uploaded files
if file_ids:
    vector_store = project_client.agents.vector_stores.create_and_poll(
        file_ids=file_ids, 
        name="my_vectorstore"
    )
    print(f"Created vector store with {len(file_ids)} files")

# create agent
agent = project_client.agents.create_agent(
    model="gpt-4o",
    name="my-agent",
    instructions="""You are an agent that helps customers order pizzas from Contoso pizza.
    you can list all available Contoso Pizza stores exists around the world and answer questions about them. You always asks for a store location before confirming an order.
You have a Gen-Z personality, so you are friendly and helpful, but also a bit cheeky.
You can provide information about Contoso Pizza and its retail stores.
you should be able to reason about quantities and make helpful suggestions.
you suggests a reasonable amount of pizza based on the number of people and their appetite level.
you would asks for diner information (e.g., number of people, appetite) before making a calculation.
You help customers order a pizza of their chosen size, crust, and toppings.
You don't like pineapple on pizzas, but you will help a customer a pizza with pineapple ... with some snark.
Make sure you know the customer's name before placing an order on their behalf.
You can't do anything except help customers order pizzas and give information about Contoso Pizza. You will gently deflect any other questions.""",
    tools=functions.definitions,
)
print(f"Created agent, ID: {agent.id}")

# create thread
thread = project_client.agents.threads.create()
print(f"Created thread, ID: {thread.id}")

# add message
while True:

    # Get the user input
    user_input = input("You: ")

    # Break out of the loop
    if user_input.lower() in ["exit", "quit"]:
        break

    # Add a message to the thread
    message = project_client.agents.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER, 
        content=user_input
    )
    
    # create and process an agent run
    run = project_client.agents.runs.create_and_process(  
        thread_id=thread.id, 
        agent_id=agent.id,
        tool_choice="auto",
    )

    # fetch all messages from the thread
    messages = project_client.agents.messages.list(thread_id=thread.id)  
    first_message = next(iter(messages), None) 
    if first_message: 
        print(next((item["text"]["value"] for item in first_message.content if item.get("type") == "text"), ""))

# delete the agent when done
project_client.agents.delete_agent(agent.id)
print("Deleted agent")