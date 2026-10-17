# P2 地图、演示数据与离线资源

地图采用 MapLibre GL 6.14.0、deck.gl 9.4.0、luma.gl 9.4.0，精确版本见 `apps/web/package-lock.json`。MapLibre 管理底图、聚合与镜头，deck.gl 绘制风险范围、计划路线、回放轨迹与模拟位置；订单业务依赖使用 ReactFlow。兼容方式参考 [deck.gl 官方文档](https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre)。

## 来源与坐标

| 资源 | 来源与授权 | 用途 |
|---|---|---|
| land.geojson | Natural Earth v5.1.2，1:50m land，[公共领域条款](https://www.naturalearthdata.com/about/terms-of-use/) | 海陆轮廓；删除无关属性，保留原几何 |
| map-ui.woff2 | Noto Sans CJK SC Regular 字体子集，SIL OFL 1.1 | 地图中文标注，不请求在线字形 |
| maplibre-gl-worker.mjs | npm maplibre-gl 6.14.0，BSD-3-Clause | 同源本地 Worker |
| manufacturing-v1.json | 本项目制造业合成样例，沿用 P1 | 企业、订单、BOM、事件、站点 |
| network-v1.json | 本项目人工编排的合成运输数据 | 8 个运输批次的路线、轨迹、里程碑与 ETA 更新 |

资源位于 `apps/web/public/maps/`，`manifest.json` 记录来源、字节数、SHA256、依赖版本；目录包含字体和 MapLibre 授权文本。三项核心资源合计 2,308,475 字节。无在线瓦片、sprite、glyph 或地图密钥依赖。

统一使用 WGS84 经纬度；底图仅用于地理概览，未包含行政区划和道路导航。线路为演示路线，轨迹为合成采样及线性插值，风险覆盖圆为展示参数。它们不能用于实际运输导航、行政边界判断或真实灾害范围判断。接入其他坐标源时须先转换，不能直接混用。

## 时间与数据口径

演示回放区间为北京时间 2026-10-16 00:00—09:00。事件按发现时间出现；ETA 按更新获知时间生效；里程碑实际完成时间与轨迹均裁切到当前回放时点。未来计划路线、计划里程碑可以展示，但不表示已经发生。插值位置明确标为模拟。

接口 `GET /api/v1/business/network`、`/business/shipments`、`/business/shipments/{shipment_id}` 支持统一场景、时间和筛选。参数为 `scenario_id`、`at_time`（带时区）、`supplier_id`、`mode`、`q`、`risk_only`。未知场景/批次返回 404，非法时间/运输方式返回 422，未认证返回 401。数据在服务端加入当前租户上下文；不访问外部 LLM。

前端一次取得当前场景的完整合成快照，在回放时进行同口径投影；敞口按风险订单 ID 去重，以整数分汇总，后端使用 Decimal。客户端隐藏未来记录属于演示回放，不能替代生产系统历史快照的访问控制。

## 离线机制

联网登录后点击“准备离线演示”，等待成功提示，再断网刷新 `/supply-chain` 或 `/tracking`。必须使用 localhost/127.0.0.1 或 HTTPS 的安全上下文，并允许 Service Worker、本地存储和 WebGL。

Service Worker 仅缓存两页公共页面壳、同源静态脚本、地图与字体；不缓存 API、认证响应或 token。三个合成场景按租户和用户单独存放 localStorage；退出登录清除合成快照。离线允许查看已有合成演示，界面标明未实时验证登录，管理页面与写入操作不可用。恢复网络后重新向服务端验证账号。此机制专用于公开合成演示，接入真实企业数据前必须重新设计敏感数据缓存策略。

新版本若改变未带哈希的地图资源或缓存规则，应同步升级 `map-sw.js` 与 `lib/network.ts` 中的缓存版本；开发调试可在浏览器 Application → Service Workers 注销、Cache Storage 删除本项目缓存后重新准备。

WebGL 不可用、资源错误或 `?fallback=1` 时显示可操作的站点、运输与订单列表。`?benchmark=1` 仅管理员可开启，使用确定性生成的 1,000 站点/2,000 路线测绘制负载，不代表客户规模或真实业务数据。
