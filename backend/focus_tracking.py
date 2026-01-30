import time

class FocusTracker:
    def __init__(self):
        self.instagram_switches = 0
        self.is_tracking = False
        self.start_time = None
    
    def start_tracking(self):
        """Start focus tracking"""
        self.is_tracking = True
        self.start_time = time.time()
        self.instagram_switches = 0
    
    def stop_tracking(self):
        """Stop focus tracking"""
        self.is_tracking = False
    
    def record_instagram_switch(self):
        """Record an Instagram switch"""
        if self.is_tracking:
            self.instagram_switches += 1
    
    def get_stats(self):
        """Get current focus tracking statistics"""
        elapsed_time = 0
        if self.start_time and self.is_tracking:
            elapsed_time = int(time.time() - self.start_time)
        
        return {
            'instagram_switches': self.instagram_switches,
            'elapsed_time': elapsed_time,
            'is_tracking': self.is_tracking
        }

# Global tracker instance
focus_tracker = FocusTracker()