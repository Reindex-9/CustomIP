// =========================================================================
// Mihomo / Clash Verge / FlClash 全局预处理脚本 v3.3
// 最新更新：2026-11-26
// =========================================================================
// 功能概览：
// 1. 多静态 IP 独立手动链路：每个静态 IP 生成独立的「🏠 静态 · <name>」select 组与专属隐藏探针，
//    不启后台 url-test 探活，避免并发测速触发静态 IP 风控，且多 IP 选同地区不同前置节点互不冲突
// 2. 精选截断与地区兜底：从完整 nodes 达标池中取当前存活的前 N 个（默认 15），底部附带 region 地区组兜底
// 3. 规则与 DNS 联动：由 rulesets 统一驱动分流与加密 DNS 出口，通用化公告词过滤
// =========================================================================

// ╔═══════════════════════════════════════════════════════════════════════╗
// ║  个人静态代理配置区（FlClash 等无 Merge 功能的客户端直接维护此块）       ║
// ║  优先级：Merge.yaml 的 static-proxies > 旧版 static-proxy > 本配置块   ║
// ╚═══════════════════════════════════════════════════════════════════════╝
const STATIC_CONFIG = {
  maxStaticNodes: 15,        // 单个静态 IP 面板最多显示的精选前置节点数
  currentAirport: "",        // 单机场订阅去前缀匹配辅助名（FlClash 不传订阅名时可在此指定当前机场名）
  staticProxies: [
    // server 留空则跳过；nodes 可直接从 latest_recommendation_flclash.js 复制粘贴
    {
      name: "美国",          // 面板显示名与测速目标名（勿留空或重名；改名会导致已记忆的策略组选中状态重置）
      type: "socks5",        // 支持 socks5 / http / vless / trojan / ss / hysteria2 等任意 Mihomo 协议
      server: "",            // 静态 IP 地址或域名（留空或填占位符则跳过该条目）
      port: 7213,            // 端口号 (1 - 65535)
      username: "",          // 鉴权用户名（无鉴权可留空或删除；多条共用同 IP:端口 网关时脚本会自动按此隔离历史库）
      password: "",          // 鉴权密码（无鉴权可留空或删除）
      udp: true,             // 是否启用 UDP 转发
      region: "US",          // 底部兜底地区组（仅挂载对应地区组，不挂 Auto；如 "US" 或 "JP,SG"）
      nodes: [],             // 达标前置节点池：直接粘贴 latest_recommendation.yaml 中对应段落的 nodes
    },
    {
      name: "日本",
      type: "socks5",
      server: "",
      port: 7213,
      username: "",
      password: "",
      udp: true,
      region: "JP",
      nodes: [],
    },
  ]
};


