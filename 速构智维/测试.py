from pyp3d import get_all_instancekey, get_noumKV_from_instancekey, get_noumenon_from_instancekey
import traceback

out_path = r"C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维\p3d_test_output.txt"
with open(out_path, 'w', encoding='utf-8') as fout:
    def log(*args):
        line = ' '.join(str(a) for a in args)
        fout.write(line + '\n')
        print(line)
    
    keys = get_all_instancekey()
    log("keys count:", len(keys))
    
    # 连续调用两次同一个key
    k = keys[0]
    log("\n--- same key, call 1 ---")
    try:
        p1 = get_noumKV_from_instancekey(k)
        log("result1 keys:", list(p1.keys())[:5] if p1 else "None")
    except Exception as e:
        log("error1:", e)
    
    log("\n--- same key, call 2 ---")
    try:
        p2 = get_noumKV_from_instancekey(k)
        log("result2 keys:", list(p2.keys())[:5] if p2 else "None")
    except Exception as e:
        log("error2:", e)
    
    # 连续调用两个不同key
    if len(keys) > 1:
        k2 = keys[1]
        log("\n--- different key, call 3 ---")
        try:
            p3 = get_noumKV_from_instancekey(k2)
            log("result3 keys:", list(p3.keys())[:5] if p3 else "None")
        except Exception as e:
            log("error3:", e)
    
    # 测试 get_noumenon_from_instancekey 后能否遍历键
    log("\n=== test get_noumenon_from_instancekey iterate ===")
    for i in range(min(3, len(keys))):
        k = keys[i]
        log(f"\n--- key {i} ---")
        try:
            noum = get_noumenon_from_instancekey(k)
            # 尝试遍历所有键
            all_keys = []
            try:
                for key in noum:
                    all_keys.append(key)
            except Exception as e:
                log("iterate error:", e)
            log("all keys count:", len(all_keys))
            # 显示前20个键
            for key in all_keys[:20]:
                try:
                    val = noum[key]
                    log(f"  {key}: {val}")
                except Exception as e:
                    log(f"  {key}: <error {e}>")
        except Exception as e:
            log("get_noumenon error:", e)
