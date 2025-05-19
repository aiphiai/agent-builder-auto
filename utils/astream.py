async def astream_graph(agent, inputs, config=None):
    async for event in agent.astream(inputs, config=config):
        yield event