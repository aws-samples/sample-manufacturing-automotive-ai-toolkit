import { NextResponse } from 'next/server';
import { BedrockAgentClient, ListAgentsCommand, GetAgentCommand, ListAgentCollaboratorsCommand, ListAgentVersionsCommand } from "@aws-sdk/client-bedrock-agent";
import fs from 'fs';
import path from 'path';
import dotenv from "dotenv";
dotenv.config();

const REGION: string = process.env.AWS_REGION || 'us-west-2';
const CONFIG_DIR = path.join(process.cwd(), 'app', 'api', 'agents', 'config');

const client = new BedrockAgentClient({ 
  region: REGION
});

function sanitizeCollaboratorName(name: string): string {
    let sanitized = name.toLowerCase().replace(/\s+/g, '_');
    sanitized = sanitized.replace(/[^a-z0-9_-]/g, '');
    if (!/^[a-z0-9]/.test(sanitized)) {
        sanitized = 'agent_' + sanitized;
    }
    return sanitized;
}

async function getLatestAgentVersionByUpdatedTimeStamp(agentId: string) {
    try {
      const command = new ListAgentVersionsCommand({agentId: agentId, maxResults: 10 });
      const response = await client.send(command);
      if (response.agentVersionSummaries && response.agentVersionSummaries.length > 0) {
        const sortedVersions = response.agentVersionSummaries.sort((a, b) => {
          if (a.updatedAt && b.updatedAt) {
            return b.updatedAt.getTime() - a.updatedAt.getTime();
          }
          return 0;
        });
        return sortedVersions[0].agentVersion;
      }
      else {
        console.log("No agent versions found for agentId:", agentId);
        return null
      }
    } catch (error) {
      console.error("Error fetching agents:", error);
      return null;
    }
}

async function listAgents() {
  try {
    const command = new ListAgentsCommand({ maxResults: 100 });
    const response = await client.send(command);
    console.log("Fetched Bedrock Agents count:", response.agentSummaries?.length);
    return response.agentSummaries || [];
  } catch (error) {
    console.error("Error fetching Bedrock agents:", error);
    return [];
  }
}

function findConfigFile(agentId: string, agentName: string): string | null {
    if (!fs.existsSync(CONFIG_DIR)) {
        return null;
    }
    
    const files = fs.readdirSync(CONFIG_DIR);

    // Look through all config files to find one with matching originalAgentId
    for (const file of files) {
        try {
            const filePath = path.join(CONFIG_DIR, file);
            const content = fs.readFileSync(filePath, 'utf8');
            const config = JSON.parse(content);
            
            // Check if this config was created from our Bedrock agent
            if (config.originalAgentId === agentId) {
                return filePath;
            }
        } catch (error) {
            continue;
        }
    }

    return null;
}

function getAgentConfig(agentId: string, agentName: string) {
    try {
        const configPath = findConfigFile(agentId, agentName);
        if (configPath) {
            const fileContent = fs.readFileSync(configPath, 'utf8');
            console.log(`Config content for ${agentId} (${agentName}):`, fileContent);
            return JSON.parse(fileContent);
        }
    } catch (error) {
        console.error(`Error reading config for agent ${agentId}:`, error);
    }
    return null;
}

function loadAgentCoreAgents(): any[] {
    try {
        const files = fs.readdirSync(CONFIG_DIR);
        const agents = [];

        for (const file of files) {
            try {
                const filePath = path.join(CONFIG_DIR, file);
                const content = fs.readFileSync(filePath, 'utf8');
                const agent = JSON.parse(content);

                // Only include AgentCore agents
                if (agent.agentType?.toLowerCase() === 'agentcore') {
                    console.log(`Found AgentCore agent: ${agent.name}`);
                    agents.push({
                        id: agent.id,
                        name: agent.name,
                        collaboratorName: sanitizeCollaboratorName(agent.name),
                        description: agent.description || "No description available.",
                        agentType: agent.agentType,
                        role: agent.role || 'standalone',
                        image: agent.image || "/images/default_agent_icon.png",
                        project: agent.project || 'Standalone Agents',
                        tags: agent.tags || [],
                        createdAt: agent.createdAt || new Date().toISOString(),
                        updatedAt: agent.updatedAt || new Date().toISOString(),
                        category: "MA3T",
                        agentStatus: "READY",
                        bedrock_agentcore: agent.bedrock_agentcore
                    });
                }
            } catch (error) {
                console.error(`Error processing file ${file}:`, error);
            }
        }

        return agents;
    } catch (error) {
        console.error("Error loading AgentCore agents:", error);
        return [];
    }
}

