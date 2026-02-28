#!/bin/bash
# ============================================================================
# Stop the ColQwen server and optionally stop the EC2 instance
# ============================================================================

echo "Stopping ColQwen server..."

# Option 1: Graceful shutdown via API
if curl -s -X POST http://localhost:8000/shutdown > /dev/null 2>&1; then
    echo "  Sent shutdown request to server"
    sleep 3
fi

# Option 2: Kill tmux session
tmux kill-session -t colqwen 2>/dev/null && echo "  Killed tmux session" || echo "  No tmux session found"

echo "Server stopped."
echo ""

# Ask about stopping the EC2 instance
read -p "Do you also want to STOP the EC2 instance to save costs? (y/N): " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    echo "Stopping EC2 instance..."
    
    # Get instance ID from metadata
    INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null)
    
    if [ -n "$INSTANCE_ID" ]; then
        echo "  Instance ID: $INSTANCE_ID"
        # Use IMDSv2 token if needed
        TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null)
        if [ -n "$TOKEN" ]; then
            INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
        fi
        
        aws ec2 stop-instances --instance-ids "$INSTANCE_ID"
        echo "  EC2 stop-instances command sent."
        echo "  Instance will stop in ~30 seconds. SSH connection will be lost."
        echo "  No more compute charges after instance is stopped."
        echo "  (EBS storage charges still apply: ~\$0.10/GB/month)"
    else
        echo "  Could not determine instance ID."
        echo "  Stop manually: aws ec2 stop-instances --instance-ids <your-id>"
    fi
else
    echo "Instance left running. Remember to stop it when done to save costs!"
    echo "  Cost: g4dn.xlarge = \$0.526/hour = \$12.62/day"
fi
