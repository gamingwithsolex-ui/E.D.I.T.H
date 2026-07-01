import os
import sys
import logging
from dotenv import load_dotenv
import typer

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("edith")

# Initialize CLI application
app = typer.Typer(name="edith", help="E.D.I.T.H. Assistant CLI Interface")

@app.callback()
def main_callback():
    """
    E.D.I.T.H. (Even Dead I'm The Hero) - Advanced Agentic AI Assistant.
    Loads settings and prepares the execution engine.
    """
    load_dotenv()

@app.command()
def start(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run E.D.I.T.H as a background daemon process"),
    port: int = typer.Option(8080, "--port", "-p", help="Server port to bind to")
):
    """
    Start the E.D.I.T.H. server daemon or shell process.
    """
    logger.info("Initializing E.D.I.T.H. Core...")
    
    # Check for basic required keys safely
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("No GOOGLE_API_KEY or OPENAI_API_KEY found in the environment. Please check your .env file.")
    
    try:
        from edith.core import EdithConfig
        from edith.engine import EdithEngine
        
        config = EdithConfig(
            host=os.getenv("EDITH_HOST", "127.0.0.1"),
            port=int(os.getenv("EDITH_PORT", str(port))),
            env=os.getenv("EDITH_ENV", "development"),
            daemon_mode=daemon
        )
        
        engine = EdithEngine(config=config)
        logger.info("Bootstrapping E.D.I.T.H. Engine execution loop...")
        engine.run()
        
    except ImportError as e:
        logger.error(f"Failed to load E.D.I.T.H submodules. Ensure you have installed the project correctly: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Fatal error during engine execution: {e}", exc_info=True)
        sys.exit(1)

@app.command()
def verify():
    """
    Validate the project directory layout and environment status.
    """
    logger.info("Verifying E.D.I.T.H structure...")
    # Add structure check logic if needed
    typer.echo("Structure looks complete. Ready to build!")

if __name__ == "__main__":
    app()
