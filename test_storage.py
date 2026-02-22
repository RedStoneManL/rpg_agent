"""测试MinIO和Redis连接"""
import sys
import os

from data.db_client import DBClient
from config.settings import AGENT_CONFIG

def test_minio():
    """测试MinIO连接"""
    print("=" * 50)
    print("测试 MinIO 连接...")
    print("=" * 50)

    try:
        minio_client = DBClient.get_minio()
        print(f"✅ MinIO 连接成功！")
        print(f"   Endpoint: {AGENT_CONFIG['minio']['endpoint']}")
        print(f"   Bucket: {AGENT_CONFIG['minio']['bucket_name']}")

        # 列出buckets
        buckets = minio_client.list_buckets()
        print(f"   可用Buckets: {[b.name for b in buckets]}")

        # 测试写入
        test_data = {"test": "hello_minio", "timestamp": "2025-02-05"}
        test_object = "test/connection_test.json"
        DBClient.save_json_to_minio(test_object, test_data)
        print(f"   ✅ 测试写入: {test_object}")

        # 测试读取
        loaded_data = DBClient.load_json_from_minio(test_object)
        print(f"   ✅ 测试读取: {loaded_data}")

        return True

    except Exception as e:
        print(f"❌ MinIO 连接失败: {e}")
        return False

def test_redis():
    """测试Redis连接"""
    print("\n" + "=" * 50)
    print("测试 Redis 连接...")
    print("=" * 50)

    try:
        redis_client = DBClient.get_redis()
        print(f"✅ Redis 连接成功！")
        print(f"   Host: {AGENT_CONFIG['redis']['host']}:{AGENT_CONFIG['redis']['port']}")
        print(f"   DB: {AGENT_CONFIG['redis']['db']}")

        # 测试写入
        test_key = "rpg:test:connection"
        redis_client.set(test_key, "test_value")
        print(f"   ✅ 测试写入: {test_key} = 'test_value'")

        # 测试读取
        value = redis_client.get(test_key)
        print(f"   ✅ 测试读取: {value}")

        # 清理
        redis_client.delete(test_key)
        print(f"   ✅ 清理测试数据")

        return True

    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return False

if __name__ == "__main__":
    minio_ok = test_minio()
    redis_ok = test_redis()

    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"MinIO: {'✅ 正常' if minio_ok else '❌ 失败'}")
    print(f"Redis: {'✅ 正常' if redis_ok else '❌ 失败'}")

    if minio_ok and redis_ok:
        print("\n🎉 存储系统全部就绪，可以开始构建游戏！")
        sys.exit(0)
    else:
        print("\n⚠️ 存储系统存在问题，请检查配置")
        sys.exit(1)