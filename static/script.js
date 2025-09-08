/**
 * Donation Celebration Widget JavaScript
 * Handles video playback, API communication, and UI updates
 */

class DonationWidget {
    constructor() {
        this.videoElement = document.getElementById('celebrationVideo');
        this.idleState = document.getElementById('idleState');
        this.loadingState = document.getElementById('loadingState');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.debugInfo = document.getElementById('debugInfo');
        
        // Ensure audio is enabled in OBS/browser
        this.configureAudio();
        
        // State management
        this.currentState = 'idle'; // idle, loading, playing, error
        this.lastVideoCheck = null;
        this.lastKnownVideo = null;
        this.checkInterval = null;
        this.retryCount = 0;
        this.maxRetries = 5;
        this.isChecking = false;
        this.isForcedPlaying = false;
        this.lastForcedFilename = null;
        this.lastProcessedRequestId = null;
        this.playLockUntil = 0;
        this.autoplayEnabled = false;
        this.initialPoll = true;
        
        // Configuration
        this.checkIntervalMs = 3000; // Check for new videos every 3 seconds
        this.retryDelayMs = 5000; // Retry failed requests after 5 seconds
        
        this.init();
    }
    
    init() {
        console.log('🎉 Donation Celebration Widget initializing...');
        
        // Setup video event handlers
        this.setupVideoHandlers();
        
        // Setup debug info visibility
        this.setupDebugInfo();
        
        // Start checking for videos
        this.startVideoChecking();
        
        // Update status
        this.updateStatus('ready', 'Ready');
        
        console.log('✅ Widget initialized successfully');
    }
    
    setupVideoHandlers() {
        this.videoElement.addEventListener('loadstart', () => {
            if (!this.videoElement.src) {
                return; // ignore spurious loadstart when no src set
            }
            console.log('📹 Video loading started');
            this.updateStatus('loading', 'Loading...');
        });
        
        this.videoElement.addEventListener('canplay', () => {
            console.log('📹 Video ready to play');
            this.showVideo();
        });
        
        this.videoElement.addEventListener('play', () => {
            console.log('📹 Video started playing');
            this.updateStatus('playing', 'Playing');
            this.setState('playing');
        });
        
        this.videoElement.addEventListener('ended', () => {
            console.log('📹 Video playback ended');
            this.onVideoEnded();
        });
        
        this.videoElement.addEventListener('error', (e) => {
            console.error('📹 Video error:', e);
            this.handleVideoError();
        });

        // Auto-resume if unexpected pause occurs during forced playback
        this.videoElement.addEventListener('pause', () => {
            if (this.isForcedPlaying && !this.videoElement.ended) {
                console.log('⏸️ Unexpected pause during forced playback, attempting to resume');
                const p = this.videoElement.play();
                if (p && p.catch) {
                    p.catch(err => console.warn('Resume play failed:', err));
                }
            }
        });

        // Helpful logging for buffering/playing states
        this.videoElement.addEventListener('waiting', () => {
            console.log('⏳ Video buffering...');
        });
        this.videoElement.addEventListener('playing', () => {
            console.log('▶️ Video playing');
        });
    }

    configureAudio() {
        if (!this.videoElement) return;
        try {
            this.videoElement.muted = false;
            this.videoElement.defaultMuted = false;
            this.videoElement.removeAttribute('muted');
            this.videoElement.volume = 1.0;
        } catch (_) {}

        // For regular browsers, unlock audio on first interaction; OBS CEF allows autoplay with sound.
        const resumeAudio = () => {
            try {
                this.videoElement.muted = false;
                this.videoElement.defaultMuted = false;
                this.videoElement.removeAttribute('muted');
                this.videoElement.volume = 1.0;
                const p = this.videoElement.play();
                if (p && p.catch) p.catch(() => {});
            } catch (_) {}
            window.removeEventListener('click', resumeAudio);
            window.removeEventListener('keydown', resumeAudio);
        };
        window.addEventListener('click', resumeAudio, { once: true });
        window.addEventListener('keydown', resumeAudio, { once: true });
    }
    
