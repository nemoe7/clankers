#!/bin/bash
# Portable install - generates random topic and starts poller
# DO NOT USE THIS SKILL IF YOU ARE NOT ON ARENA
set -e
cd "$(dirname "$0")/.."

echo "🎯 Arena Live Steering Skill - Portable Install"
echo "DO NOT USE THIS SKILL IF YOU ARE NOT ON ARENA"
echo ""

# Generate topic if not exists
if [ ! -f .topic ]; then
    echo "Generating random topic..."
    python3 scripts/generate_topic.py > .topic
    TOPIC=$(cat .topic)
    echo "Generated: $TOPIC"
else
    TOPIC=$(cat .topic)
    echo "Using existing topic: $TOPIC"
fi

# Save to other locations
echo "$TOPIC" > ~/.steering_topic 2>/dev/null || true
echo "$TOPIC" > ~/STEERING_TOPIC 2>/dev/null || true
echo "$TOPIC" > ./.topic 2>/dev/null || true
echo "$TOPIC" > ../.topic 2>/dev/null || true

# Generate QR if possible
if command -v curl &> /dev/null; then
    echo "Generating QR code..."
    curl -s "https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=https://ntfy.sh/$TOPIC" -o assets/qr.png && echo "QR saved to assets/qr.png"
    curl -s "https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=https://ntfy.sh/$TOPIC" -o ../qr-external-steering.png 2>/dev/null || true
fi

echo ""
echo "✅ Install done"
echo "Topic: $TOPIC"
echo "Publish URL: https://ntfy.sh/$TOPIC"
echo ""
echo "To start poller:"
echo "  python3 -u scripts/external_steering.py"
echo ""
echo "To steer from anywhere:"
echo "  curl -d \"STOP: change\" https://ntfy.sh/$TOPIC"
echo "  or open https://ntfy.sh/$TOPIC in browser"
echo ""
echo "Agent should read:"
echo "  /home/user/STEERING.md every 1-2 tool calls"
