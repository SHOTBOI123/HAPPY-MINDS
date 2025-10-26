#!/usr/bin/env bash
# Get your local IP address
echo ''
echo '=== Server Access Information ==='
echo ''
echo 'Local access: http://localhost:5001'
echo 'Local access: http://127.0.0.1:5001'
echo ''
echo 'Network access (from other devices):'
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS
    IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 'Not found')
    echo "http://$IP:5001"
elif [[ "$(uname)" == "Linux" ]]; then
    # Linux
    IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'Not found')
    echo "http://$IP:5001"
else
    echo 'Run: ipconfig (Windows) or ifconfig (Linux/Mac) to find your IP'
fi
echo ''
echo 'Make sure other devices are on the same Wi-Fi network!'
echo ''
