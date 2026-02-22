# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an LLM-driven TRPG (Tabletop Role-Playing Game) engine. The system generates dynamic worlds, manages player sessions, and serves as an AI Dungeon Master with intelligent narrative responses.

## Common Commands

### Running the Game
```bash
python main.py               # Start the interactive game
```

### World Initialization
```bash
python init_world.py         # Interactive world initialization menu
python init_world.py default # Use default map (no LLM generation)
python init_world.py list    # List existing maps in Redis
python init_world.py clear   # Clear all map data from Redis
```

### Testing Storage
```bash
python test_storage.py        # Test Redis and MinIO connections
```

### Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Core Systems

**RuntimeEngine** (`core/runtime.py`) - The game engine/Dungeon Master
- Main game loop via `step(user_input: str) -> str`
- Intent analysis: EXPLORE (new location), ACTION (game actions), CHAT (narrative)
- AI Director: probabilistic crisis triggering based on location risk level
- Handles `/move`, `/look`, and natural language commands

**CognitionSystem** (`core/cognition.py`) - Session state management
- Redis-backed conversation history (sliding window context)
- Player state (HP, sanity, location, tags, skills, inventory)
- Save/load to MinIO (`archive_session()`, `load_session()`)
- Static `list_saves()` for browsing available saves

**MapTopologyEngine** (`core/map_engine.py`) - Graph-based map system
- Redis-backed node graph (`rpg:map:node:*`, `rpg:map:edges:*`)
- AI-generated route descriptions between nodes via `_generate_route_concept()`
- `ingest_l2_graph()` - converts generated regions to engine nodes
- `create_dynamic_sub_location()` - on-demand location generation for exploration

**WorldGenerator** (`core/genesis.py`) - World generation pipeline
- Multi-stage: config Step 1 (world info), Step 2 (map regions), Step 3 (NPCs)
- `ingest_to_map_engine()` - hands off L2 blueprint to MapEngine
- Uses `ContentGenerator` for prompt building

**PlayerCharacter** (`core/player_character.py`) - D&D 5e-style character system
- 6 attributes (STR, DEX, INT, WIS, CON, CHA) with D&D 5e modifiers
- Skill proficiency (1-5) maps to attributes
- HP, Sanity, Stamina tracking
- Inventory with equipment slots

### Data Layer

**DBClient** (`data/db_client.py`) - Singleton storage factories
- `get_redis()` - singleton Redis connection with configurable TTL
- `get_minio()` - singleton MinIO client with auto-bucket creation
- `save_json_to_minio()`, `load_json_from_minio()` - JSON helpers

**LLMClientFactory** (`data/llm_client.py`) - Singleton LLM client
- `get_llm_client()` - returns OpenAI-compatible client
- Uses `AGENT_CONFIG["llm"]` for base_url, api_key, model, timeout

### Configuration

**`AGENT_CONFIG` in `config/settings.py`** - Central configuration
- LLM settings (base_url, api_key, model, temperature, max_tokens)
- Redis (host, port, password, db, ttl)
- MinIO (endpoint, access_key, secret_key, bucket_name)
- World settings (genre, tone, final_conflict)
- Stage token limits (genesis, narrator, map_gen, cognition)

**`config/` Directory:**
- `seeds.py` - Crisis seeds for world generation
- `rules.py` - Valid skills, tag categories, knowledge levels
- `tool_schemas.py` - Tool definitions for WorldBuilderAgent

### Entry Points

- **`main.py`** - Interactive CLI game with `/look`, `/move`, `/status`, `/map`, `/save`, `/load`, `/exits` commands
- **`init_world.py`** - Standalone world generation tool with CLI menu
- **`test_storage.py`** - Storage connection validation

## Key Integration Patterns

**Session Initialization Flow:**
1. Check Redis/MinIO connectivity
2. Load existing save or initialize new world via `WorldGenerator`
3. Create `RuntimeEngine` with session_id and LLM client
4. `engine.initialize_player(start_location, initial_tags)`
5. `engine.step("/look")` for initial description

**Game Turn Flow:**
1. User input → `RuntimeEngine.step()`
2. Add to CognitionSystem history
3. Route to handler: `_handle_move()`, `_handle_look()`, or `_handle_natural_language()`
4. For natural language: `_analyze_intent()` → EXPLORE/ACTION/CHAT
5. LLM generates response → add to history → update player state if needed

**Storage Key Patterns:**
- `rpg:map:node:{node_id}` - Map node data
- `rpg:map:edges:{node_id}` - Hash of outbound connections
- `rpg:history:{session_id}` - List of conversation messages
- `rpg:state:{session_id}` - Hash of player state
- `rpg:meta:{session_id}` - Session metadata
- `saves/{session_id}.json` - MinIO save archive

## Environment Variables

All configuration supports environment variable overrides (see `config/settings.py`):
- `RPG_GENRE`, `RPG_TONE`, `RPG_FINAL_CONFLICT`
- `RPG_LLM_BASE_URL`, `RPG_LLM_API_KEY`, `RPG_LLM_MODEL`, `RPG_LLM_TEMPERATURE`, `RPG_LLM_MAX_TOKENS`
- `RPG_MINIO_ENDPOINT`, `RPG_MINIO_ACCESS_KEY`, `RPG_MINIO_SECRET_KEY`, `RPG_MINIO_BUCKET`
- `RPG_REDIS_HOST`, `RPG_REDIS_PORT`, `RPG_REDIS_PASSWORD`, `RPG_REDIS_DB`, `RPG_REDIS_TTL`