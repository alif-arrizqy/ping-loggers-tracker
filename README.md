# Ping & Loggers Tracker

A real-time monitoring dashboard for tracking ping status and data loggers across multiple sites.

## Overview

The Ping & Loggers Tracker is a web-based monitoring system designed to track the online status of remote sites and their associated data loggers. It provides real-time insights into connectivity status, response times, and logger counts across a network of sites.

Built for network operations centers (NOC), this tool helps teams quickly identify and respond to connectivity issues and monitor the health of remote data logging systems.

## Features

- **Real-time Site Monitoring**: Track ping status (online/offline) across all sites
- **Logger Count Tracking**: Monitor the number of active data loggers at each site
- **Response Time Analysis**: View and analyze ping response times for performance monitoring
- **Dashboard Summary**: Get quick insights with summary cards showing sites up/down, total loggers, and average response time
- **Down Sites Overview**: Easily identify problematic sites with dedicated down sites section
- **Advanced Data Table**:
  - Pagination for handling large numbers of sites
  - Sortable columns (ascending/descending)
  - Filtering by site name and status
  - Real-time search functionality
- **Auto-refresh**: Automatic data updates at configurable intervals
- **Responsive Design**: Works on desktops, tablets, and mobile devices

## Technology Stack

### Backend
- Python with Flask for API endpoints
- PostgreSQL database (configurable)
- Database utilities for data management

### Frontend
- HTML5, CSS3 for structure and styling
- Vanilla JavaScript for dynamic behavior
- Font Awesome for icons
- Google Fonts (Roboto) for typography

## API Endpoints

The application provides the following API endpoints:

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/` | GET | Check if API is running | None |
| `/dashboard` | GET | Serve the main dashboard | None |
| `/ping_logs` | GET | Get ping logs | `limit`, `offset`, `site_name` |
| `/ping_logs/summary` | GET | Get summary of ping logs | `hours` (default: 24) |
| `/length_loggers` | GET | Get length loggers data | `limit`, `offset`, `site_name` |

## Installation

### Prerequisites
- Python 3.7+
- pip

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ping-datalog-tracker
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Create a `.env` file in the project root with the following variables:
     ```
        API_URL=http://localhost:port/siteInfo

        # Database Settings
        DB_HOST=localhost
        DB_PORT=5432
        DB_NAME=ping_logs_db
        DB_USER=postgres
        DB_PASSWORD=sundaya2023

        # API Server Settings
        API_PORT=5090

        # EHUB AUTH
        EHUB_TOKEN=BEARERTOKEN
     ```

5. Start the application:
   ```bash
   python main.py
   ```

6. Start the API and Dasboard:
   ```bash
   python api.py
   ```

7. Access the dashboard at `http://localhost:5090/dashboard`

## Usage

### Dashboard Navigation

- **Summary Cards**: Quick overview of key metrics
- **Search & Filter**: Use the search box to find specific sites or filter by status
- **Data Table**: View detailed information about all sites
  - Click column headers to sort the data
  - Use pagination to navigate through multiple pages of sites
- **Down Sites Section**: Check sites that are currently offline
- **Refresh Button**: Manually refresh data when needed

### Configuration

Key configuration options are available in the `.env` file:
- Change the API port by modifying `API_PORT`
- Configure database settings as needed

In the JavaScript code, you can modify:
- `REFRESH_INTERVAL`: Change how often data auto-refreshes (default: 60 seconds)
- `ITEMS_PER_PAGE`: Adjust how many sites appear per page in the table (default: 10)


### Project Structure

```
ping_datalog_tracker/
├── api.py           # Main Flask application and API endpoints
├── db_utils.py      # Database utilities and queries
├── templates/       # HTML templates
│   └── index.html   # Main dashboard template
├── requirements.txt # Python dependencies
└── .env             # Environment variables
```
