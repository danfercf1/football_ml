"""
Module for handling RabbitMQ message publishing for bet signals.
"""
import json
import logging
from typing import Dict, Any

import pika
from pika.exceptions import AMQPError

from src import config

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """
    Publisher for sending bet signals to a RabbitMQ queue.
    """
    
    def __init__(self):
        """Initialize RabbitMQ connection and channel."""
        self.connection = None
        self.channel = None
        self.connected = False
        # Store default queue name from config
        self.queue_name = config.RABBITMQ_QUEUE
        self._connect()
    
    def _connect(self) -> bool:
        """
        Establish connection to RabbitMQ server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Set up connection parameters
            credentials = pika.PlainCredentials(
                username=config.RABBITMQ_USER,
                password=config.RABBITMQ_PASS
            )
            
            parameters = pika.ConnectionParameters(
                host=config.RABBITMQ_HOST,
                port=config.RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            # Connect and create a channel
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare the queue (creates it if it doesn't exist)
            self.channel.queue_declare(
                queue=config.RABBITMQ_QUEUE,
                durable=True  # Queue survives broker restarts
            )
            
            self.connected = True
            logger.info("Successfully connected to RabbitMQ")
            return True
            
        except AMQPError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self.connected = False
            return False
    
    def publish_bet_signal(self, bet_data: Dict[str, Any]) -> bool:
        """
        Publish a bet signal to the RabbitMQ queue.
        
        Args:
            bet_data: Dictionary containing bet signal data
            
        Returns:
            True if message was published successfully, False otherwise
        """
        if not self.connected:
            if not self._connect():
                logger.error("Cannot publish message: not connected to RabbitMQ")
                return False
        
        try:
            # Ensure bet_data has all required fields
            required_fields = ["match_id", "market", "action"]
            for field in required_fields:
                if field not in bet_data:
                    logger.error(f"Cannot publish bet signal: missing required field '{field}'")
                    return False
            
            # Add timestamp to the message
            import datetime
            bet_data["timestamp"] = datetime.datetime.now().isoformat()
            
            # Convert data to JSON
            message = json.dumps(bet_data)
            
            # Publish message
            self.channel.basic_publish(
                exchange='',
                routing_key=config.RABBITMQ_QUEUE,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"Published bet signal for {bet_data['match_id']}: {bet_data['market']} - {bet_data['action']}")
            return True
            
        except AMQPError as e:
            logger.error(f"Failed to publish bet signal: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Error preparing bet signal for publication: {e}")
            return False
    
    def publish_message(self, queue_name: str, message: Dict[str, Any], routing_key: str = None) -> bool:
        """
        General purpose method to publish a message to any RabbitMQ queue.
        
        Args:
            queue_name: The name of the queue to publish to
            message: Dictionary containing the message data
            routing_key: The routing key (defaults to queue_name if not specified)
            
        Returns:
            True if message was published successfully, False otherwise
        """
        if routing_key is None:
            routing_key = queue_name
            
        if not self.connected:
            if not self._connect():
                logger.error(f"Cannot publish message to {queue_name}: not connected to RabbitMQ")
                return False
        
        try:
            # Declare the queue (creates it if it doesn't exist)
            self.channel.queue_declare(
                queue=queue_name,
                durable=True  # Queue survives broker restarts
            )
            
            # Convert data to JSON if it's not already a string
            if isinstance(message, dict):
                message_body = json.dumps(message)
            else:
                message_body = str(message)
            
            # Publish message
            self.channel.basic_publish(
                exchange='',
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"Published message to queue: {queue_name}")
            return True
            
        except AMQPError as e:
            logger.error(f"Failed to publish message to {queue_name}: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Error preparing message for publication: {e}")
            return False
    
    def publish_cashout_signal(self, cashout_signal: Dict[str, Any]) -> bool:
        """
        Publish a cashout signal to the RabbitMQ queue.
        
        Args:
            cashout_signal: Dictionary with cashout signal information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use betfair_bets queue for cashout signals
            target_queue = "betfair_bets"
            
            # Add emergency flag for routing priority
            if cashout_signal.get("reason") == "goal_canceled_emergency":
                cashout_signal["emergency"] = True
            
            # Use the generic publish_message method
            return self.publish_message(
                queue_name=target_queue,
                message=cashout_signal,
                routing_key=target_queue
            )
            
        except Exception as e:
            logger.error(f"Error publishing cashout signal: {e}")
            return False
    
    def close(self) -> None:
        """Close the RabbitMQ connection."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            logger.info("RabbitMQ connection closed")
            self.connected = False


def get_rabbitmq_publisher() -> RabbitMQPublisher:
    """
    Create and return a RabbitMQ publisher instance.
    
    Returns:
        Configured RabbitMQPublisher
    """
    return RabbitMQPublisher()


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    publisher = get_rabbitmq_publisher()
    
    # Example bet signal
    example_bet = {
        "match_id": "abcd-1234-efgh-5678",
        "market": "over_2.5",
        "action": "place",
        "odds": 1.85,
        "stake": 10.0,
        "reason": "rule_shots_high"
    }
    
    success = publisher.publish_bet_signal(example_bet)
    print(f"Message published: {success}")
    
    publisher.close()
