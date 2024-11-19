# Semantic Router

A trustless, privacy-preserving semantic routing agent that processes and evaluates content updates using LLM providers. Built with end-to-end TEE (Trusted Execution Environment) architecture for complete operational blindness - no one, including the operators, can see what's being processed or who is using it.

## Features

- Real-time content filtering using Server-Sent Events (SSE)
- End-to-end TEE architecture:
  - [Lit Protocol](https://litprotocol.com/) for secure key management and configuration
  - [OpenGradient](https://opengradient.ai/) for private LLM inference
  - [Fleek](https://fleek.network/) for secure TEE-based decentralized runtime
  - IPFS for decentralized prompt storage
- Completely blind operation - no visibility into prompts or users
- Decentralized LLM provider support ( OpenGradient)
- Secure configuration management using Lit Protocol
- Customizable semantic evaluation based on prompts
- Robust error handling and automatic reconnection
- Configurable filtering criteria
- Multiple data source integrations:
  - Farcaster
  - Lu.ma (coming soon)
  - Paragraph.xyz (coming soon)

## Architecture

The system operates entirely within TEEs (Trusted Execution Environments):
- Configuration and key management runs in Lit Protocol's TEE network
- LLM inference executed privately in OpenGradient's secure enclaves
- Agent runtime executed in Fleek's TEE infrastructure for secure computation

This architecture ensures that no single party, including the system operators, can access or view:
- User identities
- Submitted prompts
- Processing results
- Runtime operations

## Prerequisites

- Python 3.8+
- Node.js 16+
- Google Cloud Project (for Gemini)
- OpenGradient account
- Lit Protocol setup
- IPFS node (optional, for self-hosting prompts)

## Installation

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/indexnetwork/semantic-router
cd semantic-router
```

2. Build and run the Docker container:
```bash
docker build -t semantic-router .
docker run -p 8000:8000 semantic-router
```

3. Connect to the agent's SSE endpoint:

```bash
curl -N "http://localhost:8000/?prompt=If+its+a+significant+update+on+decentralized+AI+and+autonomous+agents."
```

## API

### GET /

Streams semantic evaluation results for the provided prompt.

Query Parameters:
- `prompt`: Your prompt, could be anything.

Response: Server-Sent Events stream with JSON payloads

## License

MIT License - see [LICENSE](LICENSE) file for details.