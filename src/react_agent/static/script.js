// Enhanced AI Chat Interface JavaScript with Modern Features

document.addEventListener('DOMContentLoaded', function() {
    // Disable all audio contexts globally
    if (window.AudioContext) {
        window.AudioContext = function() {
            return { createOscillator: () => ({}), createGain: () => ({}), destination: {} };
        };
    }
    if (window.webkitAudioContext) {
        window.webkitAudioContext = function() {
            return { createOscillator: () => ({}), createGain: () => ({}), destination: {} };
        };
    }
    
    // Initialize theme system
    initializeTheme();
    
    // Initialize chat functionality if we're on the conversation page
    if (document.getElementById('chatMessages')) {
        initializeChat();
    }
    
    // Initialize form enhancements for landing page
    if (document.querySelector('.landing-card')) {
        initializeLandingPage();
    }
    
    // Initialize exit page functionality
    if (document.querySelector('.exit-card')) {
        initializeExitPage();
    }
    
    // Add smooth scroll behavior
    initializeSmoothScrolling();
    
    // Add page transition effects
    initializePageTransitions();
    

});

// Theme Management System
function initializeTheme() {
    // Get saved theme or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    // Find existing theme toggle button (could be in header or standalone)
    let themeToggle = document.getElementById('themeToggle') || 
                      document.querySelector('.theme-toggle-header') || 
                      document.querySelector('.theme-toggle');
    
    if (!themeToggle) {
        // Create theme toggle button for pages that don't have one (like landing page)
        themeToggle = document.createElement('button');
        themeToggle.className = 'theme-toggle';
        themeToggle.innerHTML = '🌙';
        themeToggle.setAttribute('aria-label', 'Toggle dark mode');
        themeToggle.title = 'Toggle dark/light mode';
        document.body.appendChild(themeToggle);
    }
    
    // Apply initial theme state
    updateThemeIcon(themeToggle, savedTheme);
    
    // Add click handler
    themeToggle.addEventListener('click', function() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        // Add animation class
        themeToggle.style.transform = 'scale(0.8) rotate(180deg)';
        
        setTimeout(() => {
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(themeToggle, newTheme);
            
            // Reset animation
            themeToggle.style.transform = '';
        }, 150);
    });
}

function updateThemeIcon(button, theme) {
    button.innerHTML = theme === 'dark' ? '☀️' : '🌙';
}

