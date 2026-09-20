# 桥隧病害网站数据导出汇总

- 导出时间：2026-09-10 12:32:25
- 记录总数：**4**（桥梁 4 条，隧道 0 条）
- 缺失 3D 坐标记录：0 条；照片文件缺失：4 条
- 数据文件：`web_disease_data.json`（与本文件同目录）

## 按病害类型统计

| 病害类型 | 总数 | 桥梁 | 隧道 |
| --- | ---: | ---: | ---: |
| 异常区域 | 3 | 3 | 0 |
| 剥落 | 1 | 1 | 0 |

## 按严重程度统计

| 严重程度 | 总数 | 桥梁 | 隧道 |
| --- | ---: | ---: | ---: |
| 未填写 | 4 | 4 | 0 |

## 按构件统计

| 构件类型 | 总数 | 桥梁 | 隧道 |
| --- | ---: | ---: | ---: |
| T梁 | 3 | 3 | 0 |
| 引桥桥墩 | 1 | 1 | 0 |

## 缺失 3D 坐标的记录（前 20 条，共 0 条）

无

## 照片文件缺失的记录（前 20 条，共 4 条）

| id | 来源 | 照片路径 |
| --- | --- | --- |
| 72d2bd04 | bridge | `桥隧病害识别/datasets/bridge_disease/by_component/T梁/6_img_0004.png` |
| ba8580c1 | bridge | `桥隧病害识别/datasets/bridge_disease/by_component/T梁/6_img_0004.png` |
| d9d2c1dd | bridge | `桥隧病害识别/datasets/bridge_disease/by_component/T梁/6_img_0003.png` |
| b4b13438 | bridge | `桥隧病害识别/datasets/bridge_disease/by_component/墩柱/7_img_0853.png` |

## 数据对接说明（CIMPro 孪大师 / three.js）

### JSON 结构

```json
{
  "meta": { ... },        // 导出元信息（见下）
  "diseases": [ { ... } ],// 病害记录数组，一病一条
  "stats": { ... }        // 分类统计
}
```

- `meta.exported_at`：导出时间；`meta.total` / `bridge_count` / `tunnel_count`：记录数
- `meta.suggested_model`：留给用户填写的项目/模型信息（`project` 建议填如 `"常泰长江大桥"`）
- `meta.coordinate_system` / `meta.unit`：坐标说明。坐标为 **BIMBase 世界坐标，单位 mm，Y 轴向上**，具体坐标系以模型为准。three.js 中 Y 向上、默认单位为米，放置标记时需自行缩放（如 `position/1000`）并确认轴向。
- `diseases[i]` 关键字段：`source`(bridge/tunnel)、`id`、`tunnel_or_bridge_name`、`component`(构件类型)、`disease`(病害类型)、`severity`、`position:{x,y,z}`（无 3D 坐标时为 `null`）、`bbox`（照片像素框）、`photo`（相对项目根的照片路径，`photo_exists=false` 表示文件缺失）、`dimensions`（可选，`length_mm`/`width_mm`/`area_mm2`）、`diagnosis`（可选，AI 诊断摘要）

### 加载示例（three.js）

```js
fetch('web_disease_data.json')
  .then(r => r.json())
  .then(data => {
    const MM_PER_M = 1000;  // 数据单位为 mm，three.js 按米
    for (const d of data.diseases) {
      if (!d.position) continue;          // 无坐标的跳过
      const p = new THREE.Vector3(
        d.position.x / MM_PER_M,
        d.position.y / MM_PER_M,
        d.position.z / MM_PER_M);
      const color = d.source === 'bridge' ? 0xff4444 : 0xffa500;
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(0.3, 16, 16),
        new THREE.MeshBasicMaterial({ color }));
      marker.position.copy(p);
      marker.userData = d;   // 整条记录挂到 userData，点击可弹详情
      scene.add(marker);
    }
  });
```

### CIMPro 孪大师对接

1. 把 `web_disease_data.json` 及照片目录（如 `桥梁病害识别/datasets/`）一并放到可访问的 Web 目录或文件服务；
2. CIMPro 的 Web/API 组件按上述字段取 `position` 放置标记，`disease`/`severity`/`dimensions` 做弹窗与筛选；
3. 若平台坐标系与 BIMBase 不一致（如 Z 向上），在加载层做一次轴变换即可。