// ╔═══════════════════════════════════════════════════════════════════════╗
// ║  通用配置区 (USER_CONFIG)                                             ║
// ╚═══════════════════════════════════════════════════════════════════════╝
const USER_CONFIG = {
  // 1. Merge.yaml 注入的临时字段名（脚本读取后立即删除，避免 Mihomo 报未知字段）
  staticProxiesKey: "static-proxies",
  legacyStaticProxyKey: "static-proxy",
  maxStaticNodesKey: "max-static-nodes",
  currentAirportKey: "current-airport",

  // 2. 地区策略组定义（按国旗聚合，自动生成隐藏 url-test 组；aliases 为 region 字段支持的地区级缩写）
  regionGroups: [
    { id: 1, name: "🇺🇸 美国",   auto: "⚡ 美国自动",   flags: ["🇺🇸"], aliases: ["US", "USA", "AMERICA"] },
    { id: 2, name: "🇨🇳 港澳台", auto: "⚡ 港澳台自动", flags: ["🇭🇰", "🇹🇼", "🇲🇴"], aliases: ["HKTW", "HKTWMO", "GAT", "GREATERCHINA"] },
    { id: 3, name: "🌏 日韩新", auto: "⚡ 日韩新自动", flags: ["🇯🇵", "🇰🇷", "🇸🇬"], aliases: ["JPKRSG", "EA", "EASTASIA", "APAC"] },
    { id: 4, name: "🇪🇺 欧洲",   auto: "⚡ 欧洲自动",   flags: ["🇩🇪", "🇬🇧", "🇫🇷", "🇮🇹", "🇳🇱"], aliases: ["EU", "EUR", "EUROPE"] },
    { id: 5, name: "🛒 低价区", auto: "⚡ 低价区自动", flags: ["🇹🇷", "🇦🇷", "🇳🇬", "🇮🇳", "🇧🇷", "🇵🇭", "🇪🇬", "🇺🇦", "🇵🇰", "🇮🇩", "🇲🇾", "🇹🇭", "🇻🇳"], aliases: ["LOW", "CHEAP", "LOWPRICE"] }
  ],
  otherRegionGroup: { id: 6, name: "🗺️ 其他地区", auto: "⚡ 其他地区自动", aliases: ["OTHER", "OTHERS", "MISC"] },

  // 3. 分流规则集清单（非 REJECT 且非纯 IP 规则集的 DNS 解析出口会自动与 group 保持同步）
  // - noResolve: 仅纯 IP 规则集设为 true，匹配时跳过域名解析
  rulesets: [
    // 自定义高优先级规则集
    { id: "CustomIP",         group: "🚩 CustomIP", url: "https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/Rules/Policies/CustomIP.list" },
    { id: "Direct",           group: "DIRECT",      url: "https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/Rules/Policies/Direct.list" },
    { id: "Proxy",            group: "✈️ Overseas", url: "https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/Rules/Policies/Proxy.list" },

    // 局域网与防误杀
    { id: "LocalAreaNetwork", group: "DIRECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/LocalAreaNetwork.list" },
    { id: "UnBan",            group: "DIRECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/UnBan.list" },

    // 广告与劫持拦截
    { id: "Reject",           group: "REJECT",      url: "https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/Rules/Policies/Reject.list" },
    { id: "Hijacking",        group: "REJECT",      url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Hijacking/Hijacking.list" },
    { id: "BanAD",            group: "REJECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list" },
    { id: "BanProgramAD",     group: "REJECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list" },

    // 业务分流规则集
    { id: "AI",               group: "🚩 CustomIP", url: "https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/Rules/RuleSets/AI.list" },
    { id: "YouTube",          group: "▶️ YouTube",  url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/YouTube/YouTube.list" },
    { id: "GoogleCNProxyIP",  group: "🚩 CustomIP", url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/GoogleCNProxyIP.list" },
    { id: "Google",           group: "🚩 CustomIP", url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Google/Google.list" },
    { id: "Microsoft",        group: "🔘 Option",   url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Microsoft/Microsoft.list" },
    { id: "Apple",            group: "🔘 Option",   url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Apple/Apple.list" },
    { id: "XiaoHongShu",      group: "🌎️ IPmodify", url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/refs/heads/master/rule/Clash/XiaoHongShu/XiaoHongShu.list" },
    { id: "HoYoverse",        group: "DIRECT",      url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/HoYoverse/HoYoverse.list" },
    { id: "Game",             group: "🎮 Game",     url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Game/Game.list" },
    { id: "Telegram",         group: "✈️ Overseas", url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Telegram/Telegram.list" },

    // 通用国内外与下载分流
    { id: "ChinaMedia",       group: "DIRECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaMedia.list" },
    { id: "ProxyMedia",       group: "✈️ Overseas", url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyMedia.list" },
    { id: "ProxyGFWlist",     group: "✈️ Overseas", url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyGFWlist.list" },
    { id: "ChinaDomain",      group: "DIRECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list" },
    { id: "Download",         group: "📥 Download", url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Download.list" },
    { id: "ChinaIp",          group: "DIRECT",      url: "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaIp.list", noResolve: true }
  ],

  // 4. 国家/地区识别表（同时用于节点打国旗与 region 国家缩写反查所属地区组）
  countries: [
    { flag: "🇭🇰", keywords: ["香港", "深港", "沪港", "京港", "港", "Hong Kong"], codes: ["HK"] },
    { flag: "🇹🇼", keywords: ["台湾", "台灣", "台北", "台中", "新北", "彰化", "Taiwan"], codes: ["TW"] },
    { flag: "🇯🇵", keywords: ["日本", "东京", "大阪", "京日", "苏日", "沪日", "上日", "深日", "广日", "川日", "Japan"], codes: ["JP"] },
    { flag: "🇸🇬", keywords: ["新加坡", "狮城", "Singapore"], codes: ["SG"] },
    { flag: "🇺🇸", keywords: ["美国", "美國", "凤凰城", "洛杉矶", "西雅图", "芝加哥", "纽约", "俄勒冈", "弗吉尼亚", "沪美", "United States"], codes: ["US"] },
    { flag: "🇰🇷", keywords: ["韩", "韓", "首尔", "春川", "Korea"], codes: ["KR", "KOR"] },
    { flag: "🇬🇧", keywords: ["英国", "英國", "伦敦", "United Kingdom", "Britain"], codes: ["UK", "GB"] },
    { flag: "🇩🇪", keywords: ["德国", "德國", "法兰克福", "Germany"], codes: ["DE", "GER"] },
    { flag: "🇫🇷", keywords: ["法国", "法國", "巴黎", "France"], codes: ["FR"] },
    { flag: "🇮🇹", keywords: ["意大利", "米兰", "罗马", "Italy"], codes: ["IT"] },
    { flag: "🇳🇱", keywords: ["荷兰", "荷蘭", "阿姆斯特丹", "Netherlands"], codes: ["NL"] },
    { flag: "🇨🇦", keywords: ["加拿大", "温哥华", "多伦多", "蒙特利尔", "Canada"], codes: ["CA"] },
    { flag: "🇦🇺", keywords: ["澳大利亚", "澳洲", "悉尼", "墨尔本", "Australia"], codes: ["AU"] },
    { flag: "🇲🇴", keywords: ["澳门", "澳門", "Macau", "Macao"], codes: ["MO"] },
    { flag: "🇹🇷", keywords: ["土耳其", "伊斯坦布尔", "Turkey", "Türkiye"], codes: ["TR"] },
    { flag: "🇦🇷", keywords: ["阿根廷", "布宜诺斯艾利斯", "Argentina"], codes: ["AR"] },
    { flag: "🇳🇬", keywords: ["尼日利亚", "尼日利亞", "拉各斯", "Nigeria"], codes: ["NG"] },
    { flag: "🇮🇳", keywords: ["印度", "孟买", "新德里", "India"], codes: ["IN"] },
    { flag: "🇧🇷", keywords: ["巴西", "圣保罗", "Brazil"], codes: ["BR"] },
    { flag: "🇵🇭", keywords: ["菲律宾", "菲律賓", "马尼拉", "Philippines"], codes: ["PH"] },
    { flag: "🇪🇬", keywords: ["埃及", "开罗", "Egypt"], codes: ["EG"] },
    { flag: "🇺🇦", keywords: ["乌克兰", "烏克蘭", "基辅", "Ukraine"], codes: ["UA"] },
    { flag: "🇵🇰", keywords: ["巴基斯坦", "Pakistan"], codes: ["PK"] },
    { flag: "🇮🇩", keywords: ["印尼", "印度尼西亚", "雅加达", "Indonesia"], codes: ["ID"] },
    { flag: "🇲🇾", keywords: ["马来西亚", "馬來西亞", "吉隆坡", "Malaysia"], codes: ["MY"] },
    { flag: "🇹🇭", keywords: ["泰国", "泰國", "曼谷", "Thailand"], codes: ["TH"] },
    { flag: "🇻🇳", keywords: ["越南", "胡志明", "河内", "Vietnam"], codes: ["VN"] }
  ],

  // 5. 通用非代理信息过滤（仅排除套餐、流量、公告、官网等非节点条目）
  excludePattern: /剩余|套餐|到期|流量|更新|网址|重置|官网|防失联|过期|群组|频道|订阅|客服|公告|维护|邀请/i
};


// ╔═══════════════════════════════════════════════════════════════════════╗
// ║  核心处理引擎                                                         ║
// ╚═══════════════════════════════════════════════════════════════════════╝
function main(config, profileName = "") {
  if (!config || !Array.isArray(config.proxies) || config.proxies.length === 0) {
    return config;
  }

  // -------------------------------------------------------------------------
  // 1. 基础连接参数与域名嗅探 (Sniffer)
  // -------------------------------------------------------------------------
  config["tcp-concurrent"] = true;    // 并发拨号多 IP 解析结果，取最先建连者
  config["unified-delay"] = true;     // 统一握手延迟算法，使不同协议节点延迟可比
  config["keep-alive-interval"] = 15; // TCP Keep-Alive 探测间隔（秒）
  config["keep-alive-idle"] = 300;    // 空闲 300 秒后启用保活探测

  config.profile = {
    ...(config.profile || {}),
    "store-selected": true,           // 持久化策略组手动选中状态
    "store-fake-ip": true             // 持久化 Fake-IP 映射缓存
  };

  // 仅对明文 HTTP 覆写目标地址；TLS/QUIC 仅提取 SNI 用于分流，避免改写目标 IP 引发证书或风控异常
  config.sniffer = {
    enable: true,
    "override-destination": false,
    sniff: {
      HTTP: { ports: [80, "8080-8090"], "override-destination": true },
      TLS:  { ports: [443, 8443], "override-destination": false },
      QUIC: { ports: [443, 8443], "override-destination": false }
    },
    "skip-domain": [
      "*.lan", "*.local", "*.arpa", "localhost", "localhost.localdomain",
      "router.asus.com", "routerlogin.net", "captive.apple.com",
      "+.push.apple.com", "+.icloud.com", "+.apple.com",
      "msftconnecttest.com", "www.msftconnecttest.com", "+.msftncsi.com",
      "connectivitycheck.gstatic.com", "connectivitycheck.android.com",
      "clients3.google.com", "clients4.google.com", "android.clients.google.com",
      "time.*", "ntp.*", "+.market.xiaomi.com", "localhost.ptlogin2.qq.com",
      "+._dns-sd._udp.*", "+._services._dns-sd._udp.*",
      "cloudflare-ech.com"            // 跳过 Cloudflare ECH 公共外层 SNI
    ]
  };

  // -------------------------------------------------------------------------
  // 2. 读取、校验并规范化多静态 IP 配置
  // -------------------------------------------------------------------------
  const staticGroupPrefix = "🏠 静态 · ";
  const probeGroupName = "🧪 测速前置";
  const probeProxyPrefix = "🧪 静态测速探针|";

  const rawMaxNodes = config[USER_CONFIG.maxStaticNodesKey];
  const rawCurrentAirport = config[USER_CONFIG.currentAirportKey];
  const hasMergeList = Object.prototype.hasOwnProperty.call(config, USER_CONFIG.staticProxiesKey);
  const hasLegacySingle = Object.prototype.hasOwnProperty.call(config, USER_CONFIG.legacyStaticProxyKey);

  // 读取优先级：Merge 列表 > Merge 旧版单对象 > 脚本内置 STATIC_CONFIG
  let rawStaticList = [];
  if (hasMergeList && Array.isArray(config[USER_CONFIG.staticProxiesKey])) {
    rawStaticList = config[USER_CONFIG.staticProxiesKey];
  } else if (hasLegacySingle && config[USER_CONFIG.legacyStaticProxyKey]) {
    const legacy = config[USER_CONFIG.legacyStaticProxyKey];
    rawStaticList = Array.isArray(legacy) ? legacy : [legacy];
  } else if (Array.isArray(STATIC_CONFIG.staticProxies)) {
    rawStaticList = STATIC_CONFIG.staticProxies;
  }

  delete config[USER_CONFIG.staticProxiesKey];
  delete config[USER_CONFIG.legacyStaticProxyKey];
  delete config[USER_CONFIG.maxStaticNodesKey];
  delete config[USER_CONFIG.currentAirportKey];

  const parsedMaxNodes = Number(rawMaxNodes !== undefined ? rawMaxNodes : STATIC_CONFIG.maxStaticNodes);
  const maxStaticNodes = Number.isInteger(parsedMaxNodes) && parsedMaxNodes > 0 ? parsedMaxNodes : 15;
  const airportHint = String(
    rawCurrentAirport !== undefined && String(rawCurrentAirport).trim() !== ""
      ? rawCurrentAirport
      : (STATIC_CONFIG.currentAirport || profileName || "")
  ).trim();

  const isValidStaticNode = (node) => {
    if (!node || typeof node !== "object" || Array.isArray(node)) return false;
    const type = String(node.type ?? "").trim();
    const server = String(node.server ?? "").trim();
    const port = Number(node.port);
    const placeholders = ["", "1.2.3.4", "example.com", "服务器IP或域名"];
    return (
      type !== "" &&
      !placeholders.includes(server) &&
      !server.startsWith("YOUR_") &&
      Number.isInteger(port) &&
      port >= 1 &&
      port <= 65535
    );
  };

  // 32 位 FNV-1a 摘要：仅在多个静态 IP 共用同一网关 (host:port) 时用于区分 username，不暴露明文凭证
  const fnv1aHex = (str) => {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h + (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24)) >>> 0;
    }
    return ("00000000" + h.toString(16)).slice(-8);
  };

  const formatHostPort = (node) => {
    const server = String(node.server ?? "").trim();
    const port = Number(node.port);
    const host = server.includes(":") && !server.startsWith("[") ? `[${server}]` : server;
    return `${host}:${port}`;
  };

  const validStaticRaw = rawStaticList.filter(isValidStaticNode);

  // 统计各 host:port 出现次数：独立 IP 直接沿用 host:port 作为数据库键（兼容旧库且改名不丢历史）
  const hostPortCounts = new Map();
  validStaticRaw.forEach(node => {
    const hp = formatHostPort(node);
    hostPortCounts.set(hp, (hostPortCounts.get(hp) || 0) + 1);
  });

  // 为空名补默认值、为重名自动追加序号，防止生成重复代理名导致 Mihomo 校验失败
  const usedDisplayNames = new Set();
  const usedStorageKeys = new Set();
  const staticEntries = validStaticRaw.map((node, idx) => {
    const baseName = String(node.name ?? "").replace(/\|/g, "-").trim() || `静态${idx + 1}`;
    let displayName = baseName;
    let suffix = 2;
    while (usedDisplayNames.has(displayName)) {
      displayName = `${baseName} ${suffix}`;
      suffix += 1;
    }
    usedDisplayNames.add(displayName);

    const hp = formatHostPort(node);
    let storageKey = hp;
    if ((hostPortCounts.get(hp) || 0) > 1) {
      const discriminator = String(node.username ?? "").trim() || displayName;
      storageKey = `${hp}@${fnv1aHex(discriminator)}`;
    }
    let keyIdx = 2;
    const baseStorageKey = storageKey;
    while (usedStorageKeys.has(storageKey)) {
      storageKey = `${baseStorageKey}-${keyIdx}`;
      keyIdx += 1;
    }
    usedStorageKeys.add(storageKey);

    return {
      raw: node,
      displayName,
      storageKey,
      groupName: `${staticGroupPrefix}${displayName}`,
      // 探针名编码「显示名|存储键」，供 bench_static_chain.py 同时获取可读名称与稳定数据库主键
      probeProxyName: `${probeProxyPrefix}${displayName}|${storageKey}`
    };
  });

  // -------------------------------------------------------------------------
  // 3. 节点地区识别、国旗标注与 region 缩写映射
  // -------------------------------------------------------------------------
  const escapeRegex = str => str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  // 国家代码词边界校验：允许 US01 等后接数字的写法，但排除 "100GB" 等前接数字的流量单位误匹配
  const hasCountryCode = (name, code) => {
    const escaped = escapeRegex(code);
    if (new RegExp(`\\d+\\s*${escaped}(?=$|[^A-Za-z])`, "i").test(name)) return false;
    return new RegExp(`(?:^|[^A-Za-z0-9])${escaped}(?=$|[^A-Za-z])`, "i").test(name);
  };

  const compiledCountries = USER_CONFIG.countries.map(item => ({
    flag: item.flag,
    keywordRegex: item.keywords.length > 0
      ? new RegExp(item.keywords.map(escapeRegex).join("|"), "i")
      : null,
    codes: item.codes || []
  }));

  config.proxies.forEach(proxy => {
    if (!proxy || typeof proxy.name !== "string") return;
    const name = proxy.name;
    for (const entry of compiledCountries) {
      const matchedKeyword = entry.keywordRegex && entry.keywordRegex.test(name);
      const matchedCode = !matchedKeyword && entry.codes.some(code => hasCountryCode(name, code));
      if (matchedKeyword || matchedCode) {
        if (!name.includes(entry.flag)) {
          proxy.name = `${entry.flag} ${name}`;
        }
        break;
      }
    }
  });

  const baseProxyNames = [...new Set(config.proxies.map(p => p && p.name).filter(Boolean))];
  const validNormalNames = baseProxyNames.filter(n => !USER_CONFIG.excludePattern.test(n));

  const allDefinedFlags = new Set(USER_CONFIG.regionGroups.flatMap(g => g.flags));
  const resolvedRegionGroups = USER_CONFIG.regionGroups.map(group => ({
    id: group.id,
    name: group.name,
    auto: group.auto,
    flags: group.flags,
    aliases: group.aliases || [],
    nodes: validNormalNames.filter(n => group.flags.some(flag => n.includes(flag)))
  }));

  const otherNodes = validNormalNames.filter(
    n => ![...allDefinedFlags].some(flag => n.includes(flag))
  );
  resolvedRegionGroups.push({
    id: USER_CONFIG.otherRegionGroup.id,
    name: USER_CONFIG.otherRegionGroup.name,
    auto: USER_CONFIG.otherRegionGroup.auto,
    flags: [],
    aliases: USER_CONFIG.otherRegionGroup.aliases || [],
    nodes: otherNodes
  });

  // 仅保留非空地区组，避免面板出现空组
  const activeRegionGroups = resolvedRegionGroups.filter(g => g.nodes.length > 0);
  const activeRegionById = new Map(activeRegionGroups.map(g => [g.id, g]));
  const allRegionGroupNames = activeRegionGroups.map(g => g.name);

  // 构建 region 统一映射表：支持地区缩写 (EU/HKTW)、国家 ISO 代码 (JP/CA -> 自动归入所属地区组) 及旧版数字编号
  const regionTokenToId = new Map();
  const flagToRegionId = new Map();
  resolvedRegionGroups.forEach(g => {
    regionTokenToId.set(String(g.id), g.id);
    (g.aliases || []).forEach(alias => regionTokenToId.set(String(alias).toUpperCase(), g.id));
    (g.flags || []).forEach(flag => flagToRegionId.set(flag, g.id));
  });
  USER_CONFIG.countries.forEach(c => {
    const targetId = flagToRegionId.get(c.flag) || USER_CONFIG.otherRegionGroup.id;
    (c.codes || []).forEach(code => {
      const up = String(code).toUpperCase();
      if (!regionTokenToId.has(up)) {
        regionTokenToId.set(up, targetId);
      }
    });
  });

  const resolveActiveRegionGroups = (regionValue) => {
    if (regionValue === undefined || regionValue === null || regionValue === "") return [];
    const rawTokens = Array.isArray(regionValue)
      ? regionValue
      : String(regionValue).split(/[,，\s/|]+/);
    const seenIds = new Set();
    const matched = [];
    rawTokens.forEach(raw => {
      const token = String(raw ?? "").trim().toUpperCase();
      if (!token) return;
      const id = regionTokenToId.get(token);
      if (!id || seenIds.has(id)) return;
      const group = activeRegionById.get(id);
      if (group) {
        seenIds.add(id);
        matched.push(group);
      }
    });
    return matched;
  };

  // -------------------------------------------------------------------------
  // 4. 生成多静态 IP 链式代理节点 (dialer-proxy) 与隐藏探针
  // -------------------------------------------------------------------------
  const existingProxyNames = new Set(baseProxyNames);
  const validSet = new Set(validNormalNames);

  // 单机场回退匹配工具：从聚合订阅切回单机场订阅、精确匹配全未命中时，
  // 校验节点前缀与当前订阅/指定机场名一致后剥离前缀，再按「国旗::核心名」匹配存活节点
  const flagRegex = /(?:\uD83C[\uDDE6-\uDDFF]){2}/;
  const flagGlobalRegex = /(?:\uD83C[\uDDE6-\uDDFF]){2}/g;
  const leadingFlagsRegex = /^(?:(?:\uD83C[\uDDE6-\uDDFF]){2}|\s)+/;

  const buildCoreKey = (flagSource, bodySource) => {
    const flag = (flagSource.match(flagRegex) || [""])[0];
    const body = bodySource
      .replace(flagGlobalRegex, "")
      .replace(/\s*·\s*/g, "·")
      .replace(/\s+/g, " ")
      .trim();
    return `${flag}::${body}`;
  };

  const isAirportMatch = (prefix, prof) => {
    const a = prefix.trim().toLowerCase();
    const b = prof.trim().toLowerCase();
    if (!a || !b) return false;
    if (a === b) return true;
    return a.length >= 2 && b.length >= 2 && (b.includes(a) || a.includes(b));
  };

  const extractPrefixAndRest = (name, prof) => {
    const trimmed = name.trim();
    const stripped = trimmed.replace(leadingFlagsRegex, "").trim();

    // 依次识别括号前缀、国旗前前缀、显式分隔符前缀、空格/短横线前缀与无分隔符拼接
    let m = trimmed.match(/^[\[\【「(]\s*([^\]\】」)]{1,24}?)\s*[\]\】」)][\s|｜:：/·\-_]*/);
    if (m) return { prefix: m[1].trim(), rest: trimmed.slice(m[0].length) };

    m = stripped.match(/^[\[\【「(]\s*([^\]\】」)]{1,24}?)\s*[\]\】」)][\s|｜:：/·\-_]*/);
    if (m) return { prefix: m[1].trim(), rest: stripped.slice(m[0].length) };

    const fm = trimmed.match(flagRegex);
    if (fm && fm.index > 0) {
      const before = trimmed.slice(0, fm.index).replace(/^[\[\【「(\s]+|[\]\】」)\s|｜\-_:：/·]+$/g, "").trim();
      if (before) return { prefix: before, rest: trimmed.slice(fm.index) };
    }

    m = stripped.match(/^([^|｜:：/]{1,20}?)\s*[|｜:：/]\s*/);
    if (m) return { prefix: m[1].trim(), rest: stripped.slice(m[0].length) };

    m = stripped.match(/^([^\s\-_]{1,20})(?:\s+|\s*[-_]\s*)/);
    if (m) return { prefix: m[1].trim(), rest: stripped.slice(m[0].length) };

    if (prof && stripped.toLowerCase().startsWith(prof.toLowerCase())) {
      return { prefix: prof, rest: stripped.slice(prof.length).replace(/^[\s|｜:：/·\-_]+/, "") };
    }
    return null;
  };

  const liveKeyMap = new Map();
  validNormalNames.forEach(nodeName => {
    const key = buildCoreKey(nodeName, nodeName);
    if (!liveKeyMap.has(key)) liveKeyMap.set(key, nodeName);
  });

  const matchPinnedNodes = (rawNodes) => {
    const pinnedNames = Array.isArray(rawNodes)
      ? [...new Set(rawNodes.map(v => String(v ?? "").trim()).filter(Boolean))]
      : [];
    if (pinnedNames.length === 0) return [];

    const exactMatched = pinnedNames.filter(n => validSet.has(n));
    if (exactMatched.length > 0 || !airportHint) {
      return exactMatched;
    }

    const fallbackMatched = [];
    const seen = new Set();
    pinnedNames.forEach(pinned => {
      const parsed = extractPrefixAndRest(pinned, airportHint);
      if (!parsed || !isAirportMatch(parsed.prefix, airportHint)) return;
      const matchedNode = liveKeyMap.get(buildCoreKey(pinned, parsed.rest));
      if (matchedNode && !seen.has(matchedNode)) {
        seen.add(matchedNode);
        fallbackMatched.push(matchedNode);
      }
    });
    return fallbackMatched;
  };

  const pushUniqueProxy = (proxyObj) => {
    if (existingProxyNames.has(proxyObj.name)) return false;
    existingProxyNames.add(proxyObj.name);
    config.proxies.push(proxyObj);
    return true;
  };

  const staticProxyGroups = [];
  let hasProbeProxy = false;

  if (validNormalNames.length > 0) {
    staticEntries.forEach(entry => {
      // 完整继承协议连接参数，剔除辅助元数据与可能误填的 name / dialer-proxy
      const {
        name: _ignoreName,
        "dialer-proxy": _ignoreDialer,
        region: _ignoreRegion,
        regions: _ignoreRegions,
        nodes: _ignoreNodes,
        ...staticTemplate
      } = entry.raw;
      if (staticTemplate.username === "") delete staticTemplate.username;
      if (staticTemplate.password === "") delete staticTemplate.password;

      // 1) 生成该静态 IP 的独立隐藏测速探针（与其它探针共用 🧪 测速前置 组）
      if (pushUniqueProxy({
        ...staticTemplate,
        name: entry.probeProxyName,
        "dialer-proxy": probeGroupName
      })) {
        hasProbeProxy = true;
      }

      const groupChainNames = [];
      const chainPrefix = `🔗 ${entry.displayName} · `;

      // 2) 匹配完整 nodes 池后截取前 maxStaticNodes 个，直连具体机场节点（避免多静态 IP 争抢地区组）
      const matchedNodes = matchPinnedNodes(entry.raw.nodes).slice(0, maxStaticNodes);
      matchedNodes.forEach(nodeName => {
        const chainName = `${chainPrefix}${nodeName}`;
        if (pushUniqueProxy({
          ...staticTemplate,
          name: chainName,
          "dialer-proxy": nodeName
        })) {
          groupChainNames.push(chainName);
        }
      });

      // 3) 底部附带 region 指定的地区组前置链（作为未测速过渡与全挂兜底）
      const fallbackRegions = resolveActiveRegionGroups(entry.raw.region ?? entry.raw.regions);
      fallbackRegions.forEach(rg => {
        const chainName = `${chainPrefix}${rg.name}`;
        if (pushUniqueProxy({
          ...staticTemplate,
          name: chainName,
          "dialer-proxy": rg.name
        })) {
          groupChainNames.push(chainName);
        }
      });

      // 4) 极端防呆：仅当 nodes 与 region 均未命中任何节点时，临时补 1 条 📶 Auto 防止空组报错
      if (groupChainNames.length === 0) {
        const autoFallbackName = `${chainPrefix}📶 Auto`;
        if (pushUniqueProxy({
          ...staticTemplate,
          name: autoFallbackName,
          "dialer-proxy": "📶 Auto"
        })) {
          groupChainNames.push(autoFallbackName);
        }
      }

      if (groupChainNames.length > 0) {
        staticProxyGroups.push({
          name: entry.groupName,
          type: "select",
          proxies: groupChainNames
        });
      }
    });
  }

  const staticGroupNames = staticProxyGroups.map(g => g.name);

  // -------------------------------------------------------------------------
  // 5. 构建策略组 (proxy-groups)
  // -------------------------------------------------------------------------
  // 隐藏地区自动组采用 lazy: false（纯机场测速不触及静态 IP），保证地区组随时处于热态
  const createHiddenRegionUrlTest = (name, nodeList, interval = 300, timeout = 5000) => ({
    name,
    type: "url-test",
    url: "https://www.gstatic.com/generate_204",
    interval,
    timeout,
    tolerance: 50,
    lazy: false,
    "expected-status": "204",
    hidden: true,
    proxies: nodeList.length > 0 ? nodeList : ["DIRECT"]
  });

  config["proxy-groups"] = [
    // 高风控 / AI / Google 专用出口（静态 IP 置顶）
    {
      name: "🚩 CustomIP",
      type: "select",
      proxies: [...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },

    // 各静态 IP 独立手动策略组（纯 select，无后台自动探活）
    ...staticProxyGroups,

    // 各非空地区手动选择组（首项挂载对应隐藏自动测速组）
    ...activeRegionGroups.map(g => ({
      name: g.name,
      type: "select",
      proxies: [g.auto, ...g.nodes, "DIRECT"]
    })),

    // 常规海外流量出口
    {
      name: "✈️ Overseas",
      type: "select",
      proxies: ["🚩 CustomIP", ...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },

    // 独立专项策略组
    {
      name: "▶️ YouTube",
      type: "select",
      proxies: ["🚩 CustomIP", "✈️ Overseas", ...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "🌎️ IPmodify",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🚩 CustomIP", ...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "🔘 Option",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🚩 CustomIP", ...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "🎮 Game",
      type: "select",
      proxies: ["✈️ Overseas", "DIRECT", "🚩 CustomIP", ...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "📥 Download",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", ...allRegionGroupNames, "📶 Auto"]
    },

    // 兜底策略组
    {
      name: "♾️ Final",
      type: "select",
      proxies: ["✈️ Overseas", "DIRECT", "🚩 CustomIP", ...staticGroupNames, ...allRegionGroupNames, "📶 Auto"]
    },

    // 全局有效节点自动测速
    {
      name: "📶 Auto",
      type: "url-test",
      url: "https://www.gstatic.com/generate_204",
      interval: 300,
      timeout: 5000,
      tolerance: 50,
      lazy: false,
      "expected-status": "204",
      proxies: validNormalNames.length > 0 ? validNormalNames : ["DIRECT"]
    },

    // 后台隐藏地区自动测速组
    ...activeRegionGroups.map(g => createHiddenRegionUrlTest(g.auto, g.nodes)),

    // 隐藏测速前置选择器（仅外部 Python 脚本通过 REST API 调度，面板不可见）
    ...(hasProbeProxy && validNormalNames.length > 0 ? [{
      name: probeGroupName,
      type: "select",
      hidden: true,
      proxies: validNormalNames
    }] : [])
  ];

  // -------------------------------------------------------------------------
  // 6. 构建规则集 (rule-providers) 与分流规则 (rules)
  // -------------------------------------------------------------------------
  const ruleProviders = {};
  const rulesetRulesById = new Map();

  USER_CONFIG.rulesets.forEach(item => {
    const providerName = `script_${item.id}`;
    ruleProviders[providerName] = {
      type: "http",
      behavior: "classical",
      format: "text",
      path: `./rules/${providerName}.list`,
      url: item.url,
      interval: 86400,
      "size-limit": 33554432,
      proxy: "📶 Auto"
    };
    rulesetRulesById.set(
      item.id,
      item.noResolve
        ? `RULE-SET,${providerName},${item.group},no-resolve`
        : `RULE-SET,${providerName},${item.group}`
    );
  });

  config["rule-providers"] = ruleProviders;
  const pickRulesets = ids => ids.map(id => rulesetRulesById.get(id)).filter(Boolean);

  // 规则顺序：局域网/NTP -> 探测屏蔽 -> 个人与广告规则 -> 国内与 Apple 豁免 -> 海外 QUIC 阻断 -> 海外业务 -> 兜底
  config.rules = [
    "GEOIP,LAN,DIRECT,no-resolve",
    "AND,((NETWORK,UDP),(DST-PORT,123)),DIRECT",
    ...pickRulesets(["LocalAreaNetwork"]),

    // 屏蔽单栈 IP 探测与前端遥测端点，ping0.cc 主站走 CustomIP 检测出口质量
    "AND,((NETWORK,UDP),(DST-PORT,443),(DOMAIN-SUFFIX,ping0.cc)),REJECT",
    "DOMAIN,ipv4.ping0.cc,REJECT",
    "DOMAIN,ipv4.icanhazip.com,REJECT",
    "DOMAIN,ipv4.ip.sb,REJECT",
    "DOMAIN,browser-intake-datadoghq.com,REJECT",
    "DOMAIN,openai.qualtrics.com,REJECT",
    "DOMAIN-SUFFIX,ping0.cc,🚩 CustomIP",

    ...pickRulesets(["CustomIP", "Direct", "Proxy", "UnBan", "Reject", "Hijacking", "BanAD", "BanProgramAD"]),

    // 国内直连与 Apple 置于 QUIC 阻断前，保障国内 HTTP/3 与 Apple 推送正常
    ...pickRulesets(["HoYoverse", "ChinaMedia", "ChinaDomain", "Apple"]),
    "DOMAIN-SUFFIX,cn,DIRECT",
    "GEOIP,CN,DIRECT",

    // 阻断剩余海外 UDP 443 (QUIC)，促使浏览器回退 TCP 以提升代理链路稳定性
    "AND,((NETWORK,UDP),(DST-PORT,443)),REJECT",

    ...pickRulesets([
      "AI", "YouTube", "GoogleCNProxyIP", "Google",
      "Microsoft", "XiaoHongShu", "Game", "Telegram",
      "ProxyMedia", "ProxyGFWlist", "Download", "ChinaIp"
    ]),
    "MATCH,♾️ Final"
  ];

  // -------------------------------------------------------------------------
  // 7. 分域加密 DNS 与 Fake-IP 配置
  // -------------------------------------------------------------------------
  const cnEncryptedDns = [
    "https://dns.alidns.com/dns-query",
    "https://doh.pub/dns-query"
  ];

  // 通过 #策略组名 指定海外 DoH 出口，确保业务组切至任一静态 IP 时 DNS 解析出口同步跟随
  const foreignDohViaGroup = groupName => [
    `https://1.1.1.1/dns-query#${groupName}`,
    `https://1.0.0.1/dns-query#${groupName}`,
    `https://8.8.8.8/dns-query#${groupName}`
  ];

  const nameserverPolicy = {
    "+.ping0.cc": foreignDohViaGroup("🚩 CustomIP")
  };

  USER_CONFIG.rulesets.forEach(item => {
    if (item.group === "REJECT" || item.noResolve) return;
    const policyKey = `rule-set:script_${item.id}`;
    nameserverPolicy[policyKey] = item.group === "DIRECT"
      ? cnEncryptedDns
      : foreignDohViaGroup(item.group);
  });

  // Fake-IP 过滤白名单（系统连通性探测、国内网银与运营商认证域名需返回真实 IP）
  const fakeIpFilter = [
    "*.lan", "*.local", "*.arpa", "localhost", "localhost.localdomain",
    "router.asus.com", "routerlogin.net", "captive.apple.com", "+.push.apple.com",
    "+.icloud.com", "+.apple.com", "msftconnecttest.com", "www.msftconnecttest.com",
    "+.msftncsi.com", "dns.msftncsi.com", "connectivitycheck.gstatic.com",
    "connectivitycheck.android.com", "clients1.google.com", "clients3.google.com",
    "clients4.google.com", "android.clients.google.com", "play.googleapis.com",
    "time.*", "ntp.*", "+.market.xiaomi.com", "localhost.ptlogin2.qq.com",
    "+._dns-sd._udp.*", "+._services._dns-sd._udp.*", "+.cn",
    "connectivitycheck.platform.hicloud.com", "+.wifi.huawei.com",
    "connectivitycheck.samsung.com", "connect.rom.miui.com",
    "connectivitycheck.platform.xiaomi.com", "conn1.coloros.com", "conn2.coloros.com",
    "connectivitycheck.platform.hihonorcloud.com", "connectivitycheck.meizu.com",
    "wifi.vivo.com.cn", "noisyfox.cn",
    "+.cmpassport.com", "+.10010.com", "open.e.189.cn", "opencloud.wostore.cn",
    "id.mail.wo.cn", "mdn.open.wo.cn", "hmrz.wo.cn", "enrichgw.10010.com",
    "+.cmbchina.com", "+.ccb.com", "+.bankcomm.com", "+.bocomcc.com",
    "+.pingan.com.cn", "+.alipay.com", "+.alipayobjects.com", "id6.me"
  ];

  config.dns = {
    enable: true,
    "cache-algorithm": "arc",
    "enhanced-mode": "fake-ip",
    "fake-ip-range": "198.18.0.1/16",
    "fake-ip-filter-mode": "blacklist",
    "prefer-h3": false,                        // 配合 respect-rules 时关闭 DoH HTTP/3 规避潜在兼容问题
    "respect-rules": true,                     // DNS 请求遵循分流规则（需搭配 proxy-server-nameserver）
    "use-hosts": true,
    "use-system-hosts": true,
    "fake-ip-filter": fakeIpFilter,
    "default-nameserver": [
      "tls://223.5.5.5",
      "tls://1.12.12.12"
    ],
    nameserver: cnEncryptedDns,
    "direct-nameserver": cnEncryptedDns,
    "proxy-server-nameserver": cnEncryptedDns, // 代理节点域名走国内加密 DNS，防止解析循环依赖
    "nameserver-policy": nameserverPolicy
  };

  return config;
}
