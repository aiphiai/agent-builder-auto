import os
from langchain_openai import AzureChatOpenAI
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field


AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")


def get_openai_client():
    llm = AzureChatOpenAI(
        deployment_name="gpt-4o",
        openai_api_version="2024-12-01-preview",
        temperature=0,
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
    )

    return llm


if __name__ == "__main__":

    class test(BaseModel):
        joke: str = Field(description="joke in terms of space")
        name: str = Field(
            description="name of any history story of space realted to stars"
        )

    client = get_openai_client()
    structured_client = client.with_structured_output(test)
    response = structured_client.invoke("tell me a joke about ai")
    print(response)
