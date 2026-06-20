# -*- coding: utf-8 -*-
"""
测试：能否通过 get_noumenon_from_instancekey 修改已有组件参数
在BIMBase底部命令行中输入：
    exec(open(r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard\test_noumenon_replace.py').read())
"""
from pyp3d import get_all_instancekey, get_noumenon_from_instancekey
import traceback

out_path = r"C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard\test_noumenon_output.txt"
with open(out_path, 'w', encoding='utf-8') as fout:
    def log(*args):
        line = ' '.join(str(a) for a in args)
        fout.write(line + '\n')
        print(line)
    
    keys = get_all_instancekey()
    log("Total instances:", len(keys))
    
    if not keys:
        log("No instances found. Please place a component first.")
    else:
        # 测试第一个实例
        k = keys[0]
        log("\n=== Testing first instance ===")
        
        try:
            noum = get_noumenon_from_instancekey(k)
            log("Type:", type(noum))
            log("Dir attrs:", [a for a in dir(noum) if not a.startswith('_')])
        except Exception as e:
            log("get_noumenon error:", e)
            traceback.print_exc()
            noum = None
        
        if noum:
            # 尝试获取所有键
            all_keys = []
            try:
                for key in noum:
                    all_keys.append(key)
            except Exception as e:
                log("Iterate error:", e)
            
            log("All keys:", all_keys)
            
            # 尝试读取参数值（用可能的基础名）
            test_params = ['a', 'b', 'h', 'length', 'width', 'height', 'radius', 'x', 'y', 'z']
            for p in test_params:
                try:
                    val = noum[p]
                    log(f"  noum['{p}'] = {val} (type={type(val)})")
                except Exception as e:
                    log(f"  noum['{p}'] ERROR: {e}")
            
            # 尝试修改参数
            log("\n--- Attempting to modify params ---")
            modified = False
            for p in test_params:
                try:
                    old_val = noum[p]
                    if isinstance(old_val, (int, float)) and old_val > 0:
                        new_val = old_val + 10
                        noum[p] = new_val
                        log(f"  SET noum['{p}'] = {new_val} (was {old_val})")
                        modified = True
                        break
                except Exception as e:
                    log(f"  SET noum['{p}'] failed: {e}")
            
            if modified:
                log("\n--- Calling replace() ---")
                try:
                    if hasattr(noum, 'replace'):
                        noum.replace()
                        log("replace() called successfully")
                    else:
                        log("noum has no replace() method")
                except Exception as e:
                    log("replace() error:", e)
                    traceback.print_exc()
            else:
                log("Could not modify any param, skip replace test")

log("\nDone. Check output at:", out_path)
