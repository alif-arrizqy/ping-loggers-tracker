from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import logging
from datetime import datetime, timedelta
from db_utils import Database
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Di api.py
current_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
        template_folder=os.path.join(current_dir, 'templates'),
        static_folder=os.path.join(current_dir, 'static'))

def convert_to_jakarta_time(timestamp_str):
    """Convert a timestamp string to Jakarta time (UTC+7)"""
    if not timestamp_str:
        return timestamp_str
        
    try:
        # Check if timestamp is already in Jakarta time
        if datetime.now().astimezone().utcoffset() == timedelta(hours=7):
            # System is already in Jakarta timezone
            return timestamp_str
        else:
            # Convert UTC time to Jakarta time
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            jakarta_dt = dt + timedelta(hours=7)
            return jakarta_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Error converting timestamp to Jakarta time: {e}")
        return timestamp_str

@app.route('/', methods=['GET'])
def index():
    """API endpoint to check if the service is running"""
    return jsonify({
        'status': 'success',
        'message': 'Ping Data Logger Tracker API is running'
    })

@app.route('/dashboard', methods=['GET'])
def serve_dashboard():
    """Serve the dashboard HTML page"""
    return render_template('index.html')

@app.route('/ping_logs', methods=['GET'])
def get_ping_logs():
    """API endpoint to get ping logs"""
    try:
        # Parse query parameters
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        site_name = request.args.get('site_name')
        
        logs = Database.get_ping_logs(limit, offset, site_name)
        
        # convert time from utc to Jakarta time
        for log in logs:
            log['timestamp'] = convert_to_jakarta_time(log['timestamp'])
        
        # Count for pagination
        total_count = len(logs)  # Just a simple implementation
        
        return jsonify({
            'status': 'success',
            'data': logs,
            'meta': {
                'total': total_count,
                'limit': limit,
                'offset': offset
            }
        })
    except Exception as e:
        logger.error(f"Error in API: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/ping_logs/summary', methods=['GET'])
def get_summary():
    """API endpoint to get summary of ping logs"""
    try:
        # Parse request parameters
        hours = request.args.get('hours', default=24, type=int)
        
        # Get summary data from the database
        summary = Database.get_summary(hours)
        
        if not summary:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch summary data'
            }), 500
        
        # Add pr_code with issue
        down_sites = Database.get_down_sites(hours)
        
        # convert last_check from utc to Jakarta time
        for site in down_sites:
            site['last_check'] = convert_to_jakarta_time(site['last_check'])
        
        # Format the response
        return jsonify({
            'status': 'success',
            'data': {
                'summary': summary,
                'down_sites': down_sites
            }
        })
    except Exception as e:
        logger.error(f"Error in API Summary: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/length_loggers', methods=['GET'])
def get_length_loggers():
    """API endpoint to get length loggers"""
    try:
        # Parse query parameters
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        site_name = request.args.get('site_name')
        
        logs = Database.get_length_loggers(limit, offset, site_name)
        
        # convert time from utc to Jakarta time
        for log in logs:
            log['timestamp'] = convert_to_jakarta_time(log['timestamp'])

        # Count for pagination
        total_count = len(logs)  # Just a simple implementation
        
        return jsonify({
            'status': 'success',
            'data': logs,
            'meta': {
                'total': total_count,
                'limit': limit,
                'offset': offset
            }
        })
    except Exception as e:
        logger.error(f"Error in API: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    logger.info("Starting Ping Data Logger Tracker API...")
    logger.info(f"Running on port: {os.getenv('API_PORT', 5090)}")
    app.run(debug=True, host='0.0.0.0', port=os.getenv('API_PORT', 5090))
