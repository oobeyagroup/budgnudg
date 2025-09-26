# Updated ./v Script with ATDD Dashboard Support

The `./v` startup script has been enhanced to include ATDD dashboard server functionality.

## Usage Options

### Regular Django Development Server
```bash
./v                # Start Django server on port 8000
./v 8080           # Start Django server on port 8080
./v --migrate      # Run migrations then start Django server
./v 8080 --migrate # Start on port 8080 after migrations
```

### ATDD Dashboard Server
```bash
./v --atdd         # Start ATDD dashboard server on port 8081
./v -a             # Same as --atdd (short form)
```

## What the ATDD Dashboard Option Does

When you run `./v --atdd`, the script will:

1. **Activate the virtual environment**
2. **Check Django setup** (versions, migrations)
3. **Generate the latest ATDD dashboard** using `python manage.py generate_atdd_dashboard --generate-only`
4. **Start HTTP server** on port 8081 serving the dashboard from `docs/atdd_dashboard/`
5. **Display access information**:
   - ATDD Dashboard: http://127.0.0.1:8081

## Regular Django Server Enhancement

When starting the regular Django server (without `--atdd`), the script now also displays:
- Information about how to start the ATDD dashboard: `./v --atdd`

## Complete Help
```bash
./v --help         # Show all available options
```

## Example Workflow

### Development with ATDD Dashboard
```bash
# Terminal 1: Start the main Django application
./v 8000

# Terminal 2: Start the ATDD dashboard
./v --atdd
```

Now you can:
- Access your main application at http://127.0.0.1:8000
- View ATDD dashboard at http://127.0.0.1:8081
- Dashboard automatically regenerates with latest test/criteria status

## Benefits

- **One-command ATDD dashboard**: No need to remember complex commands
- **Always fresh data**: Dashboard regenerates each time it's started
- **Integrated workflow**: ATDD dashboard is now part of your development startup routine
- **Clear access URLs**: Script displays exactly where to find the dashboard