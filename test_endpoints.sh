#!/bin/bash

# Configuration
BASE_URL="http://127.0.0.1:8000/api/v1"
SESSION_ID=""
PLAN_ID=""
JOB_ID=""

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Helper function to prompt and run
run_test() {
    local title=$1
    local command=$2
    
    echo -e "\n${CYAN}=================================================${NC}"
    echo -e "${YELLOW}Testing: ${title}${NC}"
    echo -e "${CYAN}=================================================${NC}"
    echo -e "Command to run:"
    echo "$command"
    echo ""
    
    read -p "Run this test? (y/n): " choice
    if [[ "$choice" == "y" || "$choice" == "Y" ]]; then
        echo -e "\n${GREEN}Executing...${NC}"
        # Execute the command, save the output to a temp file
        eval "$command > /tmp/mcplink_test_output.json 2>/dev/null"
        
        # Try to format the JSON using python's built-in json tool
        python3 -m json.tool < /tmp/mcplink_test_output.json 2>/dev/null || cat /tmp/mcplink_test_output.json
        echo ""
    else
        echo -e "${RED}Skipped.${NC}"
    fi
}

echo -e "${GREEN}Starting MCPLink v2 Backend Endpoint Tests...${NC}"
echo "Make sure your server is running on $BASE_URL before continuing!"

# 1. Create a session
CMD="curl -s -X POST '$BASE_URL/sessions' -H 'accept: application/json' -d ''"
run_test "Create Session [POST /sessions]" "$CMD"

# Extract SESSION_ID using basic grep/awk (Fallback if no jq)
if [ -f /tmp/mcplink_test_output.json ]; then
    SESSION_ID=$(grep -o '"session_id": *"[^"]*"' /tmp/mcplink_test_output.json | awk -F'"' '{print $4}')
fi

if [ -z "$SESSION_ID" ]; then
    echo -e "${RED}Failed to extract SESSION_ID! Setting a dummy one to proceed, but tests will likely fail.${NC}"
    SESSION_ID="test-session-id"
else
    echo -e "${GREEN}Captured SESSION_ID: $SESSION_ID${NC}"
fi

# 2. Get session status
CMD="curl -s -X GET '$BASE_URL/sessions/$SESSION_ID' -H 'accept: application/json'"
run_test "Get Session [GET /sessions/{id}]" "$CMD"

# 3. List Tools
CMD="curl -s -X GET '$BASE_URL/tools' -H 'accept: application/json'"
run_test "List Tools [GET /tools]" "$CMD"

# 4. Generate a Plan
CMD="curl -s -X POST '$BASE_URL/sessions/$SESSION_ID/plan' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
  \"prompt\": \"Create a file named test_file.txt in the sandbox with some random text.\",
  \"document_context\": \"\"
}'"
run_test "Create Plan [POST /sessions/{id}/plan]" "$CMD"

if [ -f /tmp/mcplink_test_output.json ]; then
    PLAN_ID=$(grep -o '"plan_id": *"[^"]*"' /tmp/mcplink_test_output.json | awk -F'"' '{print $4}')
fi

if [ -z "$PLAN_ID" ]; then
    echo -e "${RED}Failed to extract PLAN_ID! You may need to run this command manually.${NC}"
    PLAN_ID="test-plan-id"
else
    echo -e "${GREEN}Captured PLAN_ID: $PLAN_ID${NC}"
fi

# 5. Preview Plan
if [ "$PLAN_ID" != "test-plan-id" ]; then
    CMD="curl -s -X GET '$BASE_URL/sessions/$SESSION_ID/plan/$PLAN_ID' -H 'accept: application/json'"
    run_test "Preview Plan [GET /sessions/{id}/plan/{plan_id}]" "$CMD"
fi

# 6. Execute Plan Async
if [ "$PLAN_ID" != "test-plan-id" ]; then
    CMD="curl -s -X POST '$BASE_URL/sessions/$SESSION_ID/execute' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
  \"plan_id\": \"$PLAN_ID\",
  \"mode\": \"full\"
}'"
    run_test "Execute Plan (Async Full) [POST /sessions/{id}/execute]" "$CMD"
    
    if [ -f /tmp/mcplink_test_output.json ]; then
        JOB_ID=$(grep -o '"job_id": *"[^"]*"' /tmp/mcplink_test_output.json | awk -F'"' '{print $4}')
    fi
    echo -e "${GREEN}Captured JOB_ID: $JOB_ID${NC}"
fi

# 7. Check Execution Status
if [ -n "$JOB_ID" ]; then
    CMD="curl -s -X GET '$BASE_URL/sessions/$SESSION_ID/execution-status/$JOB_ID' -H 'accept: application/json'"
    run_test "Get Execution Status [GET /sessions/{id}/execution-status/{job_id}]" "$CMD"
fi

# 8. Check History
CMD="curl -s -X GET '$BASE_URL/sessions/$SESSION_ID/history' -H 'accept: application/json'"
run_test "Get Session History [GET /sessions/{id}/history]" "$CMD"

# 9. Get Policy
CMD="curl -s -X GET '$BASE_URL/policy' -H 'accept: application/json'"
run_test "Get Policy [GET /policy]" "$CMD"

# 10. Update Policy
CMD="curl -s -X PUT '$BASE_URL/policy' \
-H 'accept: application/json' \
-H 'Content-Type: application/json' \
-d '{
  \"max_file_size_mb\": 20,
  \"execution_timeout_seconds\": 60
}'"
run_test "Update Policy [PUT /policy]" "$CMD"

# 11. Test File Upload Endpoint
# First create a dummy file to upload
echo "This is a test upload file" > /tmp/dummy_upload.txt

CMD="curl -s -X POST '$BASE_URL/files/upload' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/tmp/dummy_upload.txt'"
run_test "Upload File [POST /files/upload]" "$CMD"

echo -e "\n${GREEN}Testing Sandbox Directory...${NC}"
ls -la app/sandbox/workspace/ 2>/dev/null

echo -e "\n${CYAN}All tests completed!${NC}"
