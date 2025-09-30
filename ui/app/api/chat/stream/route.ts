import { NextRequest } from 'next/server';
import { ChatHandlerFactory } from '../handlers/factory';
import { ChatError } from '../handlers/base';

interface NormalizedAgent {
    id: string;
    name: string;
    agentType: string;
    collaboratorName?: string;
    [key: string]: any;  // Allow other properties
}

function normalizeAgent(agent: any): NormalizedAgent {
    return {
        ...agent,
        agentType: agent.agentType || agent.type || 'bedrock',  // Default to 'bedrock' for existing agents
        collaboratorName: agent.collaboratorName || agent.name?.toLowerCase().replace(/\s+/g, '_')
    };
}

export async function POST(req: NextRequest) {
    try {
        const { message, agents: rawAgents, agent_instruction, requestId } = await req.json();
        const sessionId = requestId || `session-${Date.now()}`;

        // Normalize agent data
        const agents = rawAgents.map(normalizeAgent);

        // Log the incoming request for debugging
        console.log('Received chat request:', {
            message,
            agentCount: agents?.length,
            agents: agents?.map((a: any) => ({
                id: a.id,
                name: a.name,
                type: a.agentType,
                collaboratorName: a.collaboratorName
            }))
        });

        // Validate request
        if (!message || !agents || !Array.isArray(agents) || agents.length === 0) {
            throw new ChatError('Invalid request parameters', 400);
        }

        // Validate that all agents are of the same type
        const { isValid, agentType } = ChatHandlerFactory.validateAgentTypes(agents);
        if (!isValid) {
            throw new ChatError('All agents must be of the same valid type', 400);
        }

        // Get the appropriate handler for the agent type
        const handler = ChatHandlerFactory.getHandler(agentType);

        // Process the chat request
        return await handler.handleChat({
            message,
            agents,
            agent_instruction,
            requestId: sessionId
        });

    } catch (error) {
        console.error('Chat error:', error);
        
        if (error instanceof ChatError) {
            return new Response(JSON.stringify({ error: error.message }), {
                status: error.statusCode,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        return new Response(JSON.stringify({ error: 'Internal server error' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}
