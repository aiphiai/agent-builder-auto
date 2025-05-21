"""This is an automatically generated file. Do not modify it.

This file was generated using `langgraph-gen` version 0.0.3.
To regenerate this file, run `langgraph-gen` with the source `yaml` file as an argument.

Usage:

1. Add the generated file to your project.
2. Create a new agent using the stub.

Below is a sample implementation of the generated stub:

```python
from typing_extensions import TypedDict

from stub import CustomAgent

class SomeState(TypedDict):
    # define your attributes here
    foo: str

# Define stand-alone functions
def Retriever(state: SomeState) -> dict:
    print("In node: Retriever")
    return {
        # Add your state update logic here
    }


def agent(state: SomeState) -> dict:
    print("In node: agent")
    return {
        # Add your state update logic here
    }


def Vlaidatoin(state: SomeState) -> dict:
    print("In node: Vlaidatoin")
    return {
        # Add your state update logic here
    }


def None(state: SomeState) -> str:
    print("In condition: None")
    raise NotImplementedError("Implement me.")


agent = CustomAgent(
    state_schema=SomeState,
    impl=[
        ("Retriever", Retriever),
        ("agent", agent),
        ("Vlaidatoin", Vlaidatoin),
        ("None", None),
    ]
)

compiled_agent = agent.compile()

print(compiled_agent.invoke({"foo": "bar"}))
"""

from typing import Callable, Any, Optional, Type

from langgraph.constants import START, END
from langgraph.graph import StateGraph


def CustomAgent(
    *,
    state_schema: Optional[Type[Any]] = None,
    config_schema: Optional[Type[Any]] = None,
    input: Optional[Type[Any]] = None,
    output: Optional[Type[Any]] = None,
    impl: list[tuple[str, Callable]],
) -> StateGraph:
    """Create the state graph for CustomAgent."""
    # Declare the state graph
    builder = StateGraph(
        state_schema, config_schema=config_schema, input=input, output=output
    )

    nodes_by_name = {name: imp for name, imp in impl}

    all_names = set(nodes_by_name)

    expected_implementations = {
        "Retriever",
        "agent",
        "Vlaidatoin",
    }

    missing_nodes = expected_implementations - all_names
    if missing_nodes:
        raise ValueError(f"Missing implementations for: {missing_nodes}")

    extra_nodes = all_names - expected_implementations

    if extra_nodes:
        raise ValueError(
            f"Extra implementations for: {extra_nodes}. Please regenerate the stub."
        )

    # Add nodes
    builder.add_node("Retriever", nodes_by_name["Retriever"])
    builder.add_node("agent", nodes_by_name["agent"])
    builder.add_node("Vlaidatoin", nodes_by_name["Vlaidatoin"])

    # Add edges
    builder.add_edge("Retriever", END)
    builder.add_edge("Vlaidatoin", END)
    builder.add_edge("agent", "Vlaidatoin")
    builder.add_conditional_edges(
        START,
        nodes_by_name["None"],
        [
            "Retriever",
            "agent",
        ],
    )
    return builder