// Enhanced Chat functionality
function initializeChat() {
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const scrollToBottomBtn = document.getElementById('scrollToBottom');
    
    // Enhanced auto-resize textarea with smooth animation
    function autoResizeTextarea() {
        messageInput.style.height = 'auto';
        const newHeight = Math.min(messageInput.scrollHeight, 120);
        messageInput.style.height = newHeight + 'px';
        
        // Animate the container if needed
        if (newHeight > 50) {
            messageInput.style.transition = 'height 0.2s ease';
        }
    }
    
    // Enhanced scroll to bottom with smooth animation
    function scrollToBottom() {
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });
        
        // Hide scroll button with animation
        scrollToBottomBtn.classList.remove('show');
    }
    
    // Enhanced scroll button visibility with debouncing
    let scrollTimeout;
    function showScrollButton() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            const isScrolledToBottom = chatMessages.scrollTop >= 
                chatMessages.scrollHeight - chatMessages.clientHeight - 100;
            scrollToBottomBtn.classList.toggle('show', !isScrolledToBottom);
        }, 100);
    }
    
    // Enhanced message addition with improved animations
    function addUserMessage(messageText) {
        // Hide conversation starter with smooth animation
        const conversationStarter = document.querySelector('.conversation-starter');
        if (conversationStarter && !conversationStarter.classList.contains('hiding')) {
            conversationStarter.classList.add('hiding');
            setTimeout(() => {
                if (conversationStarter.parentNode) {
                    conversationStarter.remove();
                }
            }, 300);
        }
        
        const userMessage = document.createElement('div');
        userMessage.className = 'message user';
        userMessage.innerHTML = `
            <div class="message-content">${escapeHtml(messageText)}</div>
            <div class="message-timestamp">${formatTime(new Date())}</div>
        `;
        
        // Add with animation
        userMessage.style.opacity = '0';
        userMessage.style.transform = 'translateY(20px) scale(0.95)';
        chatMessages.appendChild(userMessage);
        
        // Trigger animation
        requestAnimationFrame(() => {
            userMessage.style.transition = 'all 0.4s ease-out';
            userMessage.style.opacity = '1';
            userMessage.style.transform = 'translateY(0) scale(1)';
        });
        
        // Show typing indicator with enhanced animation
        typingIndicator.classList.add('show');
        scrollToBottom();
        
        // Vibration disabled
    }
    
    // Enhanced agent message with typing simulation
    function addAgentMessage(messageText) {
        // Hide typing indicator
        typingIndicator.classList.remove('show');
        
        const agentMessage = document.createElement('div');
        agentMessage.className = 'message agent';
        agentMessage.innerHTML = `
            <div class="message-content">${escapeHtml(messageText)}</div>
            <div class="message-timestamp">${formatTime(new Date())}</div>
        `;
        
        // Add with enhanced animation
        agentMessage.style.opacity = '0';
        agentMessage.style.transform = 'translateY(20px) scale(0.95)';
        chatMessages.appendChild(agentMessage);
        
        // Trigger animation with slight delay for realism
        setTimeout(() => {
            requestAnimationFrame(() => {
                agentMessage.style.transition = 'all 0.4s ease-out';
                agentMessage.style.opacity = '1';
                agentMessage.style.transform = 'translateY(0) scale(1)';
            });
        }, 200);
        
        scrollToBottom();
    }
    
    // Enhanced send message with better error handling
    async function sendMessage(event) {
        event.preventDefault();
        
        const messageText = messageInput.value.trim();
        if (!messageText) {
            // Shake animation for empty input
            messageInput.style.animation = 'shakeError 0.5s ease-in-out';
            setTimeout(() => {
                messageInput.style.animation = '';
            }, 500);
            return;
        }
        
        // For now, let's use the traditional form submission approach
        // since the backend is designed for it
        const form = event.target.closest('form');
        if (form) {
            // Add user message visually before submission
            addUserMessage(messageText);
            
            // Submit the form normally - this will cause a page reload
            // which is what the backend expects
            form.submit();
            return;
        }
        
        // Enhanced button state management for fallback AJAX approach
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<div class="loading-spinner"></div>';
        sendBtn.classList.add('loading');
        
        addUserMessage(messageText);
        messageInput.value = '';
        autoResizeTextarea();
        
        try {
            // Get lead_id from URL
            const pathParts = window.location.pathname.split('/');
            const leadId = pathParts[pathParts.length - 1];
            
            if (!leadId || leadId === 'conversation') {
                throw new Error('Lead ID not found');
            }
            
            // Enhanced fetch with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            const response = await fetch(`/conversation/${leadId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `message=${encodeURIComponent(messageText)}`,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                const html = await response.text();
                
                // Extract response from the HTML
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                
                // Look for the response in the message content
                let responseText = '';
                const responseElement = doc.querySelector('.message.agent .message-content');
                
                if (responseElement) {
                    responseText = responseElement.innerHTML; // Use innerHTML to preserve formatting
                } else {
                    // Fallback - look for any meaningful content
                    const bodyContent = doc.body?.textContent || '';
                    const lines = bodyContent.split('\n').map(line => line.trim()).filter(line => line.length > 10);
                    responseText = lines.find(line => !line.includes('<!DOCTYPE') && !line.includes('AI Sales Assistant')) || 
                                 'Thank you for your message!';
                }
                
                addAgentMessage(responseText);
            } else {
                throw new Error(`Server error: ${response.status}`);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            let errorMessage = 'Sorry, I encountered an error. Please try again.';
            
            if (error.name === 'AbortError') {
                errorMessage = 'Request timed out. Please check your connection and try again.';
            } else if (error.message.includes('Lead ID')) {
                errorMessage = 'Session error. Please refresh the page and try again.';
            }
            
            addAgentMessage(errorMessage);
        } finally {
            // Reset button state with animation
            setTimeout(() => {
                sendBtn.disabled = false;
                sendBtn.innerHTML = '→';
                sendBtn.classList.remove('loading');
                messageInput.focus();
            }, 300);
        }
    }
    
    // Enhanced message setting with animation
    function setMessage(text) {
        messageInput.value = text;
        messageInput.focus();
        autoResizeTextarea();
        
        // Add subtle highlight animation
        messageInput.style.background = 'var(--primary-light)';
        setTimeout(() => {
            messageInput.style.background = '';
        }, 500);
    }
    
    // Enhanced event listeners
    messageInput.addEventListener('input', debounce(autoResizeTextarea, 50));
    
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            // Submit the form normally
            const chatForm = document.getElementById('chatForm');
            if (chatForm && messageInput.value.trim()) {
                chatForm.submit();
            }
        }
        
        // Add typing indicator for real-time feedback
        if (e.key !== 'Enter') {
            showTypingFeedback();
        }
    });
    
    // For non-AJAX form submission, just add visual feedback
    const chatForm = document.getElementById('chatForm');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            // Don't prevent default - let form submit normally
            const messageText = messageInput.value.trim();
            if (messageText) {
                // Add visual feedback before submission
                sendBtn.disabled = true;
                sendBtn.innerHTML = '<div class="loading-spinner"></div>';
                sendBtn.classList.add('loading');
            }
        });
    }
    
    chatMessages.addEventListener('scroll', debounce(showScrollButton, 100));
    
    scrollToBottomBtn.addEventListener('click', scrollToBottom);
    
    // Enhanced quick action buttons
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const message = this.textContent.replace(/^[^\w]*/, '').trim();
            setMessage(message);
            
            // Add click animation
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
        

    });
    
    // Initialize chat state
    messageInput.focus();
    setTimeout(scrollToBottom, 300);
    
    // Make functions available globally
    window.setMessage = setMessage;
    window.scrollToBottom = scrollToBottom;
}

