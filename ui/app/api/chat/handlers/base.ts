import { NextRequest } from 'next/server';

export interface ChatRequest {
    message: string;
    agents: any[];
    agent_instruction: string;
    requestId?: string;
}

export interface ChatHandler {
    handleChat(req: ChatRequest): Promise<Response>;
    canHandle(agentType: string): boolean;
}

// Base error for chat handling
export class ChatError extends Error {
    constructor(message: string, public statusCode: number = 500) {
        super(message);
        this.name = 'ChatError';
    }
}
