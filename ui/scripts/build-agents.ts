const { BedrockAgentClient, ListAgentsCommand, GetAgentCommand } = require("@aws-sdk/client-bedrock-agent");
const fs = require('fs');
const path = require('path');
const dotenv = require("dotenv");
const yaml = require('js-yaml');

dotenv.config();

const REGION = process.env.AWS_REGION || 'us-east-1';
const CONFIG_DIR = path.join(process.cwd(), 'app', 'api', 'agents', 'config');
const AGENTS_CATALOG = path.join(process.cwd(), '..', 'agents_catalog');

type AgentRole = 'supervisor' | 'specialist' | 'standalone' | 'individual';

interface ManifestAgent {
  id: string;
  name: string;
  type: string;
  description?: string;
  entrypoint?: string;
  tags?: string[];
  role?: AgentRole;
  bedrock?: {
    agentName: string;
    override: {
      name: string;
      role: AgentRole;
      icon?: string;
      description?: string;
      tags?: string[];
    };
  };
  agentcore?: {
    override: {
      name: string;
      role: AgentRole;
      icon?: string;
      description?: string;
      tags?: string[];
    };
  };
}

interface ManifestFile {
  agents: ManifestAgent[];
}

interface BedrockAgent {
  agentId?: string;
  agentName?: string;
  updatedAt?: Date;
}

interface AgentConfig {
  id: string;
  name: string;
  description: string;
  agentType: string;
  role: AgentRole;
  image: string;
  tags?: string[];
  createdAt?: string;
  updatedAt?: string;
  originalAgentId?: string;
  bedrock_agentcore?: {
    agent_arn: string;
    agent_id?: string;
  };
}

async function getBedrockAgentDetails(client: any, agentId: string) {
  try {
    const command = new GetAgentCommand({ agentId });
    const response = await client.send(command);
    return {
      description: response.description || '',
      instruction: response.instruction || '',
      foundationModel: response.foundationModel
    };
  } catch (error) {
    console.error(`Error fetching details for agent ${agentId}:`, error);
    return {
      description: '',
      instruction: '',
      foundationModel: ''
    };
  }
}

function findManifestFiles(): string[] {
  const manifestPaths: string[] = [];
  const catalogTypes = ['multi_agent_collaboration', 'standalone_agents'];

  for (const type of catalogTypes) {
    const typePath = path.join(AGENTS_CATALOG, type);
    if (!fs.existsSync(typePath)) {
      console.log(`Directory not found: ${typePath}`);
      continue;
    }

    console.log(`Scanning directory: ${typePath}`);
    const entries: string[] = fs.readdirSync(typePath);
    console.log(`Found entries: ${entries.join(', ')}`);

    // Filter for numbered directories (starts with at least 2 digits followed by dash)
    const numberedDirs: string[] = entries.filter((entry: string) => {
      // Sanitize entry to prevent path traversal
      const sanitizedEntry = entry.replace(/\.\./g, '');
      const isDir = fs.statSync(path.join(typePath, sanitizedEntry)).isDirectory();
      const matchesPattern = /^\d{2,}-/.test(sanitizedEntry);
      console.log(`Entry ${sanitizedEntry}: isDir=${isDir}, matchesPattern=${matchesPattern}`);
      return isDir && matchesPattern;
    });

    // Look for manifest.json in each numbered directory
    for (const dir of numberedDirs) {
      const manifestPath = path.join(typePath, dir, 'manifest.json');
      if (fs.existsSync(manifestPath)) {
        console.log(`Found manifest: ${manifestPath}`);
        manifestPaths.push(manifestPath);
      } else {
        console.log(`No manifest found in: ${dir}`);
      }
    }
  }

  return manifestPaths;
}

function loadAllManifests(): Map<string, ManifestAgent> {
  const manifestPaths = findManifestFiles();
  console.log('Found manifest files:', manifestPaths);

  // Map of agentName to manifest agent
  const agentMap = new Map<string, ManifestAgent>();

  for (const manifestPath of manifestPaths) {
    try {
      const content = fs.readFileSync(manifestPath, 'utf8');
      console.log(`Manifest content from ${manifestPath}:`, content);

      const manifest: ManifestFile = JSON.parse(content);
      console.log(`Parsed manifest agents:`, manifest.agents);

      // Add each agent to the map
      for (const agent of manifest.agents) {
        if (agent.bedrock) {
          // For Bedrock agents, key by Bedrock agent name
          console.log(`Adding manifest override for Bedrock agent ${agent.bedrock.agentName}:`, agent);
          agentMap.set(agent.bedrock.agentName, agent);
        } else if (agent.type === 'agentcore') {
          // For AgentCore agents, key by agent ID
          console.log(`Adding manifest override for AgentCore agent ${agent.id}:`, agent);
          agentMap.set(agent.id, agent);
        }
      }
    } catch (error) {
      console.warn(`Warning: Error loading manifest from ${manifestPath}:`, error);
    }
  }

  return agentMap;
}

