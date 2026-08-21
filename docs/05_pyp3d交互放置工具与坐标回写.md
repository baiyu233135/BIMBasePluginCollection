# 05 - pyp3d 放置坐标获取与组件参数显示（铁路封闭网实战）

> 适用环境：BIMBase 2025，Plugin SDK 1.6.2，pyp3d v18446497937724801024（2024.10 Release）
> 试验件：`组件成品/铁路封闭网.py`（2026-08-21 实测通过）
> 源码依据：`pyp3d/v18446497937724801024/pyp3d_api.py`、`pyp3d_convention.py`、`runtime/__init__.py`

## 一、需求与最终结论

**需求**：组件放置后，属性面板的参数里能看到放置基准点的三轴坐标（X/Y/Z坐标）。

**最终方案（实测通过）**：组件的 `replace()` 里从 `self.transformation` 提取放置平移，
写入坐标参数。放置瞬间平移为零（跳过不写）；**后续任何重生成**（面板改参/点"修改"/
重开工程）时内核用已存储的实例数据重跑 replace，坐标自动写入。

```python
def _write_place_coords(self):
    """从 self.transformation 提取放置平移写入 X/Y/Z坐标（可复用模板）"""
    try:
        mat = getattr(self.transformation, '_mat', None)
        if not (isinstance(mat, (list, tuple)) and len(mat) == 3):
            return
        x, y, z = float(mat[0][3]), float(mat[1][3]), float(mat[2][3])
        if abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z) < 1e-9:
            return  # 放置瞬间（旋转未带平移）或原点放置，不写
        self['X坐标'] = x
        self['Y坐标'] = y
        self['Z坐标'] = z
    except Exception:
        pass
```

在 `replace()` 末尾调用即可。组件 `__init__` 里需先定义：
`self['X坐标'] = Attr(0.0, obvious=True)`（Y/Z 同理）。

**特性**：交互 100% 原生工具（顺滑）、零 RPC、零崩溃风险、全自动。
**代价**：坐标不是放置瞬间立即可见，而是下次重生成时补上；想立刻看就改一下任意参数。

## 二、核心技术要点（实测定论，务必记住）

### 1. "网长通道"：place_to 之前写进 data 的参数才会持久化

原生两点工具（`TwoPointPlace.linearize`）放置后 `网长` 参数自动显示拉伸长度，
因为工具在 `place_to` 之前把值写进了组件数据。**凡是在 place_to 之前进入 data 的
参数，都会持久化并显示在属性面板**。这是参数写回的唯一可靠通道。

### 2. replace() 在内核 service 进程执行，没有交互工具上下文

实测日志铁证（argv0 为 `D:\...\Support\service18446497937724801024.py`，
`__file__` 为 `C:\Users\...\AppData\Local\BIMBase\BFATemp\<hash>\铁路封闭网.py`）：

- 内核把组件数据发给 service 运行时，从 **BFATemp 缓存副本**重实例化并执行 replace
- 因此 `get_current_point()` / `get_dynamic_point()` 等工具取点 API 在 replace 里
  **恒返回 (0,0,0)**（不是异常，是零点）——无法用于捕获点击坐标
- 组件内写诊断日志时 `__file__` 指向缓存副本，需多路径兜底才能回收到日志

### 3. 实例的放置变换存储位置与提取

已放置实例的 noumKV（`get_noumKV_from_instancekey`）中：

- `'\x07_transformation'`（即 `'\a_transformation'`）与 `'\x07GraphicElement::m_transform'`
  均为 GeTransform，含完整放置平移
- `GeTransform._mat` 是 **3x4 行主序矩阵，平移在 `[i][3]`**
- 'Placement' / 'BaseTransform' 键存在但为 None
- 面板选中的"参数化组件代理"实体，其 datakey 的 noumKV 是**空的**；
  需 `get_all_instancekey()` 全扫 + `get_allbinding_entity_from_data()` 按绑定实体
  匹配（比较用 _ModelId/_ElementId 属性元组，**不可 str()**，退化 (None,None) 不可作匹配依据）

### 4. 两条失败路线的教训

- `noum[k]=v + noum.replace()` 直写：内核重实例化时按类定义重置参数，
  写入值被冲掉（回读验证实锤：written 2322.1 → 回读 0.0）
- `replace_noumenon(comp, ik)` 整体替换：重建的组件缺注册信息时**BIMBase 硬崩溃**；
  即使补全 `create_component()` 注册（DependentFile 等）仍崩。**此路禁用**。

### 5. 自定义 interact 工具（Python 回调）的性能下限

机制：`'interact'` 插槽（`PARACMPT_KEYWORD_INTERACT`）注册 `func(data, context)`，
context 含 `action`（left down/mouse movement/right down）与 `point`（点击世界坐标）。
参考实现 `pyp3d_api.interact_liner`。

**坐标捕获它是能做的**（落点时写 data 参数，同"网长通道"），但鼠标每次移动，
内核都要把整个组件数据跨进程封送给 Python 回调——重组件（数百图元）必然卡顿，
剥几何/轻量预览/30fps 节流也只能缓解，**永远达不到原生工具的跟手度**。
结论：轻量组件可用自定义 interact 捕获坐标；重组件用本文最终方案。

## 三、探索历程（铁路封闭网，2026-08-13 ~ 08-21）

| 尝试 | 结果 | 缺点/失败原因 |
|---|---|---|
| ① 事后回写按钮：读 transformation + noum 直写 | 读取成功，写入无效 | 内核重实例化冲掉写入值（回读实锤） |
| ② replace_noumenon 整体替换 | BIMBase 崩溃 ×2 | 重建组件注册信息不全；补全后仍崩，弃用 |
| ③ 自定义 interact 两点工具 | 坐标写入成功但卡顿 | 鼠标每事件封送整个组件数据；剥几何+节流后可用但不如原生 |
| ④ 原生工具 + replace 内调取点 API | 恒返回 (0,0,0) | replace 在 service 进程执行，无工具上下文（日志实锤） |
| ⑤ **replace 从 self.transformation 提取** | ✅ 实测通过 | 坐标非放置瞬间立即可见，下次重生成补上 |

辅助发现：全场景扫描兜底匹配时，1944 实例逐个 RPC 需分钟级（表现为"没反应"），
找到即停 + 进度日志后约 11 秒命中；该回写脚本已完成使命，**已删除**。

## 四、官方放置工具速查（同一 'interact' 插槽机制）

`pyp3d_api.py` 内置工具类，均往 `'interact'` 插槽注册内核函数：

| 工具类 | 用途 | 回写参数 |
|---|---|---|
| `TwoPointPlace.linearize(data, key)` | 两点拉伸 | key 参数 = 拉伸长度 |
| `RotationPlace.RotationFunction(data)` | 两点定旋转角 | — |
| `MultiPointPlace.MultiPointFunction(data, key)` | 多点 | key 参数 = 点击点列表 |
| `BoardPlace.BoardPlaceFunction(data, key)` | 板布置 | — |
| `CombineLinePlace.CombineLinePlaceFunction(data, key)` | 组合线布置 | — |

> 注：`MultiPointPlace` 会把点击点列表写进参数（纯数据流，service 上下文无关），
> 适合"多点坐标入参"型组件；但放置语义是多点而非两点拉伸。

自定义工具注册（轻量组件可用）：

```python
data['interact'] = Attr(UnifiedFunction(my_interact_func), member=True)  # 函数须在模块级
```

## 五、相关文档

- 组件颜色/透明度：`docs/04_pyp3d颜色与透明度.md`
- 本轮过程记录：`docs/对话记录/组件成品01.txt`
