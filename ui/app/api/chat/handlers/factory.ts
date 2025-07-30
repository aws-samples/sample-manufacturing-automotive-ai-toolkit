import { ChatHandler, ChatError } from './base';
import { BedrockChatHandler } from './bedrock';

export class ChatHandlerFactory {
    private static handlers: ChatHandler[] = [
        new BedrockChatHandler(),
        // Add new handlers here as they are implemented
    ];

    static getHandler(agentType: string | undefined): ChatHandler {
        if (!agentType) {
            throw new ChatError('Agent type is required', 400);
        }

        const handler = this.handlers.find(h => h.canHandle(agentType));
        if (!handler) {
            throw new ChatError(`No chat handler found for agent type: ${agentType}`, 400);
        }
        return handler;
    }

    static validateAgentTypes(agents: any[]): { isValid: boolean; agentType: string | undefined } {
        // Check if we have any agents
        if (!agents || agents.length === 0) {
            return { isValid: false, agentType: undefined };
        }
        
        // Get the first agent's type (checking both type and agentType fields)
        const firstAgent = agents[0];
        const firstType = firstAgent?.agentType || firstAgent?.type;
        
        if (!firstType) {
            console.log('No type found for first agent:', firstAgent);
            return { isValid: false, agentType: undefined };
        }

        // Check if all agents have the same type (checking both fields)
        const allSameType = agents.every(agent => {
            const agentType = agent?.agentType || agent?.type;
            return agentType && agentType.toLowerCase() === firstType.toLowerCase();
        });

        return {
            isValid: allSameType,
            agentType: firstType
        };
    }
}
