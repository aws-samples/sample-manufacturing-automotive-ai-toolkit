import {
    BedrockAgentRuntimeClient,
    InvokeInlineAgentCommand
} from '@aws-sdk/client-bedrock-agent-runtime';
import {
    BedrockAgentClient,
    ListAgentAliasesCommand,
    GetAgentAliasCommand
} from '@aws-sdk/client-bedrock-agent';
import { ChatHandler, ChatRequest, ChatError } from './base';

const REGION: string = process.env.AWS_REGION || 'us-west-2';

export class BedrockChatHandler implements ChatHandler {
    private runtimeClient: BedrockAgentRuntimeClient;
    private controlClient: BedrockAgentClient;
    private encoder: TextEncoder;

    constructor() {
        this.runtimeClient = new BedrockAgentRuntimeClient({ region: REGION });
        this.controlClient = new BedrockAgentClient({ region: REGION });
        this.encoder = new TextEncoder();
    }

    canHandle(agentType: string): boolean {
        return agentType?.toLowerCase() === 'bedrock';
    }

    private async getAgentAliasArnByName(agentId: string): Promise<string | null> {
        try {
            const listCommand = new ListAgentAliasesCommand({ agentId });
            const listResponse = await this.controlClient.send(listCommand);
            const latestAlias = listResponse.agentAliasSummaries?.sort(
                (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)
            )[0];
            if (!latestAlias) return null;

            const getCommand = new GetAgentAliasCommand({
                agentId,
                agentAliasId: latestAlias.agentAliasId
            });
            const getResponse = await this.controlClient.send(getCommand);
            return getResponse.agentAlias?.agentAliasArn || null;
        } catch (error) {
            console.error('Error getting alias ARN:', error);
            throw new ChatError('Failed to get agent alias', 500);
        }
    }

