"""Simple test to verify the game can run without Redis/MinIO."""

import os
import sys

os.environ['RPG_STORAGE_TYPE'] = 'local'

sys.path.insert(0, '.')

def test_basic_imports():
    """Test that all core modules can be imported."""
    print('=' * 60)
    print('Testing Basic Imports...')
    print('=' * 60)

    from rpg_world_agent.data.db_client import DBClient
    from rpg_world_agent.data.llm_client import get_llm_client
    from rpg_world_agent.core.cognition import CognitionSystem
    from rpg_world_agent.core.player_character import PlayerCharacter

    print('All imports successful')
    return True

def test_storage_operations():
    """Test storage operations."""
    print('\n' + '=' * 60)
    print('Testing Storage Operations...')
    print('=' * 60)

    from rpg_world_agent.data.db_client import DBClient

    redis = DBClient.get_redis()
    redis.set('test_key', 'test_value')
    assert redis.get('test_key') == 'test_value'
    redis.delete('test_key')
    print('Redis (mock) operations successful')

    storage = DBClient.get_storage_adapter()
    test_data = {'test': 'data', 'value': 123}
    storage.save_json('test_file.json', test_data)
    loaded = storage.load_json('test_file.json')
    assert loaded == test_data
    storage.delete_object('test_file.json')
    print('Storage adapter operations successful')

    return True

def test_cognition_system():
    """Test CognitionSystem with save/load."""
    print('\n' + '=' * 60)
    print('Testing CognitionSystem...')
    print('=' * 60)

    from rpg_world_agent.core.cognition import CognitionSystem

    cog = CognitionSystem('test_session')

    cog.add_message('user', 'Hello!')
    cog.add_message('assistant', 'Welcome!')
    history = cog.get_recent_history()
    assert len(history) == 2
    print('Message operations successful')

    cog.update_player_state({'hp': 90, 'location': 'tavern'})
    state = cog.get_player_state()
    assert state['hp'] == 90
    assert state['location'] == 'tavern'
    print('State operations successful')

    cog.archive_session()
    cog2 = CognitionSystem('test_session')
    success = cog2.load_session()
    assert success
    print('Save/Load operations successful')

    cog2.clear_session()
    cog2.delete_save()
    print('Cleanup successful')

    return True

def main():
    """Run all tests."""
    print('\n' + '🎮' * 30)
    print('   RPG Agent - Local Development Tests')
    print('🎮' * 30 + '\n')

    try:
        test_basic_imports()
        test_storage_operations()
        test_cognition_system()

        print('\n' + '=' * 60)
        print('ALL TESTS PASSED!')
        print('=' * 60)
        print('\nThe game can now run without Redis/MinIO.')
        print('Set RPG_STORAGE_TYPE=local to use local file storage.')
        print('Set RPG_STORAGE_TYPE=minio to use MinIO (requires minio dependency).')
        print('=' * 60)

        return 0

    except Exception as e:
        print(f'\nTEST FAILED: {e}')
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
