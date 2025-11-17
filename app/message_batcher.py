import logging
import asyncio
from openai import OpenAI
from twilio.rest import Client

from app.database import get_db_context, save_message
from app.utils import get_chatgpt_reply, send_whatsapp_message
from app.models.database import MessageDirection


class MessageBatcher:
    """
    Manages per-user message batching with a 10-second debounce timer.
    Collects messages from the same user and processes them together after the timer expires.
    """

    def __init__(
        self, openai_client: OpenAI, twilio_client: Client, whatsapp_number: str
    ):
        self.pending_batches: dict[int, dict] = {}
        self.openai_client = openai_client
        self.twilio_client = twilio_client
        self.whatsapp_number = whatsapp_number

    async def add_message(
        self, user_id: int, message: str, phone_number: str, conversation_id: str
    ):
        """
        Add a message to the user's pending batch and reset the timer.
        """
        # Cancel existing timer if user already has pending messages
        if user_id in self.pending_batches:
            existing_task = self.pending_batches[user_id].get("timer")
            if existing_task and not existing_task.done():
                existing_task.cancel()

            # Add message to existing batch
            self.pending_batches[user_id]["messages"].append(message)
            logging.debug(
                f"Added message to existing batch for user {user_id}. Total messages: {len(self.pending_batches[user_id]['messages'])}"
            )
        else:
            # Create new batch for user
            self.pending_batches[user_id] = {
                "messages": [message],
                "phone_number": phone_number,
                "conversation_id": conversation_id,
            }
            logging.debug(f"Created new batch for user {user_id}")

        # Start new timer (10 seconds)
        timer_task = asyncio.create_task(self._wait_and_process(user_id))
        self.pending_batches[user_id]["timer"] = timer_task

    async def _wait_and_process(self, user_id: int):
        """
        Wait for 10 seconds, then process the batch of messages for the user.
        """
        try:
            await asyncio.sleep(10)

            # Get batch data
            batch_data = self.pending_batches.get(user_id)
            if not batch_data:
                return

            messages = batch_data["messages"]
            phone_number = batch_data["phone_number"]
            conversation_id = batch_data["conversation_id"]

            logging.debug(
                f"Processing batch for user {user_id}: {len(messages)} message(s)"
            )

            # Process the batch
            await self._process_batch(
                user_id=user_id,
                messages=messages,
                phone_number=phone_number,
                conversation_id=conversation_id,
            )

            # Cleanup
            self._cleanup(user_id)

        except asyncio.CancelledError:
            logging.debug(f"Timer cancelled for user {user_id} (new message received)")
            raise
        except Exception as e:
            logging.error(f"Error processing batch for user {user_id}: {str(e)}")
            self._cleanup(user_id)

    async def _process_batch(
        self, user_id: int, messages: list[str], phone_number: str, conversation_id: str
    ):
        """
        Process a batch of messages: combine them, send to ChatGPT, and respond via WhatsApp.
        """
        # Combine all messages with newlines
        combined_message = "\n".join(messages)

        try:
            # Get ChatGPT response with conversation context
            reply_message = get_chatgpt_reply(
                self.openai_client, combined_message, conversation_id
            )

            # Send response via WhatsApp
            send_whatsapp_message(
                self.twilio_client, self.whatsapp_number, phone_number, reply_message
            )

            logging.info(
                f"OUTGOING - recipient={phone_number}, sender={self.whatsapp_number}, message={reply_message}"
            )

            # Save outgoing message to database
            with get_db_context() as db:
                save_message(
                    db=db,
                    recipient=phone_number,
                    sender=self.whatsapp_number,
                    message_text=reply_message,
                    direction=MessageDirection.outgoing,
                    user_id=user_id,
                )

        except Exception as e:
            logging.error(f"ERROR PROCESSING BATCH: {str(e)}")

    def _cleanup(self, user_id: int):
        """
        Remove user's batch data from memory after processing.
        """
        if user_id in self.pending_batches:
            del self.pending_batches[user_id]
            logging.debug(f"Cleaned up batch for user {user_id}")
