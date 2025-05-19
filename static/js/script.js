document.addEventListener('DOMContentLoaded', () => {
    console.log('Script loaded');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('query-input');
    const output = document.getElementById('chat-output');

    if (!form || !input || !output) {
        console.error('Required DOM elements missing:', { form, input, output });
        return;
    }
    console.log('DOM elements found');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = input.value.trim();
        if (!query) return;

        console.log('Submitting query:', query);

        // Display user query
        const userDiv = document.createElement('div');
        userDiv.className = 'user-message';
        userDiv.textContent = query;
        output.appendChild(userDiv);
        input.value = '';
        output.scrollTop = output.scrollHeight;

        // Send query to server
        try {
            console.log('Fetching /ask');
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `query=${encodeURIComponent(query)}`
            });

            console.log('Fetch response:', response.status, response.statusText);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let assistantDiv = null;

            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    console.log('SSE stream complete');
                    break;
                }

                const chunk = decoder.decode(value);
                console.log('Received chunk:', chunk);
                const lines = chunk.split('\n\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            console.log('Parsed data:', data);
                            if (data.error) {
                                const errorDiv = document.createElement('div');
                                errorDiv.className = 'error-message';
                                errorDiv.textContent = `Error: ${data.error}`;
                                output.appendChild(errorDiv);
                            } else if (data.text) {
                                if (!assistantDiv) {
                                    assistantDiv = document.createElement('div');
                                    assistantDiv.className = 'assistant-message';
                                    output.appendChild(assistantDiv);
                                }
                                assistantDiv.textContent = data.text;
                            } else if (data.tool) {
                                const toolDiv = document.createElement('div');
                                toolDiv.className = 'tool-message';
                                toolDiv.innerHTML = window.marked.parse(data.tool);
                                output.appendChild(toolDiv);
                            }
                            output.scrollTop = output.scrollHeight;
                        } catch (err) {
                            console.error('Error parsing SSE data:', err, 'Line:', line);
                            const errorDiv = document.createElement('div');
                            errorDiv.className = 'error-message';
                            errorDiv.textContent = `Client error: Failed to parse response`;
                            output.appendChild(errorDiv);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Fetch error:', error);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = `Error: ${error.message}`;
            output.appendChild(errorDiv);
        }
        output.scrollTop = output.scrollHeight;
    });
});