import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    print("\n--- Testing Health Check ---")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health Check Passed!")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"❌ Health Check Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health Check Error: {e}")

def test_verify():
    print("\n--- Testing Single Verification ---")
    payload = {"query": "吃洋葱能治感冒吗？", "use_cache": True, "detailed": False}
    try:
        response = requests.post(f"{BASE_URL}/verify", json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Verification Passed!")
                print(f"Verdict: {data.get('verdict')}")
                print(f"Confidence: {data.get('confidence')}")
                print(f"Time: {data.get('execution_time_ms'):.2f}ms")
            else:
                print(f"❌ Verification Logic Failed: {data.get('error')}")
        else:
            print(f"❌ Verification HTTP Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Verification Error: {e}")

def test_batch_verify():
    print("\n--- Testing Batch Verification ---")
    payload = {
        "queries": ["吃洋葱能治感冒吗？", "喝水会中毒吗？"],
        "use_cache": True
    }
    try:
        response = requests.post(f"{BASE_URL}/batch-verify", json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            print("✅ Batch Verification Passed!")
            print(f"Total: {data.get('total')}, Successful: {data.get('successful')}")
            print(json.dumps(data.get('results'), indent=2, ensure_ascii=False)[:200] + "...")
        else:
            print(f"❌ Batch Verification Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Batch Verification Error: {e}")

def test_verify_stream():
    print("\n--- Testing Streaming Verification ---")
    payload = {"query": "吃洋葱能治感冒吗？", "use_cache": False, "detailed": False}
    try:
        with requests.post(f"{BASE_URL}/verify-stream", json=payload, stream=True, timeout=60) as response:
            if response.status_code != 200:
                print(f"❌ Streaming HTTP Failed: {response.status_code}")
                print(response.text)
                return
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                data = json.loads(line.strip())
                print(f"{data.get('type')}: {data}")
                if data.get("type") in ("result", "error"):
                    break
    except Exception as e:
        print(f"❌ Streaming Verification Error: {e}")

if __name__ == "__main__":
    time.sleep(3)
    test_health()
    test_verify()
    test_batch_verify()
    test_verify_stream()
