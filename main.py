import os
import requests
import logging
import json
from dotenv import load_dotenv
from datetime import datetime
import subprocess
import platform
from db_utils import Database

# Load environment variables from .env file
load_dotenv()
url = os.getenv('API_URL')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ping_log_tracker.log'
)
logger = logging.getLogger(__name__)

class SiteInfoFetcher:
    def __init__(self, api_url):
        self.api_url = api_url
        
    def fetch_site_info(self):
        try:
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()  # Raise an error for bad responses
            
            data = response.json()
            logger.info(f"Successfully fetched site info: {len(data['data'])} records")
            
            # Filter to get site_name, ip_address, pr_code, status_sites
            filtered_data = [
                {
                    'pr_code': site.get('pr_code'),
                    'site_name': site.get('site_name'),
                    'ip_address': site.get('ip_site'),
                    'status_sites': site.get('status_sites'),
                } for site in data['data'] if site.get('status_sites') == 'Active'
            ]
            
            with open('site_info.json', 'w') as f:
                json.dump(filtered_data, f, indent=2)
                logger.info("Site info saved to site_info.json")
            
            logger.info(f"Total Site Active: {len(filtered_data)} records")
            return filtered_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching site info: {e}")
            try:
                logger.info("Attempting to load site info from local file")
                with open('site_info.json', 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded site info from site_info.json: {len(data)} records")
                    return data
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Error loading site info from local file: {e}")
                return []
    
    def process_sites(self):
        """Filtering and processing site info with enhanced logging data"""
        site_data = self.fetch_site_info()
        
        if not site_data:
            logger.warning("No sites available to process")
            return []
        
        results = []
        sites = site_data
        
        logger.info(f"Starting to process {len(sites)} sites")
        successful_sites = 0
        failed_sites = 0
        
        for site in sites:
            if not isinstance(site, dict):
                logger.warning(f"Skipping invalid site data: {site}")
                continue
                
            ip_address = site.get('ip_address') or site.get('ip_site')
            site_name = site.get('site_name')
            pr_code = site.get('pr_code', 'UNKNOWN')
            
            if not ip_address:
                logger.warning(f"No IP address found for site: {site_name}")
                continue
                
            try:
                # Create timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Step 1: Ping the site
                logger.info(f"Pinging site {site_name} at {ip_address}")
                ping_result = self.ping_site(ip_address)
                
                # Step 2: If ping is successful, try to get loggers length
                length_loggers_data = None
                if ping_result.get('success', False):
                    logger.info(f"Checking loggers for {site_name} at {ip_address}")
                    logger_result = self.length_loggers_site(ip_address)
                    if logger_result.get('success', False):
                        length_loggers_data = logger_result.get('data')
                        logger.info(f"Found {length_loggers_data} loggers for {site_name}")
                    else:
                        logger.error(f"Failed to get loggers for {site_name}: {logger_result.get('error', 'Unknown error')}")
                
                # Prepare ping data
                ping_success = ping_result.get('success', False)
                ping_time_ms = ping_result.get('response_time')
                
                # Convert to int for database
                if ping_time_ms is not None:
                    ping_time_ms = int(ping_time_ms)
                
                # Insert data to database in a transaction
                try:
                    # Insert ping_log
                    success_ping_log = Database.insert_ping_log(
                        timestamp=timestamp,
                        pr_code=pr_code, 
                        site_name=site_name,
                        ip_address=ip_address,
                        ping_success=ping_success,
                        ping_time_ms=ping_time_ms,
                    )
                    
                    # Insert length_loggers data
                    success_length_loggers = True  # Default to True for cases with no logger data
                    if ping_success:  # Only try to insert length_loggers if ping was successful
                        success_length_loggers = Database.insert_length_loggers(
                            pr_code=pr_code, 
                            site_name=site_name,
                            ip_address=ip_address,
                            length_loggers=length_loggers_data,
                        )
                    
                    if success_ping_log and success_length_loggers:
                        logger.info(f"Successfully logged data for {site_name}")
                        successful_sites += 1
                    else:
                        failed_operations = []
                        if not success_ping_log:
                            failed_operations.append("ping log")
                        if not success_length_loggers:
                            failed_operations.append("loggers data")
                        
                        logger.error(f"Failed to log {', '.join(failed_operations)} for {site_name}")
                        failed_sites += 1
                    
                except Exception as db_error:
                    logger.error(f"Database error for {site_name}: {db_error}")
                    failed_sites += 1
                
                # Build result object for JSON output regardless of database success
                result = {
                    'timestamp': timestamp,
                    'pr_code': pr_code,
                    'site_name': site_name,
                    'ip_address': ip_address,
                    'ping_success': ping_success,
                    'ping_time_ms': ping_time_ms,
                    'length_loggers': length_loggers_data,
                    'saved_to_db': success_ping_log and success_length_loggers
                }
                
                results.append(result)
                
                # Log comprehensive information about this site
                logger_info = f"length_loggers: {length_loggers_data}" if length_loggers_data is not None else ""
                status = "Successfully" if ping_success else "Failed"
                logger.info(f"{status} Site: {site_name} - Ping results: {ping_result} {logger_info}")
                
            except Exception as site_error:
                logger.error(f"Unexpected error processing site {site_name}: {site_error}")
                failed_sites += 1
        
        # Log summary at the end
        logger.info(f"Processing completed: {successful_sites} successful, {failed_sites} failed, {len(results)} total")
        return results
    
    def ping_site(self, ip_address):
        """Ping a site and return results"""
        # First try system ping command (more reliable)
        try:
            system = platform.system().lower()
            
            if system == "windows":
                # Windows ping command
                ping_param = "-n 1 -w 10000"  # 1 packet, 10 second timeout
                command = f"ping {ping_param} {ip_address}"
                ping_output = subprocess.run(command, capture_output=True, text=True, check=False)
                
                if "Reply from" in ping_output.stdout:
                    # Extract time from ping response
                    time_str = ping_output.stdout.split("time=")[1].split("ms")[0].strip() if "time=" in ping_output.stdout else None
                    response_time = float(time_str) if time_str else 0
                    return {
                        "success": True,
                        "response_time": response_time,
                        "method": "system_ping"
                    }
            
            elif system in ("linux", "darwin"):
                # Linux/macOS ping command
                ping_param = "-c 1 -W 10"  # 1 packet, 10 second timeout
                command = f"ping {ping_param} {ip_address}"
                ping_output = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
                
                if " 0% packet loss" in ping_output.stdout:
                    # Extract time from ping response
                    time_str = ping_output.stdout.split("time=")[1].split(" ")[0].strip() if "time=" in ping_output.stdout else None
                    response_time = float(time_str) if time_str else 0
                    return {
                        "success": True,
                        "response_time": response_time,
                        "method": "system_ping"
                    }
                    
            # If system ping fails or we're on an unsupported system, fall back to HTTP request
            logger.info(f"System ping unsuccessful for {ip_address}, trying HTTP request")
            
        except Exception as e:
            logger.error(f"System ping error for {ip_address}: {e}, trying HTTP request")
        
        # Fall back to HTTP request ping
        try:
            start_time = datetime.now()
            response = requests.get(f"http://{ip_address}", timeout=10)
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # Convert to ms
            
            return {
                "success": response.status_code < 400,
                "response_time": response_time,
                "method": "http_request"
            }
            
        except requests.RequestException as e:
            return {
                "success": False,
                "response_time": None,
                "method": "http_request",
                "error": str(e)
            }
    
    def length_loggers_site(self, ip_address):
        """Get length of loggers from a specific IP address"""
        try:
            start_time = datetime.now()
            Headers = {"Authorization": f"Bearer {os.getenv("EHUB_TOKEN")}"}
            response = requests.get(f"http://{ip_address}/api/logger", headers=Headers, timeout=10)
            
            # Ensure response is valid
            response.raise_for_status()
            
            data = response.json()
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # Convert to ms
            
            # Handle different response structures
            if isinstance(data, list):
                loggers_count = len(data)
            else:
                loggers_count = 0
                logger.error(f"Unexpected loggers data structure: {type(data)}")
            
            return {
                "success": True,
                "response_time": response_time,
                "method": "GET",
                "data": loggers_count
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error fetching loggers for {ip_address}: {e}")
            return {
                "success": False,
                "response_time": None,
                "method": "GET",
                "error": str(e)
            }
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"JSON decode error for loggers at {ip_address}: {e}")
            return {
                "success": False,
                "response_time": None,
                "method": "GET",
                "error": f"Invalid JSON response: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching loggers for {ip_address}: {e}")
            return {
                "success": False,
                "response_time": None,
                "method": "GET",
                "error": str(e)
            }

def main():
    try:
        # Initialize the database (create tables if needed)
        try:
            Database.create_tables()
            logger.info("Database initialized successfully")
        except Exception as db_error:
            logger.error(f"Database initialization failed: {db_error}")
            # Continue execution, we'll still save to JSON
        
        # Initialize the fetcher with the API URL
        fetcher = SiteInfoFetcher(url)
        
        # Process sites (fetch, filter and ping)
        results = fetcher.process_sites()
        
        if results:
            logger.info(f"Successfully processed {len(results)} sites")
            
            # Save results to a file with proper error handling (as backup)
            try:
                with open('ping_results.json', 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logger.info("Results saved to ping_results.json")
            except IOError as e:
                logger.error(f"Error writing to ping_results.json: {e}")
            except TypeError as e:
                logger.error(f"Error serializing results to JSON: {e}")
            
            # Log a summary of results
            success_count = sum(1 for r in results if r.get('ping_success'))
            logger.info(f"Ping summary: {success_count}/{len(results)} sites reachable")
        else:
            logger.warning("No sites processed")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
    logger.info("Ping log tracker script completed.")
    logger.info(f"Script run time: {datetime.now()}")
