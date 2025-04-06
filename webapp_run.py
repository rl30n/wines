import logging
import sys
from app import create_app

# Configurar logging en formato ECS y activar modo debug
def setup_logging(debug=False):
    log_level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    
    # Activar logging en ECS
    ecs_handler = logging.FileHandler('logs/webapp.log')
    ecs_handler.setFormatter(logging.Formatter('{"@timestamp":"%(asctime)s", "log.level": "%(levelname)s", "message": "%(message)s"}'))
    
    logging.basicConfig(level=log_level, handlers=[handler, ecs_handler])
    logging.debug("Logging setup complete")

app = create_app()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the web application")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging")
    args = parser.parse_args()
    
    # Configurar logging según el parámetro --debug
    setup_logging(debug=args.debug)

    app.run(debug=args.debug, host='0.0.0.0', port=5001)