    setupDebugInfo() {
        // If debug panel is not present (OBS-minimal mode), skip
        if (!this.debugInfo) return;

        // Show debug info on hover or when not in OBS
        const isOBS = window.innerWidth === 800 && window.innerHeight === 450;
        
        if (!isOBS) {
            this.debugInfo.style.opacity = '0.7';
            
            // Update debug info every second
            setInterval(() => {
                this.updateDebugInfo();
            }, 1000);
        }
    }
    
    startVideoChecking() {
        // Prevent duplicate intervals
        if (this.checkInterval) {
            return;
        }

        // Initial check
        this.checkForNewVideo();
        
        // Set up periodic checking
        this.checkInterval = setInterval(() => {
            this.checkForNewVideo();
        }, this.checkIntervalMs);
        
        console.log(`🔄 Started checking for videos every ${this.checkIntervalMs / 1000}s`);
    }

    stopVideoChecking() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
            console.log('⏸️ Stopped video checking interval');
        }
    }
    
    async checkForNewVideo() {
        if (this.isChecking) {
            return;
        }
        this.isChecking = true;
        // If we recently started a forced playback, ignore checks until lock expires
        if (this.playLockUntil && Date.now() < this.playLockUntil) {
            this.isChecking = false;
            this.updateConnectionStatus('connected');
            return;
        }
        try {
            const response = await fetch('/api/latest-video');
            console.log('🔁 /api/latest-video fetched', response);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.lastVideoCheck = new Date();
            this.retryCount = 0; // Reset retry count on success
            
            if (data.status === 'success' && data.video) {
                const videoInfo = data.video;
                const wasRequested = !!data.requested;
                const requestId = data.request_id || null;

                // If we are in a forced playback, ignore non-requested polls
                if (this.isForcedPlaying && !wasRequested) {
                    this.updateConnectionStatus('connected');
                    return;
                }

                // Do not interrupt current playback with non-requested updates
                if (this.currentState === 'playing' && !wasRequested) {
                    this.updateConnectionStatus('connected');
                    return;
                }

                if (wasRequested) {
                    // Ignore initial requested play immediately after widget loads to avoid accidental autoplay on open
                    if (this.initialPoll) {
                        console.log('⏹️ Ignoring requested play on initial poll');
                        this.lastKnownVideo = videoInfo;
                        this.updateConnectionStatus('connected');
                        this.initialPoll = false;
                        return;
                    }

                    // Avoid re-processing the same request while server TTL is active
                    if (requestId && this.lastProcessedRequestId === requestId) {
                        this.updateConnectionStatus('connected');
                        return;
                    }
                    this.lastProcessedRequestId = requestId || this.lastProcessedRequestId;

                    console.log('📣 Play request received for:', videoInfo.filename, requestId ? `(id=${requestId})` : '');
                    this.playNewVideo(videoInfo, true);
                    this.lastKnownVideo = videoInfo;
                    this.updateConnectionStatus('connected');
                    return;
                }
                
                // Check if this is a new video
                if (!this.lastKnownVideo || this.lastKnownVideo.filename !== videoInfo.filename) {
                    console.log('🆕 New video detected:', videoInfo.filename);
                    if (!this.autoplayEnabled) {
                        console.log('⏹️ Autoplay disabled; updating lastKnownVideo without playback');
                        this.lastKnownVideo = videoInfo;
                        this.updateConnectionStatus('connected');
                        return;
                    }
                    this.playNewVideo(videoInfo);
                    this.lastKnownVideo = videoInfo;
                } else {
                    // No change, but connection is fine
                    this.updateConnectionStatus('connected');
                }
            } else if (data.status === 'no_videos') {
                // No videos available - this is normal
                this.updateConnectionStatus('connected');
            }
            
        } catch (error) {
            console.error('❌ Error checking for videos:', error);
            this.handleCheckError();
        } finally {
            this.isChecking = false;
        }
    }
    
    playNewVideo(videoInfo, force = false) {
        console.log('🎬 Playing celebration video:', videoInfo.filename, force ? '(forced)' : '');
        
        if (force) {
            this.isForcedPlaying = true;
            this.lastForcedFilename = videoInfo.filename || null;
            // Set a lock window to ignore further checks while this plays
            this.playLockUntil = Date.now() + 10000; // 10s lock; will be cleared on ended/error
            // Suspend polling to avoid any interference during forced playback
            this.stopVideoChecking();
        }
        
        // Update state to loading
        this.setState('loading');
        this.updateStatus('loading', 'Loading video...');
        
        try {
            if (force) {
                // Reset playback state to ensure same file replays
                try {
                    this.videoElement.pause();
                    this.videoElement.currentTime = 0;
                } catch (_) {}
            }
            // Use cache-busting when forcing to avoid browser caching issues on same src
            this.videoElement.autoplay = true;
            const src = force ? `${videoInfo.url}?t=${Date.now()}` : videoInfo.url;
            console.log('🔧 Setting video src:', src, 'force:', force);
            this.videoElement.src = src;
            // Explicitly (re)load the media after changing src to avoid stray readyState issues
            try { this.videoElement.load(); } catch (_) {}
            // Ensure audio is unmuted and at full volume for OBS
            try {
                this.videoElement.muted = false;
                this.videoElement.defaultMuted = false;
                this.videoElement.removeAttribute('muted');
                this.videoElement.volume = 1.0;
            } catch (_) {}
        } catch (e) {
            console.error('❌ Failed to set video source:', e);
        }
        
        // Attempt to play
        const playPromise = this.videoElement.play();
        
        if (playPromise !== undefined) {
            playPromise
                .then(() => {
                    console.log('✅ Video playback started successfully');
                })
                .catch((error) => {
                    console.error('❌ Video play failed:', error);
                    this.handleVideoError();
                });
        }
    }
    
    showVideo() {
        this.videoElement.style.display = 'block';
        this.videoElement.classList.add('video-fade-in');
        if (this.idleState) this.idleState.style.display = 'none';
        if (this.loadingState) this.loadingState.style.display = 'none';
        
        // Remove animation class after animation completes
        setTimeout(() => {
            this.videoElement.classList.remove('video-fade-in');
        }, 500);
    }
    
    hideVideo() {
        this.videoElement.classList.add('video-fade-out');
        
        setTimeout(() => {
            try { this.videoElement.pause(); } catch (_) {}
            this.videoElement.style.display = 'none';
            this.videoElement.classList.remove('video-fade-out');
            // Do NOT clear src here to avoid triggering load/error loops
            if (this.idleState) this.idleState.style.display = 'block';
            if (this.loadingState) this.loadingState.style.display = 'none';
        }, 500);
    }
    
    onVideoEnded() {
        console.log('🏁 Video ended, returning to idle state');
        const wasForced = this.isForcedPlaying === true;
        this.setState('idle');
        this.updateStatus('ready', 'Ready');
        this.isForcedPlaying = false;
        this.lastForcedFilename = null;
        this.lastProcessedRequestId = null;
        this.playLockUntil = 0;

        // If the just-finished playback was forced, temporarily disable autoplay
        if (wasForced) {
            this.autoplayEnabled = false;
            setTimeout(() => {
                this.autoplayEnabled = true;
            }, 10000); // 10s cooldown to avoid auto-playing the "latest" video
        }

        this.hideVideo();
        // After hide animation, fully reset media source and autoplay
        setTimeout(() => {
            try {
                this.videoElement.autoplay = false;
                this.videoElement.pause();
                this.videoElement.removeAttribute('src');
                this.videoElement.load();
            } catch (_) {}
        }, 600);
        // Resume polling after playback completes
        this.startVideoChecking();
    }
    
    handleVideoError() {
        // Ignore benign errors when no source is set or we're idle to prevent loops
        if (!this.videoElement.src || this.currentState === 'idle') {
            console.warn('Ignoring video error due to empty src or idle state');
            return;
        }

        console.error('📹 Video playback error');
        this.setState('error');
        this.updateStatus('error', 'Video Error');
        this.isForcedPlaying = false;
        this.lastForcedFilename = null;
        this.lastProcessedRequestId = null;
        this.playLockUntil = 0;
        
        // Return to idle after a short delay and resume polling
        setTimeout(() => {
            this.setState('idle');
            this.updateStatus('ready', 'Ready');
            this.hideVideo();
            setTimeout(() => {
                try {
                    this.videoElement.autoplay = false;
                    this.videoElement.pause();
                    this.videoElement.removeAttribute('src');
                    this.videoElement.load();
                } catch (_) {}
            }, 600);
            this.startVideoChecking();
        }, 1500);
    }
    
    handleCheckError() {
        this.retryCount++;
        this.updateConnectionStatus('error');
        
        if (this.retryCount < this.maxRetries) {
            console.log(`🔄 Retrying in ${this.retryDelayMs / 1000}s (attempt ${this.retryCount}/${this.maxRetries})`);
            
            setTimeout(() => {
                this.checkForNewVideo();
            }, this.retryDelayMs);
        } else {
            console.error('❌ Max retries reached, stopping video checks');
            this.updateStatus('error', 'Connection Failed');
            
            // Restart checking after a longer delay
            setTimeout(() => {
                this.retryCount = 0;
                this.startVideoChecking();
            }, 30000);
        }
    }
    
    setState(newState) {
        if (this.currentState !== newState) {
            console.log(`🔄 State changed: ${this.currentState} → ${newState}`);
            this.currentState = newState;
            
            // Update UI based on state (guard when elements are not present)
            switch (newState) {
                case 'idle':
                    if (this.idleState) this.idleState.style.display = 'block';
                    if (this.loadingState) this.loadingState.style.display = 'none';
                    break;
                    
                case 'loading':
                    if (this.idleState) this.idleState.style.display = 'none';
                    if (this.loadingState) this.loadingState.style.display = 'block';
                    break;
                    
                case 'playing':
                    if (this.idleState) this.idleState.style.display = 'none';
                    if (this.loadingState) this.loadingState.style.display = 'none';
                    break;
                    
                case 'error':
                    if (this.loadingState) this.loadingState.style.display = 'none';
                    break;
            }
        }
    }
    
    updateStatus(type, message) {
        if (!this.statusIndicator) return;
        const statusDot = this.statusIndicator.querySelector('.status-dot');
        const statusLabel = this.statusIndicator.querySelector('.status-label');
        if (!statusDot || !statusLabel) return;
        
        // Remove existing classes
        statusDot.className = 'status-dot';
        
        // Add appropriate class
        switch (type) {
            case 'ready':
            case 'playing':
                statusDot.classList.add('ready');
                break;
            case 'loading':
                statusDot.classList.add('warning');
                break;
            case 'error':
                statusDot.classList.add('error');
                break;
        }
        
        statusLabel.textContent = message;
    }
    
    updateConnectionStatus(status) {
        const connectionElement = document.getElementById('connectionStatus');
        if (connectionElement) {
            switch (status) {
                case 'connected':
                    connectionElement.textContent = 'Connected';
                    connectionElement.style.color = '#4CAF50';
                    break;
                case 'error':
                    connectionElement.textContent = 'Connection Error';
                    connectionElement.style.color = '#F44336';
                    break;
                default:
                    connectionElement.textContent = 'Unknown';
                    connectionElement.style.color = '#FF9800';
            }
        }
    }
    
    updateDebugInfo() {
        // Update last check time
        const lastCheckElement = document.getElementById('lastCheck');
        if (lastCheckElement && this.lastVideoCheck) {
            lastCheckElement.textContent = this.lastVideoCheck.toLocaleTimeString();
        }
        
        // Update current video
        const currentVideoElement = document.getElementById('currentVideo');
        if (currentVideoElement) {
            currentVideoElement.textContent = this.lastKnownVideo ? 
                this.lastKnownVideo.filename : 'None';
        }
        
        // Video count would be updated from API responses
    }
    
    // Cleanup when page unloads
    destroy() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
        }
        console.log('🧹 Widget destroyed');
    }
}

// Global functions for video event handlers (called from HTML)
window.onVideoEnded = function() {
    if (window.donationWidget) {
        window.donationWidget.onVideoEnded();
    }
};

// Initialize widget when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.donationWidget = new DonationWidget();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.donationWidget) {
        window.donationWidget.destroy();
    }
});

/* Handle visibility change (avoid interrupting active playback) */
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        if (window.donationWidget) {
            if (window.donationWidget.isForcedPlaying || window.donationWidget.currentState === 'playing') {
                console.log('👁️ Visible but currently playing; skip check');
                return;
            }
            console.log('👁️ Widget visible, checking for new videos');
            window.donationWidget.checkForNewVideo();
        }
    }
});
