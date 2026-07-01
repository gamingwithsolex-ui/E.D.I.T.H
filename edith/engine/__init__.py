import asyncio
import logging
from edith.core import EdithConfig

logger = logging.getLogger("edith.engine")

class EdithEngine:
    """
    The central runtime execution engine for E.D.I.T.H.
    Coordinates agent initialization, manages event loops, and delegates tasks.
    """
    def __init__(self, config: EdithConfig):
        self.config = config
        self.is_running = False
        logger.info(f"EdithEngine initialized under '{self.config.env}' environment.")

    def run(self):
        """
        Synchronously start the execution loop.
        """
        self.is_running = True
        logger.info(f"EdithEngine server listening on {self.config.host}:{self.config.port}...")
        
        try:
            if self.config.daemon_mode:
                logger.info("Daemon execution loop started. Running in background...")
                # Simulate daemon block
                while self.is_running:
                    import time
                    time.sleep(1)
            else:
                logger.info("Interactive execution session started. Press Ctrl+C to terminate.")
                # Run the event loop for async operations
                asyncio.run(self._interactive_loop())
        except KeyboardInterrupt:
            logger.info("Termination signal received. Shutting down gracefully...")
        finally:
            self.stop()

    async def _interactive_loop(self):
        """
        Simple command loop for interactive console sessions.
        """
        while self.is_running:
            # Simple simulation of processing commands
            await asyncio.sleep(0.5)

    def stop(self):
        """
        Stops the execution loop and frees resources.
        """
        if self.is_running:
            self.is_running = False
            logger.info("EdithEngine stopped successfully.")
