from flask import Flask, request, jsonify
import os
import logging
from datetime import datetime, timedelta
from db_utils import Database
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/ping_logs', methods=['GET'])
def get_ping_logs():
    """API endpoint to get ping logs"""
    try:
        # Parse query parameters
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        site_name = request.args.get('site_name')
        
        logs = Database.get_ping_logs(limit, offset, site_name)

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
    app.run(debug=True, host='0.0.0.0', port=os.getenv('API_PORT', 5090))
