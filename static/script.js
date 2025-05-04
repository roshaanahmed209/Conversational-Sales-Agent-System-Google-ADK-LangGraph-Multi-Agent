document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.querySelector('.chat-container');
    const messageForm = document.querySelector('.message-form');
    const messageInput = document.querySelector('.message-input');
    const clearButton = document.querySelector('.clear-chat') || document.getElementById('clear-button');
    
    // Add system welcome message with typing animation
    const welcomeMessage = "Hello! I'm your sales assistant. How can I help you today?";
    
    // Check if there's an initial message from the server
    const initialMessageEl = document.getElementById('initial-message');
    if (initialMessageEl && initialMessageEl.textContent.trim() !== '') {
        const initialMessage = initialMessageEl.textContent.trim();
        addTypingAnimation('assistant', initialMessage);
    } else {
        addTypingAnimation('assistant', welcomeMessage);
    }
    
    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        const scrollHeight = messageInput.scrollHeight;
        messageInput.style.height = `${Math.min(scrollHeight, 150)}px`;
    });
    
    // Handle message submission
    messageForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // Prevent the default form submission
        const userMessage = messageInput.value.trim();
        
        if (!userMessage) return;
        
        // Add user message to chat with appear animation
        addMessageToChat('user', userMessage, true);
        
        // Clear and reset input
        messageInput.value = '';
        messageInput.style.height = 'auto';
        messageInput.focus();
        
        // Show typing indicator
        const typingIndicator = createTypingIndicator();
        chatContainer.appendChild(typingIndicator);
        scrollToBottom();
        
        try {
            // Get lead ID for request
            const leadId = document.getElementById('lead-id')?.textContent.trim() || 
                         sessionStorage.getItem('lead_id') || '';
            
            if (!leadId) {
                throw new Error('Missing lead ID. Please start a new conversation.');
            }
            
            // Send request to backend
            const response = await fetch(`/chat?lead_id=${encodeURIComponent(leadId)}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: userMessage,
                    lead_id: leadId 
                }),
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Check for error in response
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Check if data contains an action to redirect
            if (data.action === 'redirect') {
                // Add a goodbye message
                addMessageToChat('assistant', data.response);
                
                // Wait a moment before redirecting
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 2000);
                return; // Stop further processing
            }
            
            // Remove typing indicator
            typingIndicator.remove();
            
            // Add assistant message to chat with typing animation
            addTypingAnimation('assistant', data.response);
            
        } catch (error) {
            console.error('Error sending message:', error);
            
            // Remove typing indicator
            typingIndicator.remove();
            
            // Determine error message to show to user
            let errorMessage = 'Sorry, there was an error processing your request. Please try again.';
            
            if (error.message.includes('Missing lead ID')) {
                errorMessage = 'Your session has expired. Please refresh the page or start a new conversation.';
                
                // Redirect to home after a delay
                setTimeout(() => {
                    window.location.href = '/';
                }, 3000);
            } else if (error.message.includes('HTTP error')) {
                errorMessage = 'Unable to reach the server. Please check your connection and try again.';
            }
            
            // Show error message
            addMessageToChat('assistant', errorMessage);
        }
    });
    
    // Clear chat functionality
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            // Fade out and remove messages
            const allMessages = chatContainer.querySelectorAll('.message-group');
            
            allMessages.forEach((msg, index) => {
                msg.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                msg.style.opacity = '0';
                msg.style.transform = 'translateY(20px)';
                
                setTimeout(() => {
                    msg.remove();
                    
                    // If all messages are removed, add welcome message again
                    if (index === allMessages.length - 1) {
                        setTimeout(() => {
                            addTypingAnimation('assistant', welcomeMessage);
                        }, 300);
                    }
                }, 300);
            });
        });
    }
    
    // Send button behavior - enable/disable based on input
    const sendButton = messageForm.querySelector('button[type="submit"]');
    
    // Initial state
    sendButton.disabled = messageInput.value.trim() === '';
    
    messageInput.addEventListener('input', () => {
        sendButton.disabled = messageInput.value.trim() === '';
        if (messageInput.value.trim() === '') {
            sendButton.classList.add('disabled');
        } else {
            sendButton.classList.remove('disabled');
        }
    });
    
    // Enter to send, Shift+Enter for new line
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (messageInput.value.trim() !== '') {
                messageForm.dispatchEvent(new Event('submit'));
            }
        }
    });
    
    /**
     * Creates a message element and adds it to the chat
     * @param {string} role - 'user' or 'assistant'
     * @param {string} content - The message content
     * @param {boolean} animate - Whether to animate the message appearance
     */
    function addMessageToChat(role, content, animate = false) {
        const messageGroup = document.createElement('div');
        messageGroup.className = `message-group ${role}`;
        
        if (animate) {
            messageGroup.style.opacity = '0';
            messageGroup.style.transform = 'translateY(20px)';
        }
        
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = content;
        
        messageBubble.appendChild(messageContent);
        messageGroup.appendChild(messageBubble);
        chatContainer.appendChild(messageGroup);
        
        scrollToBottom();
        
        if (animate) {
            setTimeout(() => {
                messageGroup.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                messageGroup.style.opacity = '1';
                messageGroup.style.transform = 'translateY(0)';
            }, 10);
        }
        
        return messageGroup;
    }
    
    /**
     * Adds a message with typing animation
     * @param {string} role - 'user' or 'assistant'
     * @param {string} content - The message content
     */
    function addTypingAnimation(role, content) {
        const messageGroup = document.createElement('div');
        messageGroup.className = `message-group ${role}`;
        
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = '';
        
        messageBubble.appendChild(messageContent);
        messageGroup.appendChild(messageBubble);
        chatContainer.appendChild(messageGroup);
        
        scrollToBottom();
        
        // Type out the message character by character
        let i = 0;
        const typingSpeed = Math.max(20, Math.min(50, 1000 / content.length)); // Dynamic typing speed
        
        const typeNextChar = () => {
            if (i < content.length) {
                messageContent.textContent += content.charAt(i);
                i++;
                scrollToBottom();
                setTimeout(typeNextChar, typingSpeed);
            }
        };
        
        typeNextChar();
        
        return messageGroup;
    }
    
    /**
     * Creates a system message element
     * @param {string} content - The system message content
     * @returns {HTMLElement} - The system message element
     */
    function createSystemMessage(content) {
        const messageGroup = document.createElement('div');
        messageGroup.className = 'message-group system assistant';
        
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = content;
        
        messageBubble.appendChild(messageContent);
        messageGroup.appendChild(messageBubble);
        
        return messageGroup;
    }
    
    /**
     * Creates a typing indicator element
     * @returns {HTMLElement} - The typing indicator element
     */
    function createTypingIndicator() {
        const messageGroup = document.createElement('div');
        messageGroup.className = 'message-group assistant typing';
        
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        
        const typingDots = document.createElement('div');
        typingDots.className = 'typing-dots';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            typingDots.appendChild(dot);
        }
        
        messageBubble.appendChild(typingDots);
        messageGroup.appendChild(messageBubble);
        
        return messageGroup;
    }
    
    /**
     * Scrolls the chat container to the bottom
     */
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Focus input field on page load
    setTimeout(() => messageInput.focus(), 500);
}); 