async function getAgentDetails(agentId: string) {
    try {
        console.log(`Getting details for agent: ${agentId}`);
        const command = new GetAgentCommand({ agentId });
        const response = await client.send(command);
        
        if (!response.agent || !response.agent.agentArn) {
          console.error('No agent data received for ', agentId);
          return null;
        }

        const config = getAgentConfig(agentId, response.agent.agentName || '');
        console.log(`Config retrieved for ${agentId} (${response.agent.agentName}):`, config);
        
        const collaborators = ['SUPERVISOR', 'SUPERVISOR_ROUTER'].includes(response.agent.agentCollaboration || '')
            ? await getAgentCollaboratorDetails(response.agent.agentId || '')
            : null;

        const displayName = config?.name || response.agent.agentName;
        const tags = config?.tags || [];

        const agentDetails = {
            id: response.agent.agentId,
            name: displayName,
            collaboratorName: sanitizeCollaboratorName(displayName),
            description: config?.description || response.agent.description || "No description available.",
            version: response.agent.agentVersion,
            agentType: 'bedrock',  // Explicitly set type for Bedrock agents
            foundationModel: response.agent.foundationModel || "N/A",
            orchestrationType: response.agent.orchestrationType || "Default",
            createdAt: config?.createdAt || (response.agent.createdAt ? response.agent.createdAt.toISOString() : "N/A"),
            updatedAt: config?.updatedAt || (response.agent.updatedAt ? response.agent.updatedAt.toISOString() : "N/A"),
            tags: tags,
            image: config?.image || "/images/default_agent_icon.png",
            category: "MA3T",
            agentCollaboration: response.agent.agentCollaboration || "N/A",
            agentResourceRoleArn: response.agent.agentResourceRoleArn || "N/A",
            agentStatus: response.agent.agentStatus,
            instruction: response.agent.instruction || "N/A",
            promptOverrideConfiguration: response.agent.promptOverrideConfiguration || {},
            collaborators: collaborators?.agentCollaboratorNames ?? null
        };

        console.log(`Final agent details for ${agentId}:`, agentDetails);
        return agentDetails;
    } catch (error) {
      console.error(`Error fetching details for agent ${agentId}:`, error);
      return null;
    }
}

async function getAgentCollaboratorDetails(agentId: string) {
  const latestAgentVersion = await getLatestAgentVersionByUpdatedTimeStamp(agentId);
  if (!latestAgentVersion) {
    console.error('No agent version data received');
    return null;
  }

  try {
    const command = new ListAgentCollaboratorsCommand({ agentId: agentId, agentVersion: latestAgentVersion });
    const response = await client.send(command);
    if (!response.agentCollaboratorSummaries || response.agentCollaboratorSummaries.length == 0) {
      console.error('No agent data received');
      return null;
    }
    return {
      agentCollaboratorNames: response.agentCollaboratorSummaries.map(agent => 
        sanitizeCollaboratorName(agent.collaboratorName || '')
      ).filter(name => name.length > 0)
    };
  } catch (error) {
    console.error(`Error fetching details for agent ${agentId}:`, error);
    return null;
  }
}

export async function GET() {
    try {
      console.log('Starting GET request handler');
      
      // Get Bedrock agents
      const bedrockAgents = await listAgents();
      console.log('Retrieved Bedrock agents list, fetching details...');
      
      const detailedBedrockAgents = await Promise.all(
        bedrockAgents.map(async (agent) => {
          if (!agent.agentId) {
            return null;
          }
          
          // Only process agents that have a config file (manifest entry)
          const configPath = findConfigFile(agent.agentId, agent.agentName || '');
          if (!configPath) {
            console.log(`Skipping agent ${agent.agentName} - no config file found`);
            return null;
          }
          
          return getAgentDetails(agent.agentId)
        })
      );

      // Get AgentCore agents
      console.log('Loading AgentCore agents...');
      const agentCoreAgents = loadAgentCoreAgents();
      console.log('Loaded AgentCore agents:', agentCoreAgents);

      // Combine both types of agents
      const validAgents = [
        ...detailedBedrockAgents.filter(agent => agent !== null),
        ...agentCoreAgents
      ];

      console.log('Final combined agents list:', validAgents);
      return NextResponse.json(validAgents);
    } catch (error) {
      console.error("Error fetching agents:", error);
      return NextResponse.json({ error: "Failed to fetch agents" }, { status: 500 });
    }
}
