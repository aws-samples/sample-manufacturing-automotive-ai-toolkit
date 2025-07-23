import { NextResponse } from 'next/server';
import { BedrockAgentClient, ListAgentsCommand, GetAgentCommand, ListAgentCollaboratorsCommand, ListAgentVersionsCommand } from "@aws-sdk/client-bedrock-agent";
import fs from 'fs';
import path from 'path';
import dotenv from "dotenv";
dotenv.config();

const REGION: string = process.env.AWS_REGION
const CONFIG_DIR = path.join(process.cwd(), 'app', 'api', 'agents', 'config');

const client = new BedrockAgentClient({ 
  region: REGION
});

// Map of Bedrock agent names to manifest IDs
const agentNameMap: { [key: string]: string } = {
  'SAM-agent-bookdealerappt': 'sam-book-appointment',
  'SAM-agent-finddealeravailability': 'sam-dealer-availability',
  'SAM-agent-find-nearestdealership': 'sam-nearest-dealership',
  'SAM-agent-orchestrater': 'sam-orchestrator',
  'SAM-agent-parts-availability': 'sam-parts-availability',
  'SAM-agent-analyze_vehiclesymptom': 'sam-vehicle-symptom',
  'SAM-agent-warrantyandrecalls': 'vista-warranty-recall'
};

function sanitizeCollaboratorName(name: string): string {
    // Convert to lowercase, replace spaces with underscores
    let sanitized = name.toLowerCase().replace(/\s+/g, '_');
    // Remove any characters that aren't alphanumeric, underscore, or hyphen
    sanitized = sanitized.replace(/[^a-z0-9_-]/g, '');
    // Ensure it starts with a letter or number
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
    console.log("Fetched Agents count:", response.agentSummaries?.length);
    return response.agentSummaries || [];
  } catch (error) {
    console.error("Error fetching agents:", error);
    return [];
  }
}

function findConfigFile(agentId: string, agentName: string): string | null {
    // First try to find config using the agent name mapping
    if (agentName && agentNameMap[agentName]) {
        const mappedConfigPath = path.join(CONFIG_DIR, `${agentNameMap[agentName]}.json`);
        console.log(`Trying mapped config path for ${agentName}: ${mappedConfigPath}`);
        if (fs.existsSync(mappedConfigPath)) {
            console.log(`Found config file using agent name mapping: ${mappedConfigPath}`);
            return mappedConfigPath;
        }
    }

    // List all available config files
    const files = fs.readdirSync(CONFIG_DIR);
    console.log('Available config files:', files);

    // Try exact match with agent ID
    const exactMatch = files.find(file => file === `${agentId}.json`);
    if (exactMatch) {
        const configPath = path.join(CONFIG_DIR, exactMatch);
        console.log(`Found exact match config file: ${configPath}`);
        return configPath;
    }

    console.log(`No config file found for agent ${agentId} (${agentName})`);
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

async function getAgentDetails(agentId: string) {
    try {
        console.log(`Getting details for agent: ${agentId}`);
        const command = new GetAgentCommand({ agentId });
        const response = await client.send(command);
        
        if (!response.agent || !response.agent.agentArn) {
          console.error('No agent data received for ', agentId);
          return null;
        }

        // Get configuration overrides if they exist
        const config = getAgentConfig(agentId, response.agent.agentName || '');
        console.log(`Config retrieved for ${agentId} (${response.agent.agentName}):`, config);
        
        // Only get collaborator details if agent has collaboration enabled
        const collaborators = ['SUPERVISOR', 'SUPERVISOR_ROUTER'].includes(response.agent.agentCollaboration)
            ? await getAgentCollaboratorDetails(response.agent.agentId)
            : null;

        const displayName = config?.name || response.agent.agentName;
        const tags = config?.tags || [];
        console.log(`Final tags for agent ${agentId}:`, tags);

        const agentDetails = {
            id: response.agent.agentId,
            name: displayName,
            // Add a sanitized name for collaboration
            collaboratorName: sanitizeCollaboratorName(displayName),
            description: config?.description || response.agent.description || "No description available.",
            version: response.agent.agentVersion,
            foundationModel: response.agent.foundationModel || "N/A",
            orchestrationType: response.agent.orchestrationType || "Default",
            createdAt: config?.createdAt || (response.agent.createdAt ? response.agent.createdAt.toISOString() : "N/A"),
            updatedAt: config?.updatedAt || (response.agent.updatedAt ? response.agent.updatedAt.toISOString() : "N/A"),
            tags: tags,
            image: config?.image || "/images/default_agent_icon.png",
            category: "HCLS",
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
      const agents = await listAgents();
      console.log('Retrieved agents list, fetching details...');
      
      const detailedAgents = await Promise.all(
       agents.map(async (agent) => {
          if (!agent.agentId) {
            return null;
          }
          return getAgentDetails(agent.agentId)}));

      const validAgents = detailedAgents.filter(agent => agent !== null);
      console.log('Final agents list:', validAgents);

      return NextResponse.json(validAgents);
    } catch (error) {
      console.error("Error fetching agents:", error);
      return NextResponse.json({ error: "Failed to fetch agents" }, { status: 500 });
    }
}