function findAgentCoreYamlFiles(): Map<string, any> {
  const yamlMap = new Map<string, any>();
  const catalogTypes = ['multi_agent_collaboration', 'standalone_agents'];

  for (const type of catalogTypes) {
    const typePath = path.join(AGENTS_CATALOG, type);
    if (!fs.existsSync(typePath)) {
      continue;
    }

    const entries: string[] = fs.readdirSync(typePath);

    // Filter for numbered directories
    const numberedDirs: string[] = entries.filter((entry: string) => {
      // Sanitize entry to prevent path traversal
      const sanitizedEntry = entry.replace(/\.\./g, '');
      const fullPath = path.join(typePath, sanitizedEntry);
      const isDir = fs.statSync(fullPath).isDirectory();
      const matchesPattern = /^\d{2,}-/.test(sanitizedEntry);
      return isDir && matchesPattern;
    });

    // Look for .bedrock_agentcore.yaml in each numbered directory and its subdirectories
    for (const dir of numberedDirs) {
      const dirPath = path.join(typePath, dir);

      // First check if the YAML file is directly in the numbered directory
      const directYamlPath = path.join(dirPath, '.bedrock_agentcore.yaml');
      if (fs.existsSync(directYamlPath)) {
        try {
          const content = fs.readFileSync(directYamlPath, 'utf8');
          const yamlConfig = yaml.load(content);
          if (yamlConfig) {
            console.log(`Found AgentCore YAML directly in directory: ${directYamlPath}`);

            // If there's a default_agent field, use that as the key
            if (yamlConfig.default_agent) {
              yamlMap.set(yamlConfig.default_agent, yamlConfig);
            }

            // Also add entries for each agent in the agents field
            if (yamlConfig.agents) {
              for (const [agentId, agentConfig] of Object.entries(yamlConfig.agents)) {
                yamlMap.set(agentId, {
                  ...yamlConfig,
                  current_agent: agentConfig
                });
              }
            }
          }
        } catch (error) {
          console.warn(`Warning: Error parsing YAML file ${directYamlPath}:`, error);
        }
      }

      // Then check subdirectories
      try {
        const agentDirs = fs.readdirSync(dirPath).filter((entry: string) => {
          // Sanitize entry to prevent path traversal
          const sanitizedEntry = entry.replace(/\.\./g, '');
          return fs.statSync(path.join(dirPath, sanitizedEntry)).isDirectory();
        });

        for (const agentDir of agentDirs) {
          // Sanitize agentDir to prevent path traversal
          const sanitizedAgentDir = agentDir.replace(/\.\./g, '');
          const yamlPath = path.join(dirPath, sanitizedAgentDir, '.bedrock_agentcore.yaml');
          if (fs.existsSync(yamlPath)) {
            try {
              const content = fs.readFileSync(yamlPath, 'utf8');
              const yamlConfig = yaml.load(content);
              if (yamlConfig) {
                console.log(`Found AgentCore YAML in subdirectory: ${yamlPath}`);

                // If there's a default_agent field, use that as the key
                if (yamlConfig.default_agent) {
                  yamlMap.set(yamlConfig.default_agent, yamlConfig);
                }

                // Also add entries for each agent in the agents field
                if (yamlConfig.agents) {
                  for (const [agentId, agentConfig] of Object.entries(yamlConfig.agents)) {
                    yamlMap.set(agentId, {
                      ...yamlConfig,
                      current_agent: agentConfig
                    });
                  }
                }

                // Also map by directory name
                yamlMap.set(agentDir, yamlConfig);
              }
            } catch (error) {
              console.warn(`Warning: Error parsing YAML file ${yamlPath}:`, error);
            }
          }
        }
      } catch (error) {
        console.warn(`Warning: Error reading subdirectories in ${dirPath}:`, error);
      }
    }
  }

  return yamlMap;
}

