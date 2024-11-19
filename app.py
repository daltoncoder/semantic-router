from flask import Flask, Response, stream_with_context, request
import json
import opengradient as og
from sseclient import SSEClient
import threading
import logging
from typing import Dict, Any
import os
import queue
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
import traceback
import time
import requests
from vertexai.preview.generative_models import GenerativeModel
import vertexai

# Configure logging with more detailed setup
logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    # Load from decrypted config files in config/ directory
    with open('config/opengradient.json') as f:
        og_config = json.load(f)
    with open('config/index.json') as f:
        index_config = json.load(f)
    with open('config/project.json') as f:
        project_config = json.load(f)
        
    OG_EMAIL = og_config['email']
    OG_PASSWORD = og_config['password']
    OG_PRIVATE_KEY = og_config['private_key']
    BASE_URL = index_config['base_url']
    SOURCE = index_config['source']
    PROMPT = index_config['prompt']
    PROJECT_ID = project_config['project_id']
class LLMProvider:
    def __init__(self):
        self.providers = {
            'og': {
                'call': self._call_opengradient,
                'parse': self._parse_og_response
            },
            'gemini': {
                'call': self._call_gemini,
                'parse': self._parse_gemini_response
            }
        }
        try:
            # Set Google credentials from decrypted config
            google_creds_path = 'config/google.json'
            if os.path.exists(google_creds_path):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = google_creds_path
            
            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', Config.PROJECT_ID),
                location='us-central1'
            )
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {str(e)}")
            raise

    def _call_opengradient(self, prompt: str) -> tuple[str, str]:
        tx_hash, response = og.llm_completion(
            model_cid='meta-llama/Meta-Llama-3-8B-Instruct',
            prompt=prompt,
            max_tokens=5000,
            temperature=0.2,
            stop_sequence=['}']
        )
        return tx_hash, response

    def _call_gemini(self, prompt: str) -> tuple[str, str]:
        model = GenerativeModel('gemini-1.5-pro-002')
        generation_config = {
            'max_output_tokens': 512,
            'temperature': 0.2,
            'top_p': 0.95
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        return 'gemini', response.text

    def get_completion(self, provider: str, prompt: str) -> tuple[str, str]:
        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        tx_hash, response = self.providers[provider]['call'](prompt)
        parsed_response = self.providers[provider]['parse'](response)
        return tx_hash, parsed_response

    @staticmethod
    def _parse_og_response(response: str) -> str:
        """Parse OpenGradient response which needs JSON completion."""
        response = response + '}'
        return response

    @staticmethod
    def _parse_gemini_response(response: str) -> str:
        """Parse Gemini response which may include markdown code blocks."""
        # Remove markdown code blocks if present
        if '```json' in response:
            response = response.split('```json')[-1].split('```')[0]
        return response.strip()

class UpdateProcessor:
    def __init__(self):
        self.active_routers = {}
        self.llm_provider = LLMProvider()

    def evaluate_update(self, prompt: str, update: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate an update using specified LLM provider."""
        logger.info(f"Starting evaluation for prompt: {prompt[:100]}...")
        logger.info(f"Update content: {json.dumps(update, indent=2)}")
        try:
            author_name = update['author'].get('name') or update['author']['username']
            update_prompt = self._build_prompt(prompt, update, author_name)
            # logger.info(f"Built prompt: {update_prompt}")
            
            # Use provider (can be configured via env var or passed parameter)
            provider = os.getenv('LLM_PROVIDER', 'gemini')
            logger.info(f"Using LLM provider: {provider}")
            tx_hash, response = self.llm_provider.get_completion(provider, update_prompt)
            logger.info(f"LLM response: {response}")

            result = self._parse_response(response)
            # result['tx_hash'] = tx_hash
            logger.info(f"Parsed result: {json.dumps(result, indent=2)}")
            
            return result

        except Exception as e:
            logger.error(f"Error evaluating update: {str(e)}", exc_info=True)
            return {
                "decision": "stop",
            }

    @staticmethod
    def _build_prompt(prompt: str, update: dict, author_name: str) -> str:
        # Get base prompt from remote IPFS
        response = requests.get(f"https://ipfs.index.network/files/{Config.PROMPT}")
        basePrompt = response.text
        return f""" {basePrompt}

-------------------
Here is the conversation history to check intent:
- User: Show me {prompt} and nothing else.
-------------------
New cast update to evaluate:

Cast Text: {update['text']}
Cast Link: {update['link']}
Cast Author: [{author_name}](https://warpcast.com/{update['author']['username']})

Output response only in JSON format with the following structure:
{{
    "decision": "recommend" | "inappropriate" | "stop",
    "rationale": "explanation for the decision",
    "score": numeric_value,
    "message": "update message for the conversation"
}}"""

    @staticmethod
    def _parse_response(response: str) -> dict:
        """Parse and clean the OpenGradient response to extract valid JSON."""
        try:
            # Remove any "Here is the output:" prefix
            if "Here is the output:" in response:
                response = response.split("Here is the output:")[-1].strip()
            
            # Try parsing the response as-is first
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If that fails, try the cleanup approach
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                
                if start_idx == -1 or end_idx == -1:
                    raise ValueError("No valid JSON object found in response")
                
                # Extract everything between the first '{' and last '}'
                json_str = response[start_idx:end_idx + 1]
                return json.loads(json_str)
                
        except Exception as e:
            logger.error(f"Failed to parse response: {response}")
            raise json.JSONDecodeError(f"Failed to parse response: {str(e)}", response, 0)

# Initialize app and processor
app = Flask(__name__)
processor = UpdateProcessor()
og.init(email=Config.OG_EMAIL, password=Config.OG_PASSWORD, private_key=Config.OG_PRIVATE_KEY)

# Add a global queue for updates
update_queue = queue.Queue()

@dataclass
class RouterConfig:
    prompt: str
    queue: queue.Queue
    created_at: datetime

def process_update(updated_item: Dict[str, Any]) -> None:
    """Process an update from the event stream."""
    logger.info(f"Processing new update: {json.dumps(updated_item, indent=2)}")
    
    try:
        if not updated_item.get('data', {}).get('node'):
            logger.warning(f"Rejected malformed request: {json.dumps(updated_item, indent=2)}")
            return

        cast = updated_item['data']['node']
        # logger.info(f"Processing cast: {json.dumps(cast, indent=2)}")
        cast['link'] = f"https://warpcast.com/{cast['author']['username']}/{cast['hash'][:12]}"
        cast['channel_id'] = updated_item.get('data', {}).get('channel', {}).get('id')

        logger.info(f"Active routers: {list(processor.active_routers.keys())}")
        for prompt, router_config in processor.active_routers.items():
            logger.info(f"Processing for prompt: {prompt[:100]}")
            try:
                result = processor.evaluate_update(router_config.prompt, cast)
                logger.info(f"Evaluation result: {json.dumps(result, indent=2)}")
                

                result['item'] = updated_item
                
                # If recommended, add to queue for routers
                if result['decision'] == 'recommend':
                    router_config.queue.put(result)
                    logger.info(f"Added recommended update to queue for prompt: {prompt[:100]}")
                
            except Exception as e:
                logger.error(f"Error processing update for prompt {prompt[:100]}: {str(e)}", exc_info=True)

    except Exception as e:
        logger.error(f"Error processing update: {str(e)}", exc_info=True)

def router_thread(url: str):
    """Separated router thread function with robust error handling and backoff"""
    logger.info(f"Starting SSE router thread with URL: {url}")
    retry_count = 0
    max_retries = 5
    base_delay = 5  # Base delay in seconds
    
    while True:
        try:
            logger.info(f"Connecting to SSE stream... {url}")
            headers = {
                'Accept': 'text/event-stream',
                'Connection': 'keep-alive'
            }
            
            # Configure session with no read timeout
            session = requests.Session()
            session.keep_alive = False  # Disable keep-alive to prevent stale connections
            
            response = session.get(
                url, 
                headers=headers, 
                stream=True,
                timeout=(30, None)  # (connect timeout, read timeout=None for infinite)
            )
            response.raise_for_status()
            
            client = SSEClient(response.raw, char_enc='utf-8')
            logger.info("Successfully connected to SSE stream")
            
            # Reset retry count on successful connection
            retry_count = 0
            
            for event in client.events():
                try:
                    data = json.loads(event.data)
                    logger.info(f"Received SSE data")
                    process_update(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse SSE message: {str(e)}", exc_info=True)
                    continue  # Continue to next event on parse error
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}", exc_info=True)
                    continue  # Continue to next event on other errors
                    
        except (requests.exceptions.RequestException, TimeoutError) as e:
            logger.error(f"SSE connection error, attempting reconnection: {str(e)}", exc_info=True)
            
            # Clean up resources
            try:
                response.close()
                session.close()
            except:
                pass
            
            # Immediate retry for connection errors
            continue
            
        except Exception as e:
            retry_count += 1
            delay = min(base_delay * (2 ** retry_count), 60)  # Exponential backoff, max 60 seconds
            
            logger.error(
                f"Unexpected error (attempt {retry_count}/{max_retries}), "
                f"retrying in {delay} seconds: {str(e)}", 
                exc_info=True
            )
            
            if retry_count >= max_retries:
                logger.critical("Max retries reached, resetting retry count")
                retry_count = 0
            
            # Clean up resources
            try:
                response.close()
                session.close()
            except:
                pass
                
            time.sleep(delay)  # Wait before retrying

def start_router():
    """Start the SSE router in a separate thread."""
    logger.info("Initializing SSE router")
    
    # Use Config variables instead of hardcoded values
    url = f"{Config.BASE_URL}/discovery/updates?sources[]={Config.SOURCE}"
    
    thread = threading.Thread(target=router_thread, args=(url,), daemon=True)
    thread.start()
    return thread



# Add new route for SSE updates
@app.route('/')
def get_updates():
    """Stream updates to clients using Server-Sent Events based on specific prompt."""
    prompt = request.args.get('prompt')  # Use Config.PROMPT as default
    if not prompt:
        return Response("Missing 'prompt' parameter", status=400)

    # Create new router configuration if doesn't exist
    if prompt not in processor.active_routers:
        processor.active_routers[prompt] = RouterConfig(
            prompt=prompt,
            queue=queue.Queue(),
            created_at=datetime.now()
        )
    
    router_config = processor.active_routers[prompt]

    def generate():
        while True:
            try:
                # Get update from queue specific to this prompt, timeout after 30 seconds
                update = router_config.queue.get()
                yield f"data: {json.dumps(update)}\n\n"
            except queue.Empty:
                # Send keepalive
                yield ": keepalive\n\n"
            except Exception as e:
                logger.error(f"Error streaming update: {str(e)}")
                continue

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )

if __name__ == '__main__':
    # Start the router when the app starts

    router_thread = start_router()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=8000) 