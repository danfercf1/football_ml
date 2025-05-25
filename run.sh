#!/usr/bin/env bash
# Script to run the Football ML analysis system

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_msg() {
  echo -e "${2}${1}${NC}"
}

# Function to check if Docker and Docker Compose are installed
check_docker() {
  if ! command -v docker &> /dev/null; then
    print_msg "Docker is not installed. Please install Docker first." "$RED"
    exit 1
  fi
  
  if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_msg "Docker Compose is not installed. Please install Docker Compose first." "$RED"
    exit 1
  fi
  
  print_msg "✅ Docker and Docker Compose are installed." "$GREEN"
}

# Function to create a Python virtual environment
create_venv() {
  if [ ! -d "venv" ]; then
    print_msg "Creating Python virtual environment..." "$BLUE"
    python3 -m venv venv
  fi
  
  # Activate virtual environment
  source venv/bin/activate
  
  # Install requirements
  print_msg "Installing required Python packages..." "$BLUE"
  pip install -r requirements.txt
  
  print_msg "✅ Virtual environment setup complete." "$GREEN"
}

# Function to start Docker containers
start_containers() {
  print_msg "Starting MongoDB and RabbitMQ containers..." "$BLUE"
  
  # Check if docker compose command or docker-compose command should be used
  if command -v docker-compose &> /dev/null; then
    docker-compose up -d mongodb rabbitmq
  else
    docker compose up -d mongodb rabbitmq
  fi
  
  # Wait for services to be ready
  print_msg "Waiting for services to be ready..." "$YELLOW"
  sleep 10
  
  print_msg "✅ MongoDB and RabbitMQ are running." "$GREEN"
}

# Function to create the sample ML model
create_model() {
  print_msg "Creating sample ML model..." "$BLUE"
  python scripts/create_model.py
  print_msg "✅ Sample ML model created." "$GREEN"
}

# Function to run the test script
run_tests() {
  print_msg "Running basic tests..." "$BLUE"
  python -m tests.test_basic
  print_msg "✅ Basic tests completed." "$GREEN"
}

# Function to run the analyzer
run_analyzer() {
  print_msg "Starting Football ML analyzer..." "$BLUE"
  print_msg "Press Ctrl+C to stop the analyzer." "$YELLOW"
  python -m src.analyzer
}

# Function to start the bet viewer
start_bet_viewer() {
  print_msg "Starting bet viewer in Docker..." "$BLUE"
  
  # Check if docker compose command or docker-compose command should be used
  if command -v docker-compose &> /dev/null; then
    docker-compose up -d bet_viewer
  else
    docker compose up -d bet_viewer
  fi
  
  print_msg "✅ Bet viewer is running. Check Docker logs to see incoming bet signals." "$GREEN"
}

# Function to show logs from bet viewer
show_logs() {
  print_msg "Showing logs from bet viewer..." "$BLUE"
  print_msg "Press Ctrl+C to stop watching logs." "$YELLOW"
  
  # Check if docker compose command or docker-compose command should be used
  if command -v docker-compose &> /dev/null; then
    docker-compose logs -f bet_viewer
  else
    docker compose logs -f bet_viewer
  fi
}

# Main function
main() {
  # Check if Docker is installed
  check_docker
  
  # Create Python virtual environment
  create_venv
  
  # Start Docker containers
  start_containers
  
  # Create sample model
  create_model
  
  # Start bet viewer
  start_bet_viewer
  
  # Run tests
  run_tests
  
  # Run the analyzer
  run_analyzer
}

# Execute main function
main
