/* Dashboard app logic extracted from templates/dashboard.html
   Exposes window.streamingApp for Alpine x-data. */

window.streamingApp = function () {
    return {
        // Navigation state
        activeTab: 'statistics',
        
        // Core state
        isGenerating: false,
        customPrompt: '',
        logConnectionError: false,
        aimlApiConfigured: true, // Will be determined from backend
        
        // Statistics
        stats: {
            totalVideos: 0,
            totalDonations: 0,
            totalAmount: '$0'
        },
        
        // Data collections
        allDonations: [],
        logs: [],
        allVideos: [],
        
        // New fields for features
        systemPrompt: '',
        donationAlertsToken: '',
        thresholdAmount: 1000,
        thresholdCurrency: 'RUB',
        
        // Generation tracking
        generationStatus: { active: false, status: 'idle', progress: 0 },
        lastGenStatus: '',
        notifications: [],
        
        
        // Connection status
        connectionStatus: {
            connected: false,
            configured: false
        },
        
        // Filter state
        showFilterPanel: false,
        selectedFilter: null,
        showIpAddresses: false,
        
        init() {
            this.loadStats();
            this.loadLogs();
            this.loadDonations();
            this.loadAllVideos();
            this.loadSystemPrompt();
            this.loadSettings();
            this.loadAIMLStatus();
            this.loadGenerationStatus();
            
            // Poll for new logs every 3 seconds
            setInterval(() => this.loadLogs(), 3000);
            // Poll for new donations every 3 seconds
            setInterval(() => this.loadDonations(), 3000);
            // Poll for AIML status every 5 seconds
            setInterval(() => this.loadAIMLStatus(), 5000);
            // Poll generation status every 3 seconds
            setInterval(() => this.loadGenerationStatus(), 3000);
        },
        
        async loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                this.stats = data;
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        },
        
        async loadDonations() {
            try {
                const response = await fetch('/api/donations');
                if (response.ok) {
                    const data = await response.json();
                    this.allDonations = data.donations || [];
                }
            } catch (error) {
                console.error('Failed to load donations:', error);
            }
        },
        
        async loadLogs() {
            try {
                const lastTimestamp = this.logs.length > 0 ? this.logs[this.logs.length - 1].timestamp_ms : Date.now() - 3600000;
                const response = await fetch(`/api/logs?since=${lastTimestamp || 0}&show_ip=${this.showIpAddresses}`);
                const data = await response.json();
                
                this.logConnectionError = false;
                
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(log => {
                        this.logs.push({
                            ...log,
                            id: log.id || Date.now() + Math.random()
                        });
                    });
                    
                    // Remove duplicates and keep only recent logs (limit to 1000 entries)
                    const seen = new Set();
                    this.logs = this.logs.filter(log => {
                        if (seen.has(log.timestamp_ms)) {
                            return false;
                        }
                        seen.add(log.timestamp_ms);
                        return true;
                    });
                    
                    if (this.logs.length > 1000) {
                        this.logs = this.logs.slice(-1000);
                    }
                }
            } catch (error) {
                console.error('Failed to load logs:', error);
                this.logConnectionError = true;
            }
        },
        
        async generateCustomVideo() {
            if (!this.customPrompt.trim()) {
                alert('Please enter a custom prompt');
                return;
            }
            
            this.isGenerating = true;
            try {
                const response = await fetch('/api/generate-video', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        custom_prompt: this.customPrompt
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    alert('Video generation started successfully!');
                    this.customPrompt = '';
                    // Refresh gallery after a short delay to allow for video generation
                    setTimeout(() => {
                        this.refreshVideoGallery();
                    }, 2000);
                } else {
                    alert('Error: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            } finally {
                this.isGenerating = false;
            }
        },
        
        
        
        // Console functions
        toggleFilter() {
            this.showFilterPanel = !this.showFilterPanel;
            if (!this.showFilterPanel) {
                this.selectedFilter = null;
            }
        },
        
        toggleIpDisplay() {
            this.showIpAddresses = !this.showIpAddresses;
            this.loadLogs();
        },
        
        selectFilter(signature) {
            this.selectedFilter = signature;
        },
        
        clearFilter() {
            this.selectedFilter = null;
        },
        
        getFilteredLogs() {
            if (!this.selectedFilter) {
                return this.logs;
            }
            return this.logs.filter(log => log.signature === this.selectedFilter);
        },
        
        getUniqueHttpSignatures() {
            const uniqueSignatures = new Map();
            
            this.logs.forEach(log => {
                if (log.type === 'http' && log.signature) {
                    const signature = log.signature;
                    if (uniqueSignatures.has(signature)) {
                        uniqueSignatures.get(signature).count++;
                    } else {
                        uniqueSignatures.set(signature, {
                            signature: signature,
                            method: log.method,
                            path: log.path.split('?')[0],
                            count: 1,
                            hash: this.hashString(signature)
                        });
                    }
                }
            });
            
            return Array.from(uniqueSignatures.values())
                .sort((a, b) => b.count - a.count);
        },
        
        getMethodColor(method) {
            const colors = {
                'GET': 'text-green-400',
                'POST': 'text-blue-400', 
                'PUT': 'text-yellow-400',
                'DELETE': 'text-red-400',
                'PATCH': 'text-purple-400',
                'OPTIONS': 'text-gray-400',
                'HEAD': 'text-cyan-400'
            };
            return colors[method] || 'text-white';
        },
        
        getStatusColor(status) {
            if (status >= 200 && status < 300) return 'text-green-400';
            if (status >= 300 && status < 400) return 'text-yellow-400';  
            if (status >= 400 && status < 500) return 'text-orange-400';
            if (status >= 500) return 'text-red-400';
            return 'text-gray-400';
        },
        
        getLogColor(level) {
            const colors = {
                'CRITICAL': 'text-red-400',
                'ERROR': 'text-red-300',
                'WARNING': 'text-yellow-400',
                'INFO': 'text-blue-300',
                'DEBUG': 'text-gray-400',
                'SUCCESS': 'text-green-400'
            };
            return colors[level] || 'text-gray-300';
        },
        
        hashString(str) {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return Math.abs(hash);
        },
        
        downloadLogs() {
            const logData = this.logs.map(log => {
                if (log.type === 'http') {
                    return `${log.timestamp} ${log.method} ${log.path} ${log.status} ${log.latency}`;
                } else {
                    return `${log.timestamp} [${log.level}] ${log.message}`;
                }
            }).join('\n');
            
            const blob = new Blob([logData], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `logs_${new Date().toISOString().split('T')[0]}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        },
        
        // Settings functions
        getRealWebhookUrl() {
            return `${window.location.protocol}//${window.location.host}/webhook/donationalerts`;
        },
        
        getRealWidgetUrl() {
            return `${window.location.protocol}//${window.location.host}/widget`;
        },
        
        
        copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('Copied to clipboard!');
            }).catch(err => {
                console.error('Failed to copy: ', err);
                alert('Failed to copy to clipboard');
            });
        },
        
        // Video gallery functions
        async loadAllVideos() {
            try {
                const response = await fetch('/api/all-videos');
                const data = await response.json();
                if (data.success) {
                    this.allVideos = data.videos;
                }
            } catch (error) {
                console.error('Failed to load videos:', error);
            }
        },
        
        async refreshVideoGallery() {
            await this.loadAllVideos();
        },
        
        async generatePresetVideo(preset) {
            const presets = {
                'celebration': 'A spectacular celebration scene with colorful fireworks exploding in the night sky, confetti falling, and sparkles of light creating a joyful atmosphere',
                'confetti': 'Bright colorful confetti bursting and falling through the air in slow motion, creating a festive celebration atmosphere',
                'sparkles': 'Golden sparkles and magical glitter particles floating and dancing in the air with warm glowing light effects',
                'hearts': 'Cute animated hearts in various sizes flying and floating gracefully through a soft pink and white background'
            };
            
            const prompt = presets[preset] || presets.celebration;
            this.customPrompt = prompt;
            await this.generateCustomVideo();
        },
        
        formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },
        
        formatDate(timestamp) {
            const date = new Date(timestamp * 1000);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        },
        
        async playVideoInOBS(videoUrl) {
            try {
                const payload = { url: videoUrl };
                const response = await fetch('/api/play-in-obs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (response.ok && data.success) {
                    // Do not refresh preview; the widget will pick up via polling to avoid flicker
                    alert('Play request sent to OBS widget.');
                } else {
                    alert('Error: ' + (data.error || 'Failed to send play request'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        },
        
        downloadVideo(videoUrl, filename) {
            const link = document.createElement('a');
            link.href = videoUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        },
        
        async deleteVideo(filename) {
            if (!confirm(`Are you sure you want to delete ${filename}?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/api/delete-video/${encodeURIComponent(filename)}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                if (data.success) {
                    alert('Video deleted successfully');
                    await this.refreshVideoGallery();
                } else {
                    alert('Error deleting video: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        },
        
        // New functions for the requested features
        refreshWidgetPreview() {
            // Refresh the iframe src to reload the widget
            const iframe = document.querySelector('iframe[title="OBS Widget Preview"]');
            if (iframe) {
                const src = iframe.src;
                iframe.src = '';
                setTimeout(() => iframe.src = src, 100);
            }
        },
        
        async loadSystemPrompt() {
            try {
                const response = await fetch('/api/system-prompt');
                const data = await response.json();
                if (data.success) {
                    this.systemPrompt = data.prompt || '';
                }
            } catch (error) {
                console.error('Failed to load system prompt:', error);
            }
        },
        
        async saveSystemPrompt() {
            try {
                const response = await fetch('/api/system-prompt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        prompt: this.systemPrompt
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    alert('Custom video prompt saved successfully!');
                } else {
                    alert('Error saving system prompt: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        },
        
        async loadSettings() {
            try {
                // Load connection status
                const statusResponse = await fetch('/api/connection-status');
                const statusData = await statusResponse.json();
                this.connectionStatus = {
                    connected: statusData.connected || false,
                    configured: statusData.configured || false
                };
                
                // Load user threshold settings
                const thresholdResponse = await fetch('/api/threshold');
                const thresholdData = await thresholdResponse.json();
                this.thresholdAmount = thresholdData.threshold || 1000;
                
            } catch (error) {
                console.error('Failed to load settings:', error);
            }
        },

        async loadAIMLStatus() {
            try {
                const response = await fetch('/api/aiml-status');
                const data = await response.json();
                if (data && data.success) {
                    this.aimlApiConfigured = !!data.has_api_key;
                    if (typeof data.threshold_rub === 'number') {
                        this.thresholdAmount = data.threshold_rub;
                    }
                }
            } catch (error) {
                console.error('Failed to load AIML status:', error);
            }
        },

        // Poll generation status and push notifications
        async loadGenerationStatus() {
            try {
                const response = await fetch('/api/generation-status');
                const data = await response.json();
                if (data && data.success) {
                    const prev = (this.generationStatus && this.generationStatus.status) || 'idle';
                    this.generationStatus = data.status || { active: false, status: 'idle', progress: 0 };
                    const curr = (this.generationStatus.status || 'idle').toLowerCase();
                    if (prev !== curr) {
                        const map = {
                            starting: 'Video generation starting',
                            queued: 'Video generation queued',
                            waiting: 'AIML waiting',
                            active: 'AIML active',
                            generating: 'AIML generating video',
                            completed: 'AIML completed - retrieving result',
                            downloading: 'Downloading video',
                            done: 'Video is ready',
                            error: 'Video generation failed',
                            timeout: 'Video generation timed out'
                        };
                        const msg = map[curr] || `Status: ${curr}`;
                        const type = curr === 'error' ? 'error' : (curr === 'done' ? 'success' : 'info');
                        this.addNotification(msg, type);
                        if (curr === 'done') {
                            setTimeout(() => this.refreshVideoGallery(), 1500);
                        }
                    }
                }
            } catch (error) {
                // ignore occasional polling errors
            }
        },

        addNotification(message, type = 'info') {
            const item = { id: Date.now() + Math.random(), message, type, ts: new Date().toLocaleTimeString() };
            this.notifications.push(item);
            if (this.notifications.length > 6) {
                this.notifications = this.notifications.slice(-6);
            }
            setTimeout(() => {
                this.notifications = this.notifications.filter(n => n.id !== item.id);
            }, 10000);
        },
        
        async connectDonationAlerts() {
            window.location.href = '/api/da/oauth/login';
        },
        
        async disconnectDonationAlerts() {
            if (!confirm('Are you sure you want to disconnect from DonationAlerts? This will remove your access token.')) {
                return;
            }
            
            try {
                const response = await fetch('/api/da/disconnect', {
                    method: 'POST'
                });
                
                const data = await response.json();
                if (data.success) {
                    alert('Disconnected from DonationAlerts successfully');
                    await this.loadSettings(); // Reload to update status
                } else {
                    alert('Error disconnecting: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        },
        
        async testDonationAlertsAPI() {
            try {
                const response = await fetch('/api/test-donation-alerts');
                const data = await response.json();
                if (data.success) {
                    alert(`API test successful! Found ${data.total_donations} donations. Status: ${data.status}`);
                } else {
                    alert('API test failed: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        },
        
        async saveThreshold() {
            try {
                const response = await fetch('/api/threshold', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        amount: this.thresholdAmount,
                        currency: this.thresholdCurrency
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    alert('Donation threshold saved successfully!');
                } else {
                    alert('Error saving threshold: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        }
    };
};
