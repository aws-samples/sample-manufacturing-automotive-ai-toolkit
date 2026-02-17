"use client";

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

// SVG Icons as components
const PlusIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
  </svg>
);

const ChatIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
  </svg>
);

const XIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const InfoIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const SearchIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

const GitHubIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
  </svg>
);

// Robot icon as default for agents
const RobotIcon = ({ className = "h-12 w-12" }) => (
  <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
    <line x1="8" y1="16" x2="8" y2="16" />
    <line x1="16" y1="16" x2="16" y2="16" />
    <rect x="7" y="13" width="2" height="2" />
    <rect x="15" y="13" width="2" height="2" />
  </svg>
);

export default function Home() {
  const [agents, setAgents] = useState<any[]>([]);
  const [selectedAgents, setSelectedAgents] = useState<any[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hoveredCollaborator, setHoveredCollaborator] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [showTagFilter, setShowTagFilter] = useState(false);
  let previewTimeout = null;

  // Close tag filter dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: any) {
      if (showTagFilter && !event.target.closest('.tag-filter-container')) {
        setShowTagFilter(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showTagFilter]);

  const isSupervisorType = (a: any) => a.agentCollaboration === 'SUPERVISOR' || a.agentCollaboration === 'SUPERVISOR_ROUTER';

  useEffect(() => {
    async function fetchAgents() {
      setIsLoading(true);
      try {
        const res = await fetch('/api/agents');
        const agentData = await res.json();
        setAgents(agentData);
      } catch (err) {
        console.error('Error fetching agents:', err);
      }
      setIsLoading(false);
    }
    fetchAgents();
  }, []);

  const toggleAgentSelection = (agent: any) => {
    setSelectedAgents((prev: any) => {
      const isAlreadySelected = prev.find((a: any) => a.id === agent.id);
      return isAlreadySelected ? [] : [agent];
    });
  };

  const removeAgent = (agentId: string) => {
    setSelectedAgents(prev => prev.filter(a => a.id !== agentId));
  };

  const clearAllAgents = () => {
    setSelectedAgents([]);
  };

  // Create categories from flat agents list
  const categories = [
    {
      id: 'supervisors',
      name: 'Supervisors',
      agents: agents.filter(a => a.agentCollaboration === 'SUPERVISOR' || a.agentCollaboration === 'SUPERVISOR_ROUTER')
    },
    {
      id: 'individuals',
      name: 'Individual Agents',
      agents: agents.filter(a => a.agentCollaboration === 'DISABLED')
    }
  ];

  // Filter agents based on search, category, and tags
  const filteredAgents = agents.filter(agent => {
    const matchesSearch = !searchTerm || 
      agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (agent.description && agent.description.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesCategory = selectedCategory === 'all' || 
      (selectedCategory === 'supervisors' && isSupervisorType(agent)) ||
      (selectedCategory === 'individuals' && agent.agentCollaboration === 'DISABLED');
    
    const matchesTags = selectedTags.length === 0 || 
      (agent.tags && selectedTags.every(tag => agent.tags.includes(tag)));
    
    return matchesSearch && matchesCategory && matchesTags;
  });

  return (
    <div className="min-h-screen bg-gray-50 pb-16">
      {/* Simplified Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 sticky top-0 z-10 shadow-sm">
        {/* Top row: Title */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">MA3T Agent Playground</h1>
          </div>
          <a 
            href="https://github.com/aws-samples/sample-manufacturing-automotive-ai-toolkit"
            target="_blank" 
            rel="noopener noreferrer"
            className="text-gray-600 hover:text-gray-900 transition-colors"
            title="View on GitHub"
          >
            <GitHubIcon />
          </a>
        </div>
        
        {/* Separation line */}
        <div className="border-t border-gray-200 my-3"></div>

        {/* Bottom row: Search and filters */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <SearchIcon />
              </div>
              <input
                type="text"
                placeholder="Search agents..."
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <div className="relative tag-filter-container">
              <button
                onClick={() => setShowTagFilter(!showTagFilter)}
                className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                <span className="text-sm text-gray-600">Filter by tags</span>
                {selectedTags.length > 0 && (
                  <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
                    {selectedTags.length}
                  </span>
                )}
              </button>
              
              {showTagFilter && (
                <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium text-gray-900">Filter by tags</h3>
                      {selectedTags.length > 0 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTags([]);
                          }}
                          className="text-xs text-gray-500 hover:text-gray-700"
                        >
                          Clear all
                        </button>
                      )}
                    </div>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {Array.from(new Set(agents.flatMap(agent => agent.tags || []))).sort().map(tag => (
                        <label key={tag} className="flex items-center">
                          <input
                            type="checkbox"
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            checked={selectedTags.includes(tag)}
                            onChange={(e) => {
                              e.stopPropagation();
                              const newTags = selectedTags.includes(tag)
                                ? selectedTags.filter(t => t !== tag)
                                : [...selectedTags, tag];
                              console.log('Setting selected tags to:', newTags);
                              setSelectedTags(newTags);
                            }}
                          />
                          <span className="ml-2 text-sm text-gray-600">{tag}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <div className="flex space-x-2 overflow-x-auto">
              <button
                onClick={() => setSelectedCategory('all')}
                className={`px-3 py-1 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  selectedCategory === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setSelectedCategory('supervisors')}
                className={`px-3 py-1 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  selectedCategory === 'supervisors'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Supervisors
              </button>
              <button
                onClick={() => setSelectedCategory('individuals')}
                className={`px-3 py-1 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                  selectedCategory === 'individuals'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Individual Agents
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* Bottom bar with selected agents and Start Chat button */}
      {selectedAgents.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 py-3 px-4 shadow-lg z-10">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center overflow-x-auto">
              <span className="text-sm font-medium text-gray-700 mr-2 whitespace-nowrap">
                Selected Agent:
              </span>
              <div className="flex flex-wrap gap-1 mr-2">
                {selectedAgents.map(agent => (
                  <div key={agent.id} className="flex items-center px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full text-xs whitespace-nowrap">
                    <span className="truncate max-w-[200px]">{agent.name}</span>
                    <button
                      onClick={() => removeAgent(agent.id)}
                      className="ml-1 hover:bg-blue-200 rounded-full p-0.5"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
            <a
              href="/chat"
              onClick={() => {
                localStorage.setItem('selectedAgents', JSON.stringify(selectedAgents));
              }}
              className="flex items-center space-x-2 px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors ml-3 whitespace-nowrap"
            >
              <ChatIcon />
              <span>Start Chat</span>
            </a>
          </div>
        </div>
      )}

      {/* Agents Grid */}
      <div className="p-6">
        {isLoading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredAgents.length > 0 ? (
          <div className="space-y-6">
            {/* Group agents by project */}
            {Object.entries(
              filteredAgents.reduce((groups: Record<string, any[]>, agent) => {
                const project = agent.project || 'Standalone Agents';
                if (!groups[project]) groups[project] = [];
                groups[project].push(agent);
                return groups;
              }, {})
            ).map(([projectName, projectAgents]) => (
              <div key={projectName} className="border border-gray-200 rounded-lg overflow-hidden">
                <details className="group" open>
                  <summary className="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 cursor-pointer border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">{projectName}</h3>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-500">{projectAgents.length} agent{projectAgents.length !== 1 ? 's' : ''}</span>
                      <svg className="w-5 h-5 text-gray-400 group-open:rotate-90 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </summary>
                  <div className="p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                      {projectAgents.map(agent => {
              const isSelected = selectedAgents.some(a => a.id === agent.id);
              const isSupervisor = isSupervisorType(agent);
              
              return (
                <div
                  key={agent.id}
                  className={`relative p-4 rounded-lg border transition-all hover:shadow cursor-pointer ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                  onClick={() => toggleAgentSelection(agent)}
                >
                  {/* Info button in top right with background */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation(); // Prevent triggering the parent div's onClick
                      setSelectedAgent(agent);
                    }}
                    className="absolute top-2 right-2 p-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-blue-600 rounded-full transition-colors"
                    title="View Details"
                  >
                    <InfoIcon />
                  </button>
                  
                  <div className="flex items-start mb-3">
                    <div className="flex items-center gap-3">
                      {agent.image ? (
                        <img 
                          src={agent.image} 
                          alt={agent.name} 
                          className="w-12 h-12 rounded-full border-2 border-gray-200"
                          onError={(e) => {
                            e.currentTarget.style.display = 'none';
                            const nextSibling = e.currentTarget.nextSibling as HTMLElement;
                            if (nextSibling) {
                              nextSibling.style.display = 'flex';
                            }
                          }}
                        />
                      ) : (
                        <div className="w-12 h-12 rounded-full border-2 border-gray-200 flex items-center justify-center bg-gray-100 text-gray-600">
                          <RobotIcon className="w-8 h-8" />
                        </div>
                      )}
                      <div className="hidden w-12 h-12 rounded-full border-2 border-gray-200 items-center justify-center bg-gray-100 text-gray-600">
                        <RobotIcon className="w-8 h-8" />
                      </div>
                      <div className="max-w-full">
                        <h3 className="font-medium text-gray-900 break-words line-clamp-2 min-h-[2.5rem]">{agent.name}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          isSupervisor 
                            ? 'bg-purple-100 text-purple-700' 
                            : 'bg-green-100 text-green-700'
                        }`}>
                          {isSupervisor ? 'Supervisor' : 'Individual'}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2 break-words overflow-hidden">{agent.description}</p>
                  
                  {agent.tags && agent.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {agent.tags.slice(0, 3).map((tag: string) => (
                        <span key={tag} className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                      {agent.tags.length > 3 && (
                        <span className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded">
                          +{agent.tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
                    </div>
                  </div>
                </details>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-gray-500">No agents found matching your search criteria.</p>
          </div>
        )}
      </div>

      {/* Agent Detail Modal */}
      {selectedAgent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.2 }}
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">{selectedAgent.name}</h2>
              <button onClick={() => setSelectedAgent(null)} className="p-1 text-gray-400 hover:text-gray-600">
                <XIcon />
              </button>
            </div>
            
            <div className="p-6">
              <div className="flex items-center mb-6">
                {selectedAgent.image ? (
                  <img 
                    src={selectedAgent.image} 
                    alt={selectedAgent.name} 
                    className="w-24 h-24 rounded-full border-4 border-gray-200 mr-4"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      const nextSibling = e.currentTarget.nextSibling as HTMLElement;
                      if (nextSibling) {
                        nextSibling.style.display = 'flex';
                      }
                    }}
                  />
                ) : (
                  <div className="w-24 h-24 rounded-full border-4 border-gray-200 mr-4 flex items-center justify-center bg-gray-100 text-gray-600">
                    <RobotIcon className="w-16 h-16" />
                  </div>
                )}
                <div className="hidden w-24 h-24 rounded-full border-4 border-gray-200 mr-4 items-center justify-center bg-gray-100 text-gray-600">
                  <RobotIcon className="w-16 h-16" />
                </div>
                <div>
                  <p className="text-gray-600 mb-2">{selectedAgent.description}</p>
                  <div className="flex items-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      isSupervisorType(selectedAgent) 
                        ? 'bg-purple-100 text-purple-700' 
                        : 'bg-green-100 text-green-700'
                    }`}>
                      {isSupervisorType(selectedAgent) ? 'Supervisor' : 'Individual'}
                    </span>
                    
                    <button
                      onClick={() => {
                        toggleAgentSelection(selectedAgent);
                      }}
                      className={`ml-3 px-3 py-1 text-sm rounded ${
                        selectedAgents.some(a => a.id === selectedAgent.id)
                          ? 'bg-red-100 text-red-700 hover:bg-red-200'
                          : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                      }`}
                    >
                      {selectedAgents.some(a => a.id === selectedAgent.id) ? 'Deselect' : 'Select'}
                    </button>
                  </div>
                </div>
              </div>
              
              <div className="p-4 bg-gray-100 rounded-lg mb-4">
                <h3 className="font-bold text-md text-gray-800 mb-2">Details</h3>
                <ul className="text-sm text-gray-700 space-y-1">
                  <li><strong>Agent ID:</strong> {selectedAgent.id}</li>
                  <li><strong>ARN:</strong> {selectedAgent.arn}</li>
                  <li><strong>Collaboration:</strong> {selectedAgent.agentCollaboration}</li>
                  <li><strong>Status:</strong> {selectedAgent.agentStatus}</li>
                  <li><strong>Foundation Model:</strong> {selectedAgent.foundationModel}</li>
                  <li><strong>Orchestration Type:</strong> {selectedAgent.orchestrationType}</li>
                  <li><strong>Instruction:</strong> {selectedAgent.instruction}</li>
                  <li><strong>Created At:</strong> {selectedAgent.createdAt}</li>
                  <li><strong>Updated At:</strong> {selectedAgent.updatedAt}</li>
                </ul>
              </div>

              {/* Tags Section */}
              <div className="mb-4">
                <h3 className="font-bold text-md text-gray-800 mb-2">Tags</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedAgent.tags && selectedAgent.tags.length > 0 ? (
                    selectedAgent.tags.map((tag: string) => (
                      <span key={tag} className="bg-blue-100 text-blue-800 text-xs px-3 py-1 rounded-full">
                        {tag}
                      </span>
                    ))
                  ) : (
                    <span className="text-gray-500 text-xs">No tags available</span>
                  )}
                </div>
              </div>

              {/* Collaborators Section */}
              {Array.isArray(selectedAgent.collaborators) && selectedAgent.collaborators.length > 0 && (
                <div className="border-t pt-4">
                  <h3 className="font-bold text-md text-gray-800 mb-3">Collaborators</h3>
                  <div className="space-y-3">
                    {selectedAgent.collaborators.map((collabName: string) => {
                      const collaboratorAgent = agents.find(a => a.name === collabName);
                      if (!collaboratorAgent) return null;

                      return (
                          <div
                          key={collaboratorAgent.id}
                          className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg p-3 hover:shadow-md transition-shadow duration-200"
                        >
                          {collaboratorAgent.image ? (
                            <img
                              src={collaboratorAgent.image}
                              alt={`${collaboratorAgent.name} Icon`}
                              className="w-10 h-10 rounded-full border-2 border-gray-200"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                const nextSibling = e.currentTarget.nextSibling as HTMLElement;
                                if (nextSibling) {
                                  nextSibling.style.display = 'flex';
                                }
                              }}
                            />
                          ) : (
                            <div className="w-10 h-10 rounded-full border-2 border-gray-200 flex items-center justify-center bg-gray-100 text-gray-600">
                              <RobotIcon className="w-7 h-7" />
                            </div>
                          )}
                          <div className="hidden w-10 h-10 rounded-full border-2 border-gray-200 items-center justify-center bg-gray-100 text-gray-600">
                            <RobotIcon className="w-7 h-7" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-gray-900">{collaboratorAgent.name}</div>
                            <div className="text-xs text-gray-600">{collaboratorAgent.description}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setSelectedAgent(null)}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition-colors"
              >
                Close
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
