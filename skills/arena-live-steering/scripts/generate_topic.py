#!/usr/bin/env python3
"""
Generate random ntfy topic for steering - portable skill version
Generates arena-steer-{8 hex} via uuid4
"""
import uuid
import pathlib
import os

def generate_topic():
    """Generate random topic like arena-steer-a1b2c3d4"""
    return f"arena-steer-{uuid.uuid4().hex[:8]}"

def get_or_create_topic():
    """Get existing topic or generate new random one"""
    possible_files = [
        pathlib.Path("/home/user/.steering_topic"),
        pathlib.Path("/home/user/STEERING_TOPIC"),
        pathlib.Path("/home/user/arena-live-steering/.topic"),
        pathlib.Path("/home/user/arena-live-steering/scripts/../.topic"),
        pathlib.Path("./.topic"),
        pathlib.Path("./.steering_topic"),
    ]
    # Check for existing valid topic
    for p in possible_files:
        if p.exists():
            try:
                content = p.read_text().strip()
                # Take first token that looks like topic
                for token in content.split():
                    if token.startswith("arena-steer-") and len(token) >= 15:
                        return token
            except:
                pass
    
    # Generate new random topic
    topic = generate_topic()
    
    # Save to all locations for portability
    for p in possible_files:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(topic)
        except:
            pass
    
    return topic

if __name__ == "__main__":
    topic = get_or_create_topic()
    print(topic)
