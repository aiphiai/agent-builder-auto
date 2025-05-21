"""This file was generated using `langgraph-gen` version 0.0.3.

This file provides a placeholder implementation for the corresponding stub.

Replace the placeholder implementation with your own logic.
"""

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
    ],
)

compiled_agent = agent.compile()

print(compiled_agent.invoke({"foo": "bar"}))