// Enhanced Landing page functionality
function initializeLandingPage() {
    const form = document.querySelector('form');
    const inputs = document.querySelectorAll('.form-input');
    const submitButton = document.querySelector('.start-button');
    
    // Enhanced floating label effect
    inputs.forEach(input => {
        // Add focus management with improved animations
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
            this.style.transform = 'translateY(-2px)';
        });
        
        input.addEventListener('blur', function() {
            if (!this.value) {
                this.parentElement.classList.remove('focused');
            }
            this.style.transform = '';
        });
        
        // Enhanced input validation with visual feedback
        input.addEventListener('input', function() {
            validateInput(this);
        });
        
        // Check if input has value on load
        if (input.value) {
            input.parentElement.classList.add('focused');
        }
    });
    
    // Enhanced form validation with better UX
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        let isValid = true;
        const errors = [];
        
        inputs.forEach(input => {
            if (input.required && !input.value.trim()) {
                isValid = false;
                input.classList.add('error');
                errors.push(`${input.previousElementSibling.textContent} is required`);
                
                // Shake animation
                input.style.animation = 'shakeError 0.5s ease-in-out';
                setTimeout(() => {
                    input.style.animation = '';
                    input.classList.remove('error');
                }, 500);
            } else {
                input.classList.remove('error');
            }
        });
        
        if (isValid) {
            // Enhanced submit animation
            submitButton.classList.add('loading');
            submitButton.innerHTML = '<div class="loading-spinner"></div> Starting...';
            
            // Store lead ID for later use
            const leadIdInput = document.getElementById('lead_id');
            if (leadIdInput) {
                sessionStorage.setItem('leadId', leadIdInput.value);
            }
            
            // Submit after animation
            setTimeout(() => {
                // Create form data and submit
                const formData = new FormData(form);
                
                // Use fetch to submit the form
                fetch(form.action, {
                    method: 'POST',
                    body: formData
                }).then(response => {
                    if (response.ok) {
                        window.location.href = response.url;
                    } else {
                        throw new Error('Form submission failed');
                    }
                }).catch(error => {
                    console.error('Form submission error:', error);
                    submitButton.classList.remove('loading');
                    submitButton.innerHTML = 'Start Conversation 🚀';
                    showFormErrors(['An error occurred. Please try again.']);
                });
            }, 800);
        } else {
            // Show errors with better UX
            showFormErrors(errors);
        }
    });
    
    // Add enter key support
    inputs.forEach(input => {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                form.dispatchEvent(new Event('submit'));
            }
        });
    });
}

