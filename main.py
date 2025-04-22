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
    level=logging.ERROR,
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
                    'battery_version': site.get('battery_version'),
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
            battery_version = site.get('battery_version', 'UNKNOWN')
            
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
                    logger_result = self.length_loggers_site(ip_address, battery_version)
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
                        battery_version=battery_version,
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
                    'battery_version': battery_version,
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
    
    def length_loggers_site(self, ip_address, battery_version):
        """Get length of loggers from a specific IP address based on battery version"""
        try:
            start_time = datetime.now()
            Headers = {"Authorization": f"Bearer {os.getenv('EHUB_TOKEN')}"}
            
            # Initialize total logger count
            total_loggers_count = 0
            
            # Determine which endpoint(s) to use based on battery version
            if battery_version and "TALIS5" in battery_version.upper():
                # For any TALIS5-related battery versions (FULL or MIX)
                logger.info(f"Using Talis5 endpoint for {ip_address} with battery version {battery_version}")
                
                # Try fetching Talis5 data with better error handling
                talis_loggers_count = 0
                try:
                    response_talis = requests.get(f"http://{ip_address}/api/logger/talis", headers=Headers, timeout=10)
                    response_talis.raise_for_status()
                    data_talis = response_talis.json()
                    
                    # Calculate Talis5 logger count
                    if "data" in data_talis:
                        logger.info(f"site {ip_address} message: {data_talis.get('message')}")
                        if data_talis.get("message") == "Success":
                            talis_data = data_talis["data"]
                            # Sum the length of arrays for each interface
                            mppt_count = len(talis_data.get("mppt", []))
                            usb0_count = len(talis_data.get("usb0", []))
                            usb1_count = len(talis_data.get("usb1", []))
                        
                            talis_loggers_count = mppt_count + usb0_count + usb1_count
                            logger.info(f"Talis5 loggers: MPPT={mppt_count}, USB0={usb0_count}, USB1={usb1_count}, Talis Total={talis_loggers_count}")
                        else:
                            # Fallback if message isn't "Success" but data exists
                            talis_loggers_count = len(data_talis.get("data", []))
                            logger.info(f"Talis5 loggers count (from data array): {talis_loggers_count}")
                    else:
                        logger.warning(f"Unexpected Talis5 response structure from {ip_address}: Missing 'data' key")
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching Talis5 data from {ip_address}: {e}")
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"JSON decode error in Talis5 response from {ip_address}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing Talis5 data from {ip_address}: {e}")
                
                total_loggers_count += talis_loggers_count
                
                # For MIX TALIS5, we also need to check the JSPro endpoint
                if "MIX" in battery_version.upper():
                    logger.info(f"MIX TALIS5 detected, also checking JSPro endpoint for {ip_address}")
                    jspro_loggers_count = 0
                    
                    # Try fetching JSPro data with better error handling
                    try:
                        response_jspro = requests.get(f"http://{ip_address}/api/logger", headers=Headers, timeout=10)
                        response_jspro.raise_for_status()
                        data_jspro = response_jspro.json()
                        
                        # Handle JSPro response structure
                        if "data" in data_jspro:
                            logger.info(f"site {ip_address} message: {data_jspro.get('message')}")
                            if data_jspro.get("message") == "Success":
                                jspro_data = len(data_jspro["data"])
                                jspro_loggers_count = jspro_data
                                logger.info(f"JSPro loggers count: {jspro_loggers_count}")
                            else:
                                # Fallback if message isn't "Success" but data exists
                                jspro_loggers_count = len(data_jspro.get("data", []))
                                logger.info(f"JSPro loggers count (from data array): {jspro_loggers_count}")
                        else:
                            jspro_loggers_count = len(data_jspro.get("data", []))
                            logger.info(f"JSPro loggers count (from data array): {jspro_loggers_count}")
                            
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error fetching JSPro data from {ip_address}: {e}")
                    except (ValueError, json.JSONDecodeError) as e:
                        logger.error(f"JSON decode error in JSPro response from {ip_address}: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error processing JSPro data from {ip_address}: {e}")
                    
                    total_loggers_count += jspro_loggers_count
                    logger.info(f"Total loggers for MIX TALIS5: Talis={talis_loggers_count}, JSPro={jspro_loggers_count}, Combined={total_loggers_count}")
            
            else:
                # Default to JSPro endpoint for all other battery types
                logger.info(f"Using JSPro endpoint for {ip_address} with battery version {battery_version}")
                
                # Try fetching JSPro data with better error handling
                try:
                    response = requests.get(f"http://{ip_address}/api/logger", headers=Headers, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Handle JSPro response structure
                    if isinstance(data, list):
                        total_loggers_count = len(data)
                        logger.info(f"JSPro loggers count: {total_loggers_count}")
                    else:
                        logger.error(f"Unexpected JSPro data structure from {ip_address}: {type(data)}")
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching JSPro data from {ip_address}: {e}")
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"JSON decode error in JSPro response from {ip_address}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing JSPro data from {ip_address}: {e}")
            
            # Calculate response time
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000  # Convert to ms
            
            return {
                "success": True,
                "response_time": response_time,
                "method": "GET",
                "data": total_loggers_count,
                "battery_version": battery_version
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in length_loggers_site for {ip_address}: {e}")
            return {
                "success": False,
                "response_time": None,
                "method": "GET",
                "error": str(e),
                "battery_version": battery_version
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
