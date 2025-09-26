#!/bin/bash

# BudgNudg Development Server Startup Script
# Usage: ./v [port] [--migrate] [--collect] [--help]

set -e  # Exit on any error

# Default port
PORT=8000
MIGRATE=false
COLLECTSTATIC=false
SHOW_HELP=false
ATDD_DASHBOARD=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --migrate|-m)
            MIGRATE=true
            shift
            ;;
        --collect|-c)
            COLLECTSTATIC=true
            shift
            ;;
        --atdd|-a)
            ATDD_DASHBOARD=true
            shift
            ;;
        --help|-h)
            SHOW_HELP=true
            shift
            ;;
        [0-9]*)
            PORT=$1
            shift
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

# Show help
if [ "$SHOW_HELP" = true ]; then
    echo "BudgNudg Development Server Startup Script"
    echo ""
    echo "Usage: ./v [port] [options]"
    echo ""
    echo "Options:"
    echo "  [port]        Port number (default: 8000)"
    echo "  --migrate, -m Run migrations before starting server"
    echo "  --collect, -c Collect static files before starting server"
    echo "  --atdd, -a    Start ATDD dashboard server on port 8081"
    echo "  --help, -h    Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./v                Start server on port 8000"
    echo "  ./v 8080           Start server on port 8080"
    echo "  ./v --migrate      Run migrations then start server"
    echo "  ./v --atdd         Start ATDD dashboard server"
    echo "  ./v 8080 --migrate Start on port 8080 after migrations"
    exit 0
fi

echo "🚀 Starting BudgNudg Development Environment..."
echo "📁 Working directory: $(pwd)"

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source ~/venv/budgnudg_env/bin/activate

# Show Python and Django versions
echo "🐍 Python version: $(python --version)"
echo "🎯 Django version: $(python -c "import django; print(django.get_version())" 2>/dev/null || echo 'Not found')"

# Run migrations if requested
if [ "$MIGRATE" = true ]; then
    echo "📊 Running database migrations..."
    python manage.py migrate
fi

# Collect static files if requested
if [ "$COLLECTSTATIC" = true ]; then
    echo "📦 Collecting static files..."
    python manage.py collectstatic --noinput
fi

# Check for pending migrations (but don't block)
echo "🔍 Checking for unapplied migrations..."
if python manage.py showmigrations --plan | grep -q "\[ \]"; then
    echo "⚠️  Warning: You have unapplied migrations. Run './v --migrate' to apply them."
else
    echo "✅ All migrations are up to date."
fi

# Handle ATDD Dashboard request
if [ "$ATDD_DASHBOARD" = true ]; then
    echo ""
    echo "📊 Starting ATDD Dashboard Server..."
    echo "🔧 Generating latest dashboard..."
    
    # Generate the latest dashboard
    python manage.py generate_atdd_dashboard --generate-only
    
    echo ""
    echo "🌐 ATDD Dashboard will be available at:"
    echo "   - http://127.0.0.1:8081"
    echo ""
    echo "💡 Press Ctrl+C to stop the dashboard server"
    echo "----------------------------------------"
    
    # Start the ATDD dashboard server
    cd docs/atdd_dashboard
    exec python -m http.server 8081
fi

# Show useful URLs
echo ""
echo "🌐 Server will be available at:"
echo "   - Local:     http://127.0.0.1:$PORT"
echo "   - Network:   http://localhost:$PORT"
echo "   - Admin:     http://127.0.0.1:$PORT/admin/"
echo "   - Budgets:   http://127.0.0.1:$PORT/budgets/"
echo ""
echo "📊 To start ATDD Dashboard: ./v --atdd"
echo ""

# Start the server
echo "🎬 Starting Django development server on port $PORT..."
echo "💡 Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Use exec to replace the shell process with the Django server
exec python manage.py runserver 127.0.0.1:$PORT