import aiohttp
import asyncio
import json
import sys
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('c2_tester')

class C2Tester:
    def __init__(self, server_url):
        """
        Initialize the C2 tester with the server URL
        
        Args:
            server_url (str): Base URL of the C2 server
        """
        self.server_url = server_url
    
    async def list_clients(self):
        """
        Retrieve a list of all registered clients
        
        Returns:
            list: Client IDs connected to the server
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/api/clients") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('clients', [])
                    else:
                        logger.error(f"Failed to list clients. Status: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error listing clients: {e}")
            return []
    
    async def send_command(self, client_id, command):
        """
        Send a command to a specific client
        
        Args:
            client_id (str): ID of the target client
            command (str): Command to execute
        
        Returns:
            str or None: Command ID if successful, None otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "client_id": client_id,
                    "command": command
                }
                async with session.post(f"{self.server_url}/api/commands/send", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('cmd_id')
                    else:
                        logger.error(f"Failed to send command. Status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return None
    
    async def get_command_status(self, cmd_id):
        """
        Retrieve the status of a specific command
        
        Args:
            cmd_id (str): ID of the command to check
        
        Returns:
            dict or None: Command details if found, None otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/api/commands/{cmd_id}") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Failed to get command status. Status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting command status: {e}")
            return None
    
    async def wait_for_command_completion(self, cmd_id, timeout=60):
        """
        Wait for a command to complete and return its result
        
        Args:
            cmd_id (str): ID of the command to wait for
            timeout (int): Maximum time to wait in seconds
        
        Returns:
            dict or None: Command result if completed, None if timed out
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            status = await self.get_command_status(cmd_id)
            
            if not status:
                logger.error(f"Command {cmd_id} not found")
                return None
            
            if status.get('status') == 'completed':
                return status.get('result')
            
            await asyncio.sleep(1)
        
        logger.warning(f"Command {cmd_id} timed out after {timeout} seconds")
        return None

async def interactive_shell(tester):
    """
    Interactive shell for testing the C2 system
    
    Args:
        tester (C2Tester): Initialized C2 tester instance
    """
    print("\n===== C2 Tester Interactive Shell =====")
    print("Type 'help' for a list of available commands")
    
    while True:
        try:
            # Get user input
            command = input("\nC2> ").strip()
            
            # Skip empty inputs
            if not command:
                continue
            
            # Exit commands
            if command in ['exit', 'quit', 'q']:
                break
            
            # Help command
            if command == 'help':
                print("\nAvailable Commands:")
                print("  clients         - List all connected clients")
                print("  send <client_id> <command>  - Send a command to a specific client")
                print("  status <cmd_id> - Check the status of a specific command")
                print("  wait <cmd_id>   - Wait for a command to complete")
                print("  exit/quit       - Exit the tester")
                continue
            
            # List clients
            if command == 'clients':
                clients = await tester.list_clients()
                if clients:
                    print("\nConnected Clients:")
                    for client in clients:
                        print(f"  - {client}")
                else:
                    print("No clients connected.")
                continue
            
            # Send command
            if command.startswith('send '):
                parts = command.split(' ', 2)
                if len(parts) != 3:
                    print("Usage: send <client_id> <command>")
                    continue
                
                _, client_id, cmd = parts
                cmd_id = await tester.send_command(client_id, cmd)
                
                if cmd_id:
                    print(f"\nCommand sent successfully!")
                    print(f"Command ID: {cmd_id}")
                    
                    # Automatically wait for result
                    result = await tester.wait_for_command_completion(cmd_id)
                    
                    if result:
                        print("\nCommand Result:")
                        if isinstance(result, dict):
                            if 'stdout' in result:
                                print("Standard Output:")
                                print(result.get('stdout', 'No output'))
                            if 'stderr' in result and result.get('stderr'):
                                print("\nStandard Error:")
                                print(result.get('stderr'))
                            if 'exit_code' in result:
                                print(f"\nExit Code: {result.get('exit_code')}")
                        else:
                            print(result)
                    else:
                        print("No result received or command timed out.")
                else:
                    print("Failed to send command.")
                continue
            
            # Status command
            if command.startswith('status '):
                parts = command.split(' ')
                if len(parts) != 2:
                    print("Usage: status <cmd_id>")
                    continue
                
                cmd_id = parts[1]
                status = await tester.get_command_status(cmd_id)
                
                if status:
                    print("\nCommand Status:")
                    print(json.dumps(status, indent=2))
                else:
                    print(f"No status found for command {cmd_id}")
                continue
            
            # Wait command
            if command.startswith('wait '):
                parts = command.split(' ')
                if len(parts) != 2:
                    print("Usage: wait <cmd_id>")
                    continue
                
                cmd_id = parts[1]
                result = await tester.wait_for_command_completion(cmd_id)
                
                if result:
                    print("\nCommand Result:")
                    if isinstance(result, dict):
                        if 'stdout' in result:
                            print("Standard Output:")
                            print(result.get('stdout', 'No output'))
                        if 'stderr' in result and result.get('stderr'):
                            print("\nStandard Error:")
                            print(result.get('stderr'))
                        if 'exit_code' in result:
                            print(f"\nExit Code: {result.get('exit_code')}")
                    else:
                        print(result)
                else:
                    print("No result received or command timed out.")
                continue
            
            # Unknown command
            print(f"Unknown command: {command}")
            print("Type 'help' for a list of available commands")
        
        except KeyboardInterrupt:
            print("\nExiting tester...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='C2 Tester')
    parser.add_argument('--server', type=str, default='http://localhost:8080', 
                        help='C2 server URL (default: http://localhost:8080)')
    args = parser.parse_args()
    
    # Create tester instance
    tester = C2Tester(args.server)
    
    # Start interactive shell
    await interactive_shell(tester)

if __name__ == '__main__':
    asyncio.run(main())
