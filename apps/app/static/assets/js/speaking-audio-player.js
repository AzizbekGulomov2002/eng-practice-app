/**
 * Speaking Audio Player Component
 * WebM va boshqa audio formatlar uchun chiroyli audio player
 */

class SpeakingAudioPlayer {
    constructor(containerId, audioData) {
        this.containerId = containerId;
        this.audioData = audioData;
        this.audio = null;
        this.duration = 0;
        this.currentTime = 0;
        this.isPlaying = false;
        this.init();
    }

    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container with id "${this.containerId}" not found`);
            return;
        }

        if (!this.audioData || !this.audioData.url) {
            container.innerHTML = '<p class="audio-error">Audio fayl topilmadi</p>';
            return;
        }

        this.createPlayer(container);
        this.setupAudio();
    }

    createPlayer(container) {
        const playerHTML = `
            <div class="speaking-audio-player">
                <div class="audio-player-container">
                    <button class="play-pause-btn" id="${this.containerId}-play-btn" aria-label="Play/Pause">
                        <svg class="play-icon" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M8 5v14l11-7z"/>
                        </svg>
                        <svg class="pause-icon" viewBox="0 0 24 24" fill="currentColor" style="display: none;">
                            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
                        </svg>
                    </button>
                    <div class="audio-controls">
                        <div class="progress-container">
                            <div class="progress-bar" id="${this.containerId}-progress-bar">
                                <div class="progress-fill" id="${this.containerId}-progress-fill"></div>
                                <div class="progress-tooltip" id="${this.containerId}-progress-tooltip" style="display: none;">0:00</div>
                            </div>
                        </div>
                        <div class="time-display">
                            <span class="current-time" id="${this.containerId}-current-time">0:00</span>
                            <span class="duration" id="${this.containerId}-duration">0:00</span>
                        </div>
                    </div>
                    <div class="volume-control">
                        <button class="volume-btn" id="${this.containerId}-volume-btn" aria-label="Volume">
                            <svg class="volume-icon" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                            </svg>
                        </button>
                        <input type="range" class="volume-slider" id="${this.containerId}-volume-slider" min="0" max="100" value="100">
                    </div>
                    <button class="download-btn" id="${this.containerId}-download-btn" aria-label="Download" title="Yuklab olish">
                        <svg class="download-icon" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/>
                        </svg>
                    </button>
                </div>
                <audio id="${this.containerId}-audio" preload="metadata" crossorigin="anonymous">
                    <source src="${this.audioData.url}" type="${this.audioData.mime_type || 'audio/*'}">
                    <source src="${this.audioData.url}">
                    Sizning brauzeringiz audio elementni qo'llab-quvvatlamaydi.
                </audio>
            </div>
        `;
        container.innerHTML = playerHTML;
    }

    setupAudio() {
        this.audio = document.getElementById(`${this.containerId}-audio`);
        if (!this.audio) return;

        const playBtn = document.getElementById(`${this.containerId}-play-btn`);
        const progressBar = document.getElementById(`${this.containerId}-progress-bar`);
        const progressFill = document.getElementById(`${this.containerId}-progress-fill`);
        const progressTooltip = document.getElementById(`${this.containerId}-progress-tooltip`);
        const currentTimeEl = document.getElementById(`${this.containerId}-current-time`);
        const durationEl = document.getElementById(`${this.containerId}-duration`);
        const volumeBtn = document.getElementById(`${this.containerId}-volume-btn`);
        const volumeSlider = document.getElementById(`${this.containerId}-volume-slider`);
        const downloadBtn = document.getElementById(`${this.containerId}-download-btn`);

        // Play/Pause button
        playBtn.addEventListener('click', () => this.togglePlay());

        // Download button
        downloadBtn.addEventListener('click', () => this.downloadAudio());

        // Progress bar hover va click - timestamp ko'rsatish
        const updateTooltip = (e) => {
            if (!this.duration || this.duration === 0) return;
            
            const rect = progressBar.getBoundingClientRect();
            const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            const time = this.duration * percent;
            const timeStr = this.formatTime(time);
            
            // Tooltip ni ko'rsatish va pozitsiyasini o'rnatish
            progressTooltip.textContent = timeStr;
            progressTooltip.style.display = 'block';
            
            // Tooltip pozitsiyasini hisoblash
            const tooltipWidth = progressTooltip.offsetWidth || 40;
            const tooltipLeft = percent * rect.width - tooltipWidth / 2;
            progressTooltip.style.left = `${Math.max(0, Math.min(rect.width - tooltipWidth, tooltipLeft))}px`;
        };

        // Progress bar hover
        progressBar.addEventListener('mousemove', updateTooltip);
        progressBar.addEventListener('mouseenter', () => {
            progressTooltip.style.display = 'block';
        });
        progressBar.addEventListener('mouseleave', () => {
            progressTooltip.style.display = 'none';
        });

        // Progress bar click - timestamp ko'rsatish va seek qilish
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            const time = this.duration * percent;
            
            // Click qilingan vaqtni ko'rsatish
            const timeStr = this.formatTime(time);
            currentTimeEl.textContent = timeStr;
            
            // Seek qilish
            this.seek(percent);
            
            // Tooltip ni yangilash
            updateTooltip(e);
            
            // Tooltip ni bir oz vaqt ko'rsatib, keyin yashirish
            setTimeout(() => {
                if (!progressBar.matches(':hover')) {
                    progressTooltip.style.display = 'none';
                }
            }, 1000);
        });

        // Volume control
        volumeSlider.addEventListener('input', (e) => {
            this.audio.volume = e.target.value / 100;
        });

        volumeBtn.addEventListener('click', () => {
            if (this.audio.volume > 0) {
                this.audio.volume = 0;
                volumeSlider.value = 0;
            } else {
                this.audio.volume = 1;
                volumeSlider.value = 100;
            }
            this.updateVolumeIcon();
        });

        // Audio events
        this.audio.addEventListener('loadedmetadata', () => {
            this.duration = this.audio.duration;
            durationEl.textContent = this.formatTime(this.duration);
        });

        this.audio.addEventListener('timeupdate', () => {
            this.currentTime = this.audio.currentTime;
            currentTimeEl.textContent = this.formatTime(this.currentTime);
            const percent = (this.currentTime / this.duration) * 100 || 0;
            progressFill.style.width = `${percent}%`;
        });

        this.audio.addEventListener('play', () => {
            this.isPlaying = true;
            this.updatePlayButton();
        });

        this.audio.addEventListener('pause', () => {
            this.isPlaying = false;
            this.updatePlayButton();
        });

        this.audio.addEventListener('ended', () => {
            this.isPlaying = false;
            this.updatePlayButton();
            this.audio.currentTime = 0;
        });

        // TO'LIQ DURATION KO'RSATISH - KUCHLI YECHIM
        this.audio.preload = 'auto'; // Barcha formatlar uchun auto
        let durationFound = false;

        // Universal duration update function - to'liq duration olish uchun
        let lastDuration = 0;
        const tryUpdateDuration = () => {
            if (this.audio.duration && !isNaN(this.audio.duration) && isFinite(this.audio.duration) && this.audio.duration > 0) {
                if (this.audio.duration !== lastDuration) {
                    lastDuration = this.audio.duration;
                    this.duration = this.audio.duration;
                    durationEl.textContent = this.formatTime(this.duration);
                    durationFound = true;
                    return true;
                }
            }
            return false;
        };

        // Method 1: XHR orqali audio faylning uzunligini olish
        const getDurationViaXHR = () => {
            if (durationFound) return;
            const xhr = new XMLHttpRequest();
            xhr.open('HEAD', this.audioData.url, true);
            xhr.onreadystatechange = () => {
                if (xhr.readyState === 4 && xhr.status === 200) {
                    const contentLength = xhr.getResponseHeader('Content-Length');
                    if (contentLength) {
                        // Audio fayl yuklanganini tekshirish
                        this.audio.load();
                        setTimeout(() => {
                            if (this.audio.duration && this.audio.duration > 0) {
                                durationFound = true;
                                tryUpdateDuration();
                            }
                        }, 500);
                    }
                }
            };
            xhr.send();
        };

        // Method 2: Seek to end trick - duration ni trigger qilish
        const seekToEndTrick = () => {
            if (durationFound) return;
            if (this.audio.readyState >= 2) {
                const savedTime = this.audio.currentTime;
                this.audio.currentTime = 1e10;
                setTimeout(() => {
                    if (this.audio.duration && this.audio.duration > 0) {
                        durationFound = true;
                        this.audio.currentTime = savedTime;
                        tryUpdateDuration();
                    } else {
                        this.audio.currentTime = savedTime;
                    }
                }, 200);
            }
        };

        // Method 3: Play/pause trick
        const playPauseTrick = () => {
            if (durationFound || this.isPlaying) return;
            if (this.audio.readyState >= 2) {
                const promise = this.audio.play();
                if (promise !== undefined) {
                    promise.then(() => {
                        setTimeout(() => {
                            if (this.audio.duration && this.audio.duration > 0) {
                                durationFound = true;
                            }
                            this.audio.pause();
                            this.audio.currentTime = 0;
                            tryUpdateDuration();
                        }, 100);
                    }).catch(() => {
                        tryUpdateDuration();
                    });
                }
            }
        };

        // Method 4: Force load va to'liq yuklash
        const forceLoad = () => {
            this.audio.load();
            this.audio.preload = 'auto';
        };

        // Barcha usullarni bir vaqtda ishga tushirish
        const forceGetDuration = () => {
            if (durationFound) return;
            tryUpdateDuration();
            seekToEndTrick();
            playPauseTrick();
        };

        // BARCHA event listenerlar - duration ni to'liq olish uchun
        this.audio.addEventListener('loadstart', tryUpdateDuration);
        this.audio.addEventListener('loadedmetadata', tryUpdateDuration);
        this.audio.addEventListener('loadeddata', tryUpdateDuration);
        this.audio.addEventListener('canplay', tryUpdateDuration);
        this.audio.addEventListener('canplaythrough', tryUpdateDuration);
        this.audio.addEventListener('durationchange', tryUpdateDuration);
        this.audio.addEventListener('progress', tryUpdateDuration);
        this.audio.addEventListener('suspend', tryUpdateDuration);
        this.audio.addEventListener('stalled', tryUpdateDuration);
        this.audio.addEventListener('waiting', tryUpdateDuration);
        this.audio.addEventListener('playing', tryUpdateDuration);
        
        // Initial setup
        forceLoad();
        getDurationViaXHR();
        
        // Initial check
        if (this.audio.readyState >= 1) {
            forceGetDuration();
        }
        
        // IMMEDIATE va tez urinishlar
        setTimeout(forceGetDuration, 50);
        setTimeout(forceGetDuration, 100);
        setTimeout(forceGetDuration, 200);
        setTimeout(forceGetDuration, 300);
        setTimeout(forceGetDuration, 500);
        setTimeout(forceGetDuration, 800);
        setTimeout(forceGetDuration, 1000);
        setTimeout(forceGetDuration, 1500);
        setTimeout(forceGetDuration, 2000);
        setTimeout(forceGetDuration, 3000);
        setTimeout(forceGetDuration, 5000);
        setTimeout(forceGetDuration, 8000);
        setTimeout(forceGetDuration, 10000);
        setTimeout(forceGetDuration, 15000);
        
        // AGGRESSIVE interval check (har 300ms)
        const durationCheckInterval = setInterval(() => {
            if (durationFound) {
                clearInterval(durationCheckInterval);
                return;
            }
            if (tryUpdateDuration()) {
                durationFound = true;
                clearInterval(durationCheckInterval);
            } else {
                forceGetDuration();
            }
        }, 300);
        
        // 60 soniyadan keyin intervalni to'xtatish
        setTimeout(() => {
            clearInterval(durationCheckInterval);
            // Oxirgi urinishlar
            forceGetDuration();
            setTimeout(forceGetDuration, 1000);
        }, 60000);
    }

    downloadAudio() {
        if (!this.audioData || !this.audioData.url) {
            return;
        }
        
        // Download link yaratish
        const link = document.createElement('a');
        link.href = this.audioData.url;
        link.download = this.audioData.file_name || 'audio.webm';
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    togglePlay() {
        if (this.isPlaying) {
            this.audio.pause();
        } else {
            this.audio.play();
        }
    }

    seek(percent) {
        if (this.duration) {
            this.audio.currentTime = this.duration * percent;
        }
    }

    updatePlayButton() {
        const playBtn = document.getElementById(`${this.containerId}-play-btn`);
        const playIcon = playBtn.querySelector('.play-icon');
        const pauseIcon = playBtn.querySelector('.pause-icon');
        
        if (this.isPlaying) {
            playIcon.style.display = 'none';
            pauseIcon.style.display = 'block';
        } else {
            playIcon.style.display = 'block';
            pauseIcon.style.display = 'none';
        }
    }

    updateVolumeIcon() {
        const volumeBtn = document.getElementById(`${this.containerId}-volume-btn`);
        const volumeIcon = volumeBtn.querySelector('.volume-icon');
        const volume = this.audio.volume;
        
        if (volume === 0) {
            volumeIcon.innerHTML = '<path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>';
        } else if (volume < 0.5) {
            volumeIcon.innerHTML = '<path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z"/>';
        } else {
            volumeIcon.innerHTML = '<path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>';
        }
    }

    formatTime(seconds) {
        if (!seconds || isNaN(seconds) || !isFinite(seconds)) {
            return '0:00';
        }
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Global function for easy usage
window.createSpeakingAudioPlayer = function(containerId, audioData) {
    return new SpeakingAudioPlayer(containerId, audioData);
};

