# Index Semantic Router

A trustless, privacy-preserving semantic routing agent that processes and evaluates content updates using LLM providers. Built with end-to-end TEE (Trusted Execution Environment) architecture for complete operational blindness - no one, including the operators, can see what's being processed or who is using it.

## Features

- Real-time content filtering using Server-Sent Events (SSE)
- End-to-end TEE architecture:
  - [Lit Protocol](https://litprotocol.com/) for secure key management and configuration
  - [OpenGradient](https://opengradient.ai/) for private LLM inference
  - [Fleek](https://fleek.network/) for secure TEE-based decentralized runtime
  - IPFS for decentralized prompt storage
- Multiple data source integrations:
  - Farcaster
  - Lu.ma (coming soon)
  - Paragraph.xyz (coming soon)

## Prerequisites

- Python 3.8+
- Node.js 16+
- Google Cloud Project (for Gemini)
- OpenGradient account
- Lit Protocol setup
- IPFS node (optional, for self-hosting prompts)

## Installation

### Using Pre-built Image

1. Pull and run the official Docker image:
```bash
docker pull indexnetwork/semantic-router:0.0.2
docker run -p 8000:8000 --env ROUTER_CONFIG="<YOUR_CONFIG>" indexnetwork/semantic-router:0.0.2
```

> **Note**: Contact hello@index.network for testing purposes to obtain the ROUTER_CONFIG value. Do not share this configuration directly.

### Using Docker (Build from Source)

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