#!/usr/bin/env python3
"""
Simple RabbitMQ consumer that displays bet signals from the queue.
"""
import json
import pika
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# RabbitMQ connection parameters
RABBITMQ_HOST = "rabbitmq"  # Use service name in Docker network
RABBITMQ_PORT = 5672
RABBITMQ_USER = "guest"
RABBITMQ_PASS = "guest"
RABBITMQ_QUEUE = "bet_signals"

def callback(ch, method, properties, body):
    """Process received messages from RabbitMQ."""
    try:
        message = json.loads(body)
        logger.info("=" * 50)
        logger.info("🚨 NEW BET SIGNAL RECEIVED 🚨")
        logger.info(f"Match ID: {message.get('match_id')}")
        logger.info(f"Market: {message.get('market')}")
        logger.info(f"Action: {message.get('action')}")
        logger.info(f"Reason: {message.get('reason')}")
        
        # Show confidence if available
        if 'confidence' in message:
            logger.info(f"Confidence: {message.get('confidence'):.2f}")
            
        # Show odds if available
        if 'odds' in message:
            logger.info(f"Odds: {message.get('odds')}")
            
        # Show timestamp in a readable format
        if 'timestamp' in message:
            try:
                dt = datetime.fromisoformat(message['timestamp'])
                logger.info(f"Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except ValueError:
                logger.info(f"Timestamp: {message.get('timestamp')}")
                
        logger.info("=" * 50)
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse message: {body}")
        # Still acknowledge to remove from queue
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        # Still acknowledge to remove from queue
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    """Connect to RabbitMQ and start consuming messages."""
    # Wait a bit for RabbitMQ to be ready
    time.sleep(5)
    
    connection = None
    
    while True:
        try:
            # Set up connection parameters
            credentials = pika.PlainCredentials(username=RABBITMQ_USER, password=RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600
            )
            
            # Connect and create a channel
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            
            # Declare the queue (creates it if it doesn't exist)
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            
            # Set up consumer
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
            
            logger.info("🎮 Bet Viewer Started - Waiting for messages...")
            logger.info("Press Ctrl+C to exit")
            
            # Start consuming
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError:
            logger.warning("Failed to connect to RabbitMQ. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Bet viewer shutting down...")
            if connection and connection.is_open:
                connection.close()
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if connection and connection.is_open:
                connection.close()
            time.sleep(5)

if __name__ == "__main__":
    main()
