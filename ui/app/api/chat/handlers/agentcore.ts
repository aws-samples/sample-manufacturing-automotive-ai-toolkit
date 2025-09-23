import {
    BedrockAgentCoreClient,
    InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";
import { ChatHandler, ChatRequest, ChatError } from './base';

const REGION: string = process.env.AWS_REGION || 'us-west-2';

interface AgentCoreResponse {
    result: {
        role: string;
        content: Array<{
            text: string;
        }>;
    };
    source: any;
    confidence: number;
}

export class AgentCoreChatHandler implements ChatHandler {
    private agentCoreClient: BedrockAgentCoreClient;
    private encoder: TextEncoder;

    constructor() {
        this.agentCoreClient = new BedrockAgentCoreClient({ region: REGION });
        this.encoder = new TextEncoder();
    }

    canHandle(agentType: string): boolean {
        return agentType?.toLowerCase() === 'agentcore';
    }

    private parseAgentCoreChunk(chunk: string): string | null {
        try {
            const response: AgentCoreResponse = JSON.parse(chunk);
            if (response.result?.content?.[0]?.text) {
                return response.result.content[0].text;
            }
            return null;
        } catch (error) {
            console.error('Error parsing AgentCore chunk:', error);
            return null;
        }
    }

    async handleChat(req: ChatRequest): Promise<Response> {
        const sessionId = req.requestId || `session-${Date.now()}`;
        const log = (msg: string, ...args: any[]) => {
            console.log(`[${sessionId}] ${msg}`, ...args);
        };

        try {
            const agent = req.agents[0];
            if (!agent.bedrock_agentcore?.agent_arn) {
                throw new ChatError('Agent ARN is required for AgentCore agents', 400);
            }

            const payload = JSON.stringify({
                prompt: req.message,
                session_id: sessionId,
                prompt_uuid: `prompt-${Date.now()}`,
                user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                last_k_turns: 10,
            });

            const input = {
                agentRuntimeArn: agent.bedrock_agentcore.agent_arn,
                payload,
            };

            log('Invoking AgentCore with input:', input);
            const command = new InvokeAgentRuntimeCommand(input);
            const response = await this.agentCoreClient.send(command);
            log('AgentCore invocation started');

            // Create encoder instance for the stream
            const encoder = new TextEncoder();

            // Create a reference to parseAgentCoreChunk that maintains the correct context
            const parseChunk = this.parseAgentCoreChunk.bind(this);

            const stream = new ReadableStream({
                async start(controller) {
                    let finalMessage = '';
                    let step = 1;

                    try {
                        if (response.response) {
                            const stream = response.response.transformToWebStream();
                            const reader = stream.getReader();
                            const decoder = new TextDecoder();

                            try {
                                while (true) {
                                    const { done, value } = await reader.read();
                                    if (done) break;

                                    const chunk = decoder.decode(value, { stream: true });
                                    log('Chunk received:', chunk);

                                    const text = parseChunk(chunk);
                                    if (text) {
                                        // Send the chunk to the client
                                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                            type: 'chunk',
                                            step,
                                            agent: agent.name,
                                            data: text
                                        })}\n\n`));

                                        finalMessage += text;
                                        step++;
                                    }
                                }
                            } finally {
                                reader.releaseLock();
                            }
                        } else {
                            // Handle non-streaming response
                            const bytes = await (response.response as any)?.transformToByteArray();
                            if (bytes) {
                                const text = new TextDecoder().decode(bytes);
                                const parsedText = parseChunk(text);
                                finalMessage = parsedText || text;
                            }

                            controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                type: 'chunk',
                                step,
                                agent: agent.name,
                                data: finalMessage
                            })}\n\n`));
                        }
                    } catch (streamError) {
                        log('Error during streaming:', streamError);
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                            type: 'error',
                            step,
                            agent: agent.name,
                            text: 'An error occurred during streaming.'
                        })}\n\n`));
                        finalMessage = "Sorry! I am having trouble processing your request. Please try again later.";
                    } finally {
                        // Send the final message
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                            type: 'end',
                            finalMessage,
                            requestId: sessionId
                        })}\n\n`));
                        controller.close();
                    }
                }
            });

            return new Response(stream, {
                headers: {
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache, no-transform',
                    'Connection': 'keep-alive',
                    'Transfer-Encoding': 'chunked'
                }
            });

        } catch (err) {
            log('Error during processing:', err);
            throw new ChatError('Failed to process chat request', 500);
        }
    }
}
