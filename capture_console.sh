#!/bin/bash
# Script to capture console logs from a webpage

URL="http://127.0.0.1:8000/transactions/categorize/1622/?no_payoree=1"
OUTPUT_FILE="console_log_$(date +%Y%m%d_%H%M%S).txt"

# Using Node.js with puppeteer (if installed)
# npm install -g puppeteer

cat << 'EOF' > capture_console.js
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  
  // Listen to console events
  page.on('console', msg => {
    console.log(`${new Date().toISOString()} [${msg.type()}]: ${msg.text()}`);
  });
  
  await page.goto(process.argv[2]);
  
  // Wait a bit for JavaScript to run
  await page.waitForTimeout(5000);
  
  await browser.close();
})();
EOF

node capture_console.js "$URL" > "$OUTPUT_FILE" 2>&1
echo "Console log saved to: $OUTPUT_FILE"