function createAgentCoreConfigs(manifestAgents: Map<string, ManifestAgent>): AgentConfig[] {
  const yamlMap = findAgentCoreYamlFiles();
  console.log('Found AgentCore YAML configurations:', Array.from(yamlMap.keys()));

  const agentCoreConfigs: AgentConfig[] = [];
  const processedIds = new Set<string>();

  // Process each manifest agent
  for (const [id, agent] of manifestAgents.entries()) {
    if (agent.type === 'agentcore') {
      console.log(`Processing AgentCore agent from manifest: ${agent.id}`);

      // Try to find YAML config for this agent
      let yamlConfig = yamlMap.get(agent.id);

      if (!yamlConfig) {
        // If not found by ID, try to find by name or other means
        console.log(`No direct YAML match for agent ID ${agent.id}, trying alternative lookups`);

        // Look for partial matches in keys
        for (const [key, value] of yamlMap.entries()) {
          if (key.includes(agent.id) || agent.id.includes(key)) {
            console.log(`Found partial match: ${key} for agent ${agent.id}`);
            yamlConfig = value;
            break;
          }
        }
      }

      // Create config
      const config: AgentConfig = {
        id: agent.id,
        name: agent.name,
        description: agent.description || '',
        agentType: 'agentcore',
        role: agent.agentcore?.override?.role || agent.role || 'standalone',
        image: '',
        tags: agent.tags || [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      // Add bedrock_agentcore if we found a YAML config
      if (yamlConfig) {
        // Try to get agent_arn from different possible locations in the YAML
        let agentArn: string | undefined;
        let agentId: string | undefined;

        // Check in agents.<agent_id>.bedrock_agentcore
        if (yamlConfig.agents && yamlConfig.agents[agent.id] && yamlConfig.agents[agent.id].bedrock_agentcore) {
          agentArn = yamlConfig.agents[agent.id].bedrock_agentcore.agent_arn;
          agentId = yamlConfig.agents[agent.id].bedrock_agentcore.agent_id;
        }
        // Check in current_agent.bedrock_agentcore
        else if (yamlConfig.current_agent && yamlConfig.current_agent.bedrock_agentcore) {
          agentArn = yamlConfig.current_agent.bedrock_agentcore.agent_arn;
          agentId = yamlConfig.current_agent.bedrock_agentcore.agent_id;
        }
        // Check in bedrock_agentcore
        else if (yamlConfig.bedrock_agentcore) {
          agentArn = yamlConfig.bedrock_agentcore.agent_arn;
          agentId = yamlConfig.bedrock_agentcore.agent_id;
        }

        if (agentArn) {
          config.bedrock_agentcore = {
            agent_arn: agentArn
          };

          if (agentId) {
            config.bedrock_agentcore.agent_id = agentId;
          }

          console.log(`Added agent_arn to config for ${agent.id}: ${agentArn}`);
        } else {
          console.warn(`Warning: Could not find agent_arn in YAML config for ${agent.id}`);
        }
      } else {
        console.warn(`Warning: No YAML config found for AgentCore agent ${agent.id}`);
      }

      agentCoreConfigs.push(config);
      processedIds.add(agent.id);
    }
  }

  // Process any YAML configs that don't have a corresponding manifest entry
  for (const [key, yamlConfig] of yamlMap.entries()) {
    // Skip if we've already processed this ID
    if (processedIds.has(key)) {
      continue;
    }

    // Skip if this doesn't look like an agent ID
    if (key.includes('/') || key.includes('\\')) {
      continue;
    }

    console.log(`Processing AgentCore agent from YAML only: ${key}`);

    // Try to get agent_arn from different possible locations in the YAML
    let agentArn: string | undefined;
    let agentId: string | undefined;

    // Check in agents.<agent_id>.bedrock_agentcore
    if (yamlConfig.agents && yamlConfig.agents[key] && yamlConfig.agents[key].bedrock_agentcore) {
      agentArn = yamlConfig.agents[key].bedrock_agentcore.agent_arn;
      agentId = yamlConfig.agents[key].bedrock_agentcore.agent_id;
    }
    // Check in current_agent.bedrock_agentcore
    else if (yamlConfig.current_agent && yamlConfig.current_agent.bedrock_agentcore) {
      agentArn = yamlConfig.current_agent.bedrock_agentcore.agent_arn;
      agentId = yamlConfig.current_agent.bedrock_agentcore.agent_id;
    }
    // Check in bedrock_agentcore
    else if (yamlConfig.bedrock_agentcore) {
      agentArn = yamlConfig.bedrock_agentcore.agent_arn;
      agentId = yamlConfig.bedrock_agentcore.agent_id;
    }

    if (agentArn) {
      const config: AgentConfig = {
        id: key,
        name: yamlConfig.agents?.[key]?.name || key,
        description: '',
        agentType: 'agentcore',
        role: 'standalone',
        image: '',
        tags: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        bedrock_agentcore: {
          agent_arn: agentArn
        }
      };

      if (agentId) {
        config.bedrock_agentcore!.agent_id = agentId;
      }

      agentCoreConfigs.push(config);
      processedIds.add(key);
    }
  }

  return agentCoreConfigs;
}

async function main() {
  try {
    // Clear the config directory first
    if (fs.existsSync(CONFIG_DIR)) {
      console.log('Clearing existing config directory');
      fs.rmSync(CONFIG_DIR, { recursive: true });
    }
    fs.mkdirSync(CONFIG_DIR, { recursive: true });

    // Initialize Bedrock client
    const client = new BedrockAgentClient({ region: REGION });

    // Load all manifests from agents_catalog
    const manifestAgents = loadAllManifests();
    console.log(`Loaded ${manifestAgents.size} agent manifests`);

    // Load all agents from Bedrock
    const bedrockAgents = await loadBedrockAgents();
    console.log(`Loaded ${bedrockAgents.length} Bedrock agents:`,
      bedrockAgents.map((a: BedrockAgent) => ({ name: a.agentName, id: a.agentId })));

    // Process Bedrock agents
    const processedIds = new Set(); // Track processed agent IDs

    for (const agent of bedrockAgents) {
      if (processedIds.has(agent.agentId)) {
        console.log(`Skipping duplicate agent: ${agent.agentName}`);
        continue;
      }

      const manifestAgent = manifestAgents.get(agent.agentName || '');

      // Only process if there's a manifest entry for this Bedrock agent
      if (!manifestAgent || !manifestAgent.bedrock) {
        console.log(`Skipping Bedrock agent ${agent.agentName} - no manifest entry found`);
        continue;
      }

      console.log(`Processing agent ${agent.agentName}, found manifest:`, manifestAgent);

      // Get Bedrock agent details
      const bedrockDetails = await getBedrockAgentDetails(client, agent.agentId || '');

      // Agent has a manifest override
      const config: AgentConfig = {
        id: manifestAgent.id,
        name: manifestAgent.bedrock.override.name,
        description: manifestAgent.bedrock.override.description || manifestAgent.description || bedrockDetails.description,
        agentType: 'bedrock',
        role: manifestAgent.bedrock.override.role || manifestAgent.role || 'individual',
        image: '',
        tags: manifestAgent.bedrock.override.tags || manifestAgent.tags || [],
        createdAt: agent.updatedAt?.toISOString(),
        updatedAt: agent.updatedAt?.toISOString(),
        originalAgentId: agent.agentId // Store original Bedrock agent ID
      };
      console.log(`Writing config for agent with override:`, config);
      writeAgentConfig(config);

      processedIds.add(agent.agentId);
    }

    // Process AgentCore agents
    const agentCoreConfigs = createAgentCoreConfigs(manifestAgents);
    for (const config of agentCoreConfigs) {
      // Only write if we haven't already processed this ID
      if (!processedIds.has(config.id)) {
        writeAgentConfig(config);
        processedIds.add(config.id);
      }
    }

    console.log('Agent configuration files generated successfully');
  } catch (error) {
    console.error('Error processing agents:', error);
    process.exit(1);
  }
}

async function loadBedrockAgents(): Promise<BedrockAgent[]> {
  try {
    const client = new BedrockAgentClient({ region: REGION });
    const command = new ListAgentsCommand({ maxResults: 100 });
    const response = await client.send(command);
    return response.agentSummaries || [];
  } catch (error) {
    console.error('Error loading Bedrock agents:', error);
    return [];
  }
}

function writeAgentConfig(config: AgentConfig) {
  // Sanitize config.id to prevent path traversal
  const sanitizedId = config.id.replace(/[^a-zA-Z0-9_-]/g, '_');
  const filePath = path.join(CONFIG_DIR, `${sanitizedId}.json`);
  const content = JSON.stringify(config, null, 2);
  fs.writeFileSync(filePath, content);
  console.log(`Generated config for agent: ${config.name} (type: ${config.agentType}, role: ${config.role})`);
  console.log(`Config content:`, content);
}

main();