// Form validation helpers
function validateInput(input) {
    const value = input.value.trim();
    const name = input.name;
    
    // Clear previous error state
    input.classList.remove('error', 'warning');
    
    if (!value && input.required) {
        return false;
    }
    
    // Specific validation rules
    switch (name) {
        case 'name':
            if (value.length < 2) {
                input.classList.add('warning');
                return false;
            }
            break;
        case 'lead_id':
            if (value.length < 3) {
                input.classList.add('warning');
                return false;
            }
            break;
    }
    
    // Add success state
    if (value) {
        input.classList.add('valid');
    }
    
    return true;
}

function showFormErrors(errors) {
    // Remove existing error messages
    const existingError = document.querySelector('.form-error-message');
    if (existingError) {
        existingError.remove();
    }
    
    if (errors.length > 0) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'form-error-message error-message';
        errorDiv.innerHTML = errors.join('<br>');
        
        const form = document.querySelector('form');
        form.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }
}

// Exit page functionality (enhanced)
function initializeExitPage() {
    const countdownElement = document.querySelector('.countdown');
    const redirectUrl = document.querySelector('[data-redirect-url]')?.dataset.redirectUrl;
    
    if (countdownElement && redirectUrl) {
        let seconds = 10;
        
        const countdownInterval = setInterval(() => {
            countdownElement.textContent = seconds;
            seconds--;
            
            if (seconds < 0) {
                clearInterval(countdownInterval);
                window.location.href = redirectUrl;
            }
        }, 1000);
        
        // Add manual navigation options
        const skipButton = document.createElement('button');
        skipButton.textContent = 'Continue Now';
        skipButton.className = 'btn';
        skipButton.addEventListener('click', () => {
            clearInterval(countdownInterval);
            window.location.href = redirectUrl;
        });
        
        const exitCard = document.querySelector('.exit-card');
        if (exitCard) {
            exitCard.appendChild(skipButton);
        }
    }
}

// Enhanced utility functions
function formatTime(date) {
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Enhanced debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Page transition effects
function initializePageTransitions() {
    // Add page load animation
    document.body.style.opacity = '0';
    window.addEventListener('load', () => {
        document.body.style.transition = 'opacity 0.5s ease-in';
        document.body.style.opacity = '1';
    });
}

// Smooth scrolling for internal links
function initializeSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Audio feedback functions (disabled)
function playNotificationSound() {
    // Sound disabled
    return;
}

function playClickSound() {
    // Sound disabled
    return;
}

// Show typing feedback
function showTypingFeedback() {
    // Add a subtle visual cue when user is typing
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.style.borderColor = 'var(--primary-color)';
        clearTimeout(window.typingTimeout);
        window.typingTimeout = setTimeout(() => {
            messageInput.style.borderColor = '';
        }, 1000);
    }
}

// Add CSS for loading spinner and form states
const enhancedStyles = document.createElement('style');
enhancedStyles.textContent = `
    .loading-spinner {
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        border-radius: 50%;
        border-top-color: #fff;
        animation: spin 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    .form-input.error {
        border-color: var(--danger-color) !important;
        box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1) !important;
    }
    
    .form-input.warning {
        border-color: var(--accent-color) !important;
    }
    
    .form-input.valid {
        border-color: var(--secondary-color) !important;
    }
    
    .form-error-message {
        margin-top: 1rem;
        animation: slideDown 0.3s ease-out;
    }
    
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(enhancedStyles);



// Service Worker registration for PWA capabilities
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
} 