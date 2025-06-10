// Mobile bottom sheet functionality for responsive UI
class MobileSheet {
    constructor() {
        this.sheet = null;
        this.handle = null;
        this.content = null;
        this.startY = 0;
        this.currentY = 0;
        this.isDragging = false;
        this.startTime = 0;
        this.velocity = 0;
        
        // Sheet states and positions
        this.states = {
            collapsed: { height: 120, name: 'collapsed' },
            half: { height: 50, name: 'half' }, // 50% of viewport
            full: { height: 85, name: 'full' }   // 85% of viewport
        };
        
        this.currentState = 'collapsed';
        this.snapThreshold = 50; // pixels to trigger snap
        this.velocityThreshold = 0.5; // velocity to trigger state change
        
        // Bind methods
        this.handleTouchStart = this.handleTouchStart.bind(this);
        this.handleTouchMove = this.handleTouchMove.bind(this);
        this.handleTouchEnd = this.handleTouchEnd.bind(this);
        this.handleResize = this.handleResize.bind(this);
    }
    
    initialize() {
        // Get DOM elements
        this.sheet = document.querySelector('.control-panel');
        if (!this.sheet) return;
        
        // Add mobile sheet classes
        this.sheet.classList.add('mobile-bottom-sheet');
        
        // Create and insert drag handle
        this.createDragHandle();
        
        // Wrap existing content
        this.wrapContent();
        
        // Set initial state
        this.setState('collapsed');
        
        // Add event listeners
        this.addEventListeners();
        
        // Handle keyboard visibility
        this.handleKeyboardVisibility();
    }
    
    createDragHandle() {
        const handle = document.createElement('div');
        handle.className = 'bottom-sheet-handle';
        handle.innerHTML = '<div class="handle-bar"></div>';
        
        // Insert at beginning of sheet
        this.sheet.insertBefore(handle, this.sheet.firstChild);
        this.handle = handle;
    }
    
    wrapContent() {
        // Get all children except the handle
        const children = Array.from(this.sheet.children).filter(child => 
            !child.classList.contains('bottom-sheet-handle')
        );
        
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'bottom-sheet-content';
        
        // Move children to wrapper
        children.forEach(child => wrapper.appendChild(child));
        
        // Append wrapper
        this.sheet.appendChild(wrapper);
        this.content = wrapper;
    }
    
    addEventListeners() {
        // Touch events on handle and sheet
        this.handle.addEventListener('touchstart', this.handleTouchStart, { passive: true });
        this.handle.addEventListener('touchmove', this.handleTouchMove, { passive: false });
        this.handle.addEventListener('touchend', this.handleTouchEnd, { passive: true });
        
        // Also allow dragging from sheet header area
        const logoSection = this.sheet.querySelector('.logo-section');
        if (logoSection) {
            logoSection.addEventListener('touchstart', this.handleTouchStart, { passive: true });
            logoSection.addEventListener('touchmove', this.handleTouchMove, { passive: false });
            logoSection.addEventListener('touchend', this.handleTouchEnd, { passive: true });
        }
        
        // Window resize
        window.addEventListener('resize', this.handleResize);
        
        // Prevent pull-to-refresh when scrolling in sheet
        this.content.addEventListener('touchmove', (e) => {
            if (this.content.scrollTop > 0) {
                e.stopPropagation();
            }
        }, { passive: false });
    }
    
    handleTouchStart(e) {
        this.isDragging = true;
        this.startY = e.touches[0].clientY;
        this.startTime = Date.now();
        this.velocity = 0;
        
        // Add dragging class for visual feedback
        this.sheet.classList.add('dragging');
        
        // Store initial transform
        const transform = window.getComputedStyle(this.sheet).transform;
        if (transform !== 'none') {
            const matrix = new DOMMatrix(transform);
            this.currentY = matrix.m42; // translateY value
        } else {
            this.currentY = 0;
        }
    }
    
