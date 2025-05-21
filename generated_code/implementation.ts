/* This file was generated using `langgraph-gen` version 0.0.3.

This file provides a placeholder implementation for the corresponding stub.

Replace the placeholder implementation with your own logic.
*/
import { Annotation } from "@langchain/langgraph";

import { CustomAgent } from "stub"

const agent = CustomAgent(Annotation.Root({ foo: Annotation<string>() }), {
    Retriever: (state) => {
        console.log("In node: Retriever")
        return {} // Add your state update logic here
    },
    agent: (state) => {
        console.log("In node: agent")
        return {} // Add your state update logic here
    },
    Vlaidatoin: (state) => {
        console.log("In node: Vlaidatoin")
        return {} // Add your state update logic here
    },
    None: (state) => {
        console.log("In condition: None");
        throw new Error("Implement me. Returns one of the paths.");
    },
});

const compiled_agent = agent.compile();
console.log(await compiled_agent.invoke({ foo: "bar" }));