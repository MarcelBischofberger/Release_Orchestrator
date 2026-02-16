from flask import Flask, request, jsonify
from datetime import datetime
import logging

app = Flask(__name__)

import argparse

# Parse arguments
parser = argparse.ArgumentParser(description='Deployment Agent Server')
parser.add_argument('--port', type=int, default=5001, help='Port to run the agent on')
parser.add_argument('--name', type=str, default='Default-Agent', help='Agent/Environment Name')
args = parser.parse_args()

AGENT_NAME = args.name
PORT = args.port

# Configure logging
logging.basicConfig(level=logging.INFO, format=f'%(asctime)s - [%(levelname)s] - [{AGENT_NAME}] - %(message)s')
logger = logging.getLogger(__name__)

# In-memory history
history = []

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Deployment Agent",
        "name": AGENT_NAME,
        "history_count": len(history)
    })

@app.route('/distribute', methods=['POST'])
def distribute():
    data = request.json
    package_name = data.get('package')
    nexus_url = data.get('nexus_url')
    release_name = data.get('release')
    
    timestamp = datetime.utcnow().isoformat()
    
    logger.info(f"DISTRIBUTE STARTED: Release={release_name}, Package={package_name}, URL={nexus_url}")
    
    # Simulate work...
    
    logger.info(f"DISTRIBUTE COMPLETED: Release={release_name}, Package={package_name}")
    
    record = {
        "type": "distribute",
        "timestamp": timestamp,
        "package": package_name,
        "release": release_name,
        "status": "success",
        "agent": AGENT_NAME
    }
    history.append(record)
    
    return jsonify({"status": "success", "message": f"Distribution of {package_name} completed on {AGENT_NAME}"}), 200

@app.route('/deploy', methods=['POST'])
def deploy():
    data = request.json
    package_name = data.get('package')
    nexus_url = data.get('nexus_url')
    release_name = data.get('release')
    
    timestamp = datetime.utcnow().isoformat()
    
    logger.info(f"DEPLOY STARTED: Release={release_name}, Package={package_name}")
    
    # Simulate work...
    
    logger.info(f"DEPLOY COMPLETED: Release={release_name}, Package={package_name}")
    
    record = {
        "type": "deploy",
        "timestamp": timestamp,
        "package": package_name,
        "release": release_name,
        "status": "success",
        "agent": AGENT_NAME
    }
    history.append(record)
    
    return jsonify({"status": "success", "message": f"Deployment of {package_name} completed on {AGENT_NAME}"}), 200

@app.route('/history', methods=['GET'])
def get_history():
    return jsonify(history)

if __name__ == '__main__':
    print(f"Agent Server '{AGENT_NAME}' running on port {PORT}...")
    app.run(port=PORT, debug=True, use_reloader=False)
