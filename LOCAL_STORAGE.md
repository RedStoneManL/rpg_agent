Local Storage Setup
==================

This project now supports local file storage for save games, removing the dependency on MinIO for local development.

Quick Start
-----------

Running the Game

To run the game with local file storage (no Redis/MinIO required):

    export RPG_STORAGE_TYPE=local
    python main.py

Storage Options
---------------

The game supports two storage backends:

1. Local File Storage (default) - Saves to ./saves/ directory
2. MinIO Storage - Requires MinIO server and dependencies

Local File Storage
------------------

    export RPG_STORAGE_TYPE=local
    python main.py

Save files are stored as JSON in the ./saves/ directory with the following structure:
    saves/
      └── saves/
          └── {session_id}.json

MinIO Storage
-------------

    # Install minio dependency first
    pip install minio>=7.2.0

    # Set environment variable
    export RPG_STORAGE_TYPE=minio

    # Configure MinIO settings (optional, defaults in config/settings.py)
    export RPG_MINIO_ENDPOINT=your-minio-server:9000
    export RPG_MINIO_ACCESS_KEY=your-access-key
    export RPG_MINIO_SECRET_KEY=your-secret-key

    # Run the game
    python main.py

Environment Variables
---------------------

Variable                   Default                        Description
---------------------      -----------------------        ---------------------------
RPG_STORAGE_TYPE           local                          Storage backend: local or minio
RPG_STORAGE_PATH           ./saves                        Base path for local file storage
RPG_MINIO_ENDPOINT         100.102.191.200:9000           MinIO server endpoint
RPG_MINIO_ACCESS_KEY       minioadmin                     MinIO access key
RPG_MINIO_SECRET_KEY       minioadmin                     MinIO secret key
RPG_MINIO_BUCKET           rpg-world-data                  MinIO bucket name

Redis Notes
-----------

For local development, the game will automatically use a mock Redis implementation if the real Redis server is not available. This allows full game functionality without running Redis.

To use a real Redis server:

    export RPG_REDIS_HOST=localhost
    export RPG_REDIS_PORT=6379
    export RPG_REDIS_PASSWORD=
    export RPG_REDIS_DB=0

Testing
-------

Run the local storage tests:

    python test_local.py

Migration
---------

Existing MinIO saves can still be loaded. The game will automatically use the configured storage backend.

From MinIO to Local
-------------------

If you have saves in MinIO and want to migrate to local storage:

1. Set RPG_STORAGE_TYPE=minio
2. Load each save and re-save it
3. Set RPG_STORAGE_TYPE=local

The save file format is identical (JSON), so manual migration is also possible by copying the JSON files from MinIO to the ./saves/ directory.
