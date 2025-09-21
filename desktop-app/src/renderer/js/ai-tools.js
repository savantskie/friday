// Friday AI Tools Monitor

class AIToolsManager {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('🤖 AI Tools manager initialized');
    }
    
    async loadAIToolsView() {
        const toolsView = document.getElementById('tools-view');
        if (!toolsView) {
            console.error('🔧 AI Tools view element not found');
            return;
        }
        
        console.log('🤖 Loading AI Tools view...');
        
        // Check Friday system status
        let systemHealth = null;
        let embeddingConfig = null;
        
        try {
            systemHealth = await window.fridayAPI?.friday.getSystemHealth();
            embeddingConfig = await window.fridayAPI?.friday.getEmbeddingConfig();
            console.log('🤖 Friday API data loaded:', { systemHealth, embeddingConfig });
        } catch (error) {
            console.error('🔧 Error loading Friday API data:', error);
        }
        
        toolsView.innerHTML = `
            <div class="view-header">
                <h1>Friday AI Tools</h1>
                <p>Monitor Nate's Friday Memory System and MCP Server tools</p>
            </div>
            
            <div class="tools-overview">
                <div class="tools-section">
                    <h3>Friday Memory System Tools</h3>
                    <div class="tools-grid">
                        <div class="tool-card">
                            <h4>Memory Management</h4>
                            <p>Core memory storage and retrieval system</p>
                            <div class="tool-status">
                                <span class="status-dot ${systemHealth?.status === 'accessible' ? 'status-running' : 'status-error'}"></span>
                                ${systemHealth?.status === 'accessible' ? 'Available' : 'Not accessible'}
                            </div>
                        </div>
                        
                        <div class="tool-card">
                            <h4>Embedding System</h4>
                            <p>Text embeddings for semantic search</p>
                            <div class="tool-status">
                                <span class="status-dot status-warning"></span>
                                Config: Ollama (${this.getEmbeddingModelStatus(embeddingConfig)})
                            </div>
                        </div>
                        
                        <div class="tool-card">
                            <h4>Weather Integration</h4>
                            <p>Open-Meteo weather data for Motley, MN</p>
                            <div class="tool-status">
                                <span class="status-dot status-running"></span>
                                Integrated
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="tools-section">
                    <h3>MCP Server Tools</h3>
                    <div class="tools-grid">
                        <div class="tool-card">
                            <h4>Memory Search</h4>
                            <p>Semantic search across conversation history</p>
                            <div class="tool-status">
                                <span class="status-dot status-running"></span>
                                Available via MCP
                            </div>
                        </div>
                        
                        <div class="tool-card">
                            <h4>Reminder System</h4>
                            <p>Create and manage reminders and appointments</p>
                            <div class="tool-status">
                                <span class="status-dot status-running"></span>
                                Available via MCP
                            </div>
                        </div>
                        
                        <div class="tool-card">
                            <h4>System Health</h4>
                            <p>Database statistics and system monitoring</p>
                            <div class="tool-status">
                                <span class="status-dot status-running"></span>
                                Available via MCP
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="tools-section">
                    <h3>Integration Status</h3>
                    <div class="integration-status">
                        <div class="status-item">
                            <strong>VS Code:</strong> MCP server can be integrated via MCP extension
                        </div>
                        <div class="status-item">
                            <strong>LM Studio:</strong> MCP server can be configured in settings
                        </div>
                        <div class="status-item">
                            <strong>OpenWebUI:</strong> MCP server runs automatically with OpenWebUI launch
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    getEmbeddingModelStatus(embeddingConfig) {
        try {
            if (embeddingConfig?.primary?.model) {
                return embeddingConfig.primary.model;
            }
            return 'Unknown';
        } catch (error) {
            return 'Error loading config';
        }
    }
}

// Initialize when needed
window.AIToolsManager = AIToolsManager;
