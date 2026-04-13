# Setup Guide — Instagram Agent System

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd brandpilot
pip install -e .
```

### 2. Create your brand profile

```bash
cp -r brands/_template brands/my-company
```

### 3. Configure your brand

Edit `brands/my-company/config.yaml`:
- Fill in your brand identity (name, language, market, business type)
- Define your brand voice and caption style
- Set your visual identity and image generation prompts
- Configure your content strategy (post frequency, pillars)
- Set your schedule (planning day, publish times, etc.)

### 4. Add your credentials

```bash
cp brands/_template/.env.example brands/my-company/.env
```

Edit `brands/my-company/.env` with your API keys:
- **Instagram/Meta**: App ID, secret, access token, account ID
- **Telegram**: Bot token, chat ID
- **Image generation**: fal.ai key
- **Image hosting**: Cloudinary credentials
- **Web search**: Tavily API key
- **LLM**: OpenAI key (or set LLM_PROVIDER=ollama for local)

### 5. Write your content guide

Edit `brands/my-company/CONTENT_GUIDE.md`:
- List your products/menu items by category
- Write detailed image generation prompts for each item
- Add vibe/lifestyle shot descriptions
- Set your global negative prompt

### 6. Write your design guide

Edit `brands/my-company/DESIGN.md`:
- Define your color palette
- Specify typography
- Describe your visual language

### 7. Run

```bash
# Run a single task
python main.py --brand my-company content

# Start the full autonomous daemon
python daemon.py --brand my-company

# Interactive mode
python main.py --brand my-company interactive
```

## Running Multiple Brands

Each brand runs as a separate process with its own database and credentials:

```bash
# Terminal 1
python daemon.py --brand company-a

# Terminal 2
python daemon.py --brand company-b
```

Or use the `BRAND` environment variable:

```bash
BRAND=my-company python daemon.py
```

## Available Commands

| Command | Description |
|---------|-------------|
| `content` | Run content planning (creates weekly posts) |
| `design` | Run design review on drafts |
| `images` | Generate images for drafts |
| `analytics` | Run analytics collection |
| `leads` | Run lead generation |
| `engagement` | Run engagement advisor |
| `publish` | Publish approved feed posts |
| `stories` | Publish approved stories |
| `review` | Review performance & adjust upcoming content |
| `interactive` | Chat with a specific agent |

## Brand Directory Structure

```
brands/
  my-company/
    config.yaml          # Brand identity, voice, visual style, schedule
    .env                 # API credentials (gitignored)
    CONTENT_GUIDE.md     # Product/menu items with image prompts
    DESIGN.md            # Brand design system
```