    private extractAndRemoveImageUrls(text: string): [string[], string] {
        const imageUrlRegex = /(https:\/\/[^\s"']+\.(?:png|jpg|jpeg|webp)[^\s"']*)/gi;
        const imageUrls = [...text.matchAll(imageUrlRegex)].map(match => match[1]);
        const cleanedText = text.replace(imageUrlRegex, '').trim();
        return [imageUrls, cleanedText];
    }

    private chunkTextSafely(text: string, size: number = 3000): string[] {
        const chunks = [];
        for (let i = 0; i < text.length; i += size) {
            let chunk = text.slice(i, i + size).trim();
            if (i > 0) chunk = '... ' + chunk;
            if (i + size < text.length) chunk += ' ...';
            chunks.push(chunk);
        }
        return chunks;
    }

    async handleChat(req: ChatRequest): Promise<Response> {
        const sessionId = req.requestId || `session-${Date.now()}`;
        const log = (msg: string, ...args: any[]) => {
            console.log(`[${sessionId}] ${msg}`, ...args);
        };

        try {
            const foundationModel = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0';

            log('Resolving agent aliases...');
            const collaboratorConfigurations = await Promise.all(
                req.agents.map(async (agent) => {
                    const agentAliasArn = await this.getAgentAliasArnByName(agent.id);
                    log(`Resolved agent "${agent.name}" to ARN`, agentAliasArn);
                    return {
                        collaboratorName: agent.collaboratorName || agent.id,
                        collaboratorInstruction: req.agent_instruction,
                        agentAliasArn,
                        relayConversationHistory: 'TO_COLLABORATOR'
                    };
                })
            );

            const requestParams = {
                foundationModel,
                instruction: req.agent_instruction,
                sessionId,
                endSession: false,
                enableTrace: true,
                agentCollaboration: 'SUPERVISOR_ROUTER',
                inputText: req.message,
                collaboratorConfigurations,
                inlineSessionState: {
                    promptSessionAttributes: {
                        today: new Date().toISOString().split('T')[0],
                    },
                },
            };

            log('Invoking agent collaboration', requestParams);
            const command = new InvokeInlineAgentCommand(requestParams);
            const result = await this.runtimeClient.send(command);
            log('Agent invocation started');

            // Create encoder instance for the stream
            const encoder = new TextEncoder();

            const stream = new ReadableStream({
                async start(controller) {
                    let finalMessage = '';
                    let imageUrls: string[] = [];
                    let step = 1;
                    let inputTokens = 0;
                    let outputTokens = 0;

                    try {
                        for await (const event of result.completion) {
                            const agentId = event.trace?.agentId || 'unknown-agent';

                            if (event.chunk?.bytes) {
                                const text = new TextDecoder('utf-8').decode(event.chunk.bytes);
                                finalMessage += text;
                                controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'chunk', data: text })}\n\n`));
                            }

                            if (event.trace?.trace?.orchestrationTrace) {
                                const trace = event.trace.trace.orchestrationTrace;

                                // Handle tool input
                                const toolInput = trace.invocationInput?.actionGroupInvocationInput;
                                if (toolInput) {
                                    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                        type: 'tool',
                                        step,
                                        agent: agentId,
                                        function: toolInput.function || '',
                                        apiPath: toolInput.apiPath || '',
                                        executionType: toolInput.executionType || '',
                                        parameters: toolInput.parameters || []
                                    })}\n\n`));
                                    step++;
                                }

                                // Handle rationale
                                if (trace.rationale?.text) {
                                    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                        type: 'rationale',
                                        step,
                                        agent: "Model",
                                        text: trace.rationale.text
                                    })}\n\n`));
                                    step++;
                                }

                                // Handle agent collaboration
                                const agentColab = trace.invocationInput?.agentCollaboratorInvocationInput;
                                if (agentColab) {
                                    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                        type: 'agent-collaborator',
                                        step,
                                        agent: agentColab.agentCollaboratorName,
                                        text: agentColab.input.text
                                    })}\n\n`));
                                    step++;
                                }

                                // Handle tool observation
                                const obsTool = trace.observation?.actionGroupInvocationOutput?.text;
                                if (obsTool) {
                                    const [extractedUrls, cleanedText] = this.extractAndRemoveImageUrls(obsTool);
                                    if (extractedUrls.length > 0) {
                                        imageUrls.push(...extractedUrls);
                                    }

                                    const obs_chunks = this.chunkTextSafely(cleanedText, 4000);
                                    for (const obs_chunk of obs_chunks) {
                                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                            type: 'observation',
                                            step,
                                            agent: agentId,
                                            text: obs_chunk
                                        })}\n\n`));
                                    }
                                    step++;
                                }

                                // Handle knowledge base output
                                const kbOutput = trace.observation?.knowledgeBaseLookupOutput;
                                if (kbOutput?.retrievedReferences?.length) {
                                    for (const reference of kbOutput.retrievedReferences) {
                                        const metadata = reference.metadata || {};
                                        const sourceUri = metadata['x-amz-bedrock-kb-source-uri'] || '';
                                        const contentText = reference.content?.text || '';

                                        if (contentText) {
                                            const combinedText = `${contentText}\n\nReference: ${sourceUri}`;
                                            controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                                type: 'knowledge-base',
                                                step,
                                                agent: agentId,
                                                text: combinedText
                                            })}\n\n`));
                                        }
                                    }
                                    step++;
                                }

                                // Handle final response
                                const finalResp = trace.observation?.finalResponse;
                                if (finalResp?.text) {
                                    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                                        type: 'observation',
                                        step,
                                        agent: agentId,
                                        text: finalResp.text
                                    })}\n\n`));
                                    step++;
                                }

                                // Track usage
                                const usage = trace.modelInvocationOutput?.metadata?.usage;
                                if (usage) {
                                    inputTokens += usage.inputTokens || 0;
                                    outputTokens += usage.outputTokens || 0;
                                }

                                // Handle attachments
                                const attachment = finalResp?.attachments?.[0];
                                if (attachment?.url) {
                                    imageUrls.push(attachment.url);
                                }
                            }
                        }
                    } catch (streamError) {
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                            type: 'error',
                            step,
                            agent: 'Model',
                            text: streamError + ' ' + sessionId || 'An error occurred during streaming.',
                        })}\n\n`));
                        finalMessage = "Sorry! I am having trouble processing your request. Please try again later.";
                    } finally {
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                            type: 'end',
                            finalMessage,
                            images: imageUrls,
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
            log('Error during processing', err);
            throw new ChatError('Failed to process chat request', 500);
        }
    }
}