    handleTouchMove(e) {
        if (!this.isDragging) return;
        
        e.preventDefault(); // Prevent scrolling while dragging
        
        const touchY = e.touches[0].clientY;
        const deltaY = touchY - this.startY;
        
        // Calculate velocity
        const currentTime = Date.now();
        const timeDelta = currentTime - this.startTime;
        if (timeDelta > 0) {
            this.velocity = deltaY / timeDelta;
        }
        
        // Update position with edge resistance
        let newY = this.currentY + deltaY;
        
        // Add resistance at edges
        const maxTranslate = 0;
        const minTranslate = -(window.innerHeight * 0.85);
        
        if (newY > maxTranslate) {
            newY = maxTranslate + (newY - maxTranslate) * 0.2;
        } else if (newY < minTranslate) {
            newY = minTranslate + (newY - minTranslate) * 0.2;
        }
        
        // Apply transform
        this.sheet.style.transform = `translateY(${newY}px)`;
        
        // Update for next move
        this.startY = touchY;
        this.currentY = newY;
        this.startTime = currentTime;
    }
    
    handleTouchEnd(e) {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.sheet.classList.remove('dragging');
        
        // Determine target state based on position and velocity
        const currentTranslateY = this.currentY;
        const viewportHeight = window.innerHeight;
        
        // Convert positions to percentages
        const collapsedY = -(viewportHeight - this.states.collapsed.height);
        const halfY = -(viewportHeight * this.states.half.height / 100);
        const fullY = -(viewportHeight * this.states.full.height / 100);
        
        let targetState = this.currentState;
        
        // Velocity-based detection
        if (Math.abs(this.velocity) > this.velocityThreshold) {
            if (this.velocity > 0) {
                // Swiping down - move to less expanded state
                if (this.currentState === 'full') targetState = 'half';
                else if (this.currentState === 'half') targetState = 'collapsed';
            } else {
                // Swiping up - move to more expanded state
                if (this.currentState === 'collapsed') targetState = 'half';
                else if (this.currentState === 'half') targetState = 'full';
            }
        } else {
            // Position-based detection
            const distToCollapsed = Math.abs(currentTranslateY - collapsedY);
            const distToHalf = Math.abs(currentTranslateY - halfY);
            const distToFull = Math.abs(currentTranslateY - fullY);
            
            if (distToCollapsed < distToHalf && distToCollapsed < distToFull) {
                targetState = 'collapsed';
            } else if (distToHalf < distToFull) {
                targetState = 'half';
            } else {
                targetState = 'full';
            }
        }
        
        // Animate to target state
        this.setState(targetState);
    }
    
    setState(state, animate = true) {
        this.currentState = state;
        
        // Remove all state classes
        Object.keys(this.states).forEach(s => {
            this.sheet.classList.remove(`sheet-${s}`);
        });
        
        // Add new state class
        this.sheet.classList.add(`sheet-${state}`);
        
        // Calculate transform
        const viewportHeight = window.innerHeight;
        let translateY;
        
        if (state === 'collapsed') {
            translateY = viewportHeight - this.states.collapsed.height;
        } else {
            translateY = viewportHeight * (1 - this.states[state].height / 100);
        }
        
        // Apply transform with animation
        if (animate) {
            this.sheet.style.transition = 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        } else {
            this.sheet.style.transition = 'none';
        }
        
        this.sheet.style.transform = `translateY(${translateY}px)`;
        this.currentY = translateY;
        
        // Update sheet data attribute
        this.sheet.setAttribute('data-sheet-state', state);
        
        // Emit custom event
        const event = new CustomEvent('sheetStateChange', { 
            detail: { state, previousState: this.currentState }
        });
        this.sheet.dispatchEvent(event);
    }
    
    expandToShowResults() {
        if (this.currentState === 'collapsed') {
            this.setState('half');
        }
    }
    
    expandFull() {
        this.setState('full');
    }
    
    collapse() {
        this.setState('collapsed');
    }
    
    handleResize() {
        // Recalculate position on resize
        this.setState(this.currentState, false);
    }
    
    handleKeyboardVisibility() {
        // Detect virtual keyboard
        const inputs = this.sheet.querySelectorAll('input, textarea');
        
        inputs.forEach(input => {
            input.addEventListener('focus', () => {
                // Expand sheet when input focused
                if (this.currentState === 'collapsed') {
                    this.setState('half');
                }
                
                // Add class for keyboard adjustments
                this.sheet.classList.add('keyboard-visible');
            });
            
            input.addEventListener('blur', () => {
                // Remove keyboard class after delay
                setTimeout(() => {
                    this.sheet.classList.remove('keyboard-visible');
                }, 100);
            });
        });
    }
    
    // Check if device is mobile
    static isMobile() {
        return window.innerWidth <= 768 || 
               ('ontouchstart' in window) || 
               (navigator.maxTouchPoints > 0);
    }
}

// Export for use in other modules
window.MobileSheet = MobileSheet;