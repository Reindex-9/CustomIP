// =========================================================================
// Mihomo / Clash Verge 全局预处理脚本 v3.2
// 最新更新：2026-11-24
// =========================================================================
// 功能概览：
// 1. 策略与规则联动：统一由 rulesets 驱动路由分流与加密 DNS 出口，确保策略一致
// 2. 双模式链式代理：支持精选池 nodes 优先、region 地区编号兜底、手动多地区前置组与隐藏单探针
// 3. 节点清洗与分类：按关键字与国家代码词边界自动标注国旗，过滤非代理信息节点与空地区组
// =========================================================================
// ╔═══════════════════════════════════════════════════════════════════════╗
// ║  配置区 (USER_CONFIG)                                                 ║
// ╚═══════════════════════════════════════════════════════════════════════╝
const USER_CONFIG = {

  // 1. 基础开关与静态代理配置
  staticProxyKey: "static-proxy",    // 外部覆写（如 Clash Verge Merge）约定的静态代理字段名，优先读取
  staticProxy: {                     // 内置静态代理配置（未检测到外部覆写时生效，适用于 FlClash 等单脚本客户端）
    type: "socks5",                  // 协议类型（支持 socks5 / http / vless / trojan / ss / hysteria2 等）
    server: "",                      // 服务器 IP 或域名（留空则自动跳过链式代理生成）
    port: 109,                       // 端口号（1 - 65535）
    username: "",                    // 鉴权用户名（无鉴权可留空）
    password: "",                    // 鉴权密码（无鉴权可留空）
    udp: true,                       // 是否启用 UDP 转发
    region: "1",                     // (自定义配置)备用：nodes 留空时按地区编号生成「⛓️ 静态链路自动」（如 "1,3"），未命中则跳过
    nodes: []                        // (自定义配置)精选池：由外部低并发测速脚本产出的节点名列表，优先级高于 region
  },
  enableAutoChain: true,             // 是否启用「⛓️ 静态链路自动」

  // 2. 地区策略组定义（id 为固定编号，供 static-proxy.region 指定；按国旗聚合，自动生成隐藏 url-test 组）
  regionGroups: [
    { id: 1, name: "🇺🇸 美国",   auto: "⚡ 美国自动",   flags: ["🇺🇸"] },
    { id: 2, name: "🇨🇳 港澳台", auto: "⚡ 港澳台自动", flags: ["🇭🇰", "🇹🇼", "🇲🇴"] },
    { id: 3, name: "🌏 日韩新", auto: "⚡ 日韩新自动", flags: ["🇯🇵", "🇰🇷", "🇸🇬"] },
    { id: 4, name: "🇪🇺 欧洲",   auto: "⚡ 欧洲自动",   flags: ["🇩🇪", "🇬🇧", "🇫🇷", "🇮🇹", "🇳🇱"] },
    { id: 5, name: "🛒 低价区", auto: "⚡ 低价区自动", flags: ["🇹🇷", "🇦🇷", "🇳🇬", "🇮🇳", "🇧🇷", "🇵🇭", "🇪🇬", "🇺🇦", "🇵🇰", "🇮🇩", "🇲🇾", "🇹🇭", "🇻🇳"] }
  ],
  otherRegionGroup: { id: 6, name: "🗺️ 其他地区", auto: "⚡ 其他地区自动" }, // 未命中上述国旗的兜底地区组

  // 3. 分流规则集清单（脚本自动将非 REJECT / 非纯 IP 规则集的 DNS 出口与 group 保持同步）
  // - id       : 唯一标识，用于生成 provider 名称及本地缓存路径
  // - group    : 目标策略组（同时作为该规则集内域名的 DNS 解析出口）
  // - noResolve: 仅针对纯 IP 类规则集设为 true，匹配时跳过域名解析
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

  // 4. 国家/地区识别表（keywords 为名称关键字，codes 为带前后词边界校验的国家代码）
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

  // 5. 过滤非通用节点的关键字正则（套餐信息、官网公告、音乐/游戏专用线路等）
  excludePattern: /剩余|套餐|到期|流量|更新|网址|重置|官网|防失联|过期|群组|频道|订阅|客服|公告|静态\s*IP|music|𝐌𝐮𝐬𝐢𝐜|Unbolck|Unblock|网易云|音乐|Music|Netease|🎶|手游|游戏|game|yue\.to|@yue/i
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
  config["tcp-concurrent"] = true;    // 并发拨号多 IP 解析结果，取最先建立的连接
  config["unified-delay"] = true;     // 统一握手延迟计算标准，使不同协议节点测速可比
  config["keep-alive-interval"] = 15; // TCP Keep-Alive 探测包发送间隔（秒）
  config["keep-alive-idle"] = 300;    // 空闲 300 秒后启动保活探测

  config.profile = {
    ...(config.profile || {}),
    "store-selected": true,           // 持久化策略组手动选择状态
    "store-fake-ip": true             // 持久化 Fake-IP 地址映射缓存
  };

  // 仅对明文 HTTP 覆写目标地址；TLS/QUIC 仅提取 SNI 用于分流，不改写目标 IP
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
  // 2. 提取并校验 Merge 注入的静态代理配置块
  // -------------------------------------------------------------------------
  const staticManualGroupName = "🏠 静态IP(手动前置)";
  const staticAutoGroupName = "⛓️ 静态链路自动";
  const manualChainPrefix = "🔗 静态 · ";
  const autoChainPrefix = "🔗 静态链路 · ";
  const probeGroupName = "🧪 测速前置";
  const probeProxyPrefix = "🧪 静态测速探针|";

  // 读取 static-proxy 配置块，并从最终配置中清理该临时字段（优先读取 Merge、兜底读取 USER_CONFIG）
  const rawStaticProxy = config[USER_CONFIG.staticProxyKey] || USER_CONFIG.staticProxy;
  delete config[USER_CONFIG.staticProxyKey];

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

  // 解析地区编号（支持单数字、逗号分隔字符串、数组，兼容中文逗号）
  const parseRegionIds = (value) => {
    if (value === undefined || value === null || value === "") return [];
    const rawList = Array.isArray(value)
      ? value
      : String(value).split(/[,，\s]+/);
    return [...new Set(
      rawList
        .map(item => Number(String(item).trim()))
        .filter(num => Number.isInteger(num) && num > 0)
    )];
  };

  // 拼接静态 IP 唯一标识（IP:端口），用于隐藏测速探针向外部脚本暴露当前静态 IP
  const formatStaticTargetId = (node) => {
    const server = String(node.server ?? "").trim();
    const port = Number(node.port);
    const host = server.includes(":") && !server.startsWith("[") ? `[${server}]` : server;
    return `${host}:${port}`;
  };

  const hasStaticIP = isValidStaticNode(rawStaticProxy);
  const probeProxyName = hasStaticIP
    ? `${probeProxyPrefix}${formatStaticTargetId(rawStaticProxy)}`
    : "";

  // -------------------------------------------------------------------------
  // 3. 节点地区识别与国旗标注
  // -------------------------------------------------------------------------
  const escapeRegex = str => str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  // 校验国家代码词边界：左侧不允许紧邻字母或数字，右侧不允许紧邻字母（兼容 US01 等编号），同时排除 "100GB" 等容量单位
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

  // 按地区分组表聚合有效节点，并过滤无节点的空地区组
  const baseProxyNames = [...new Set(config.proxies.map(p => p && p.name).filter(Boolean))];
  const validNormalNames = baseProxyNames.filter(n => !USER_CONFIG.excludePattern.test(n));

  const allDefinedFlags = new Set(USER_CONFIG.regionGroups.flatMap(g => g.flags));
  const resolvedRegionGroups = USER_CONFIG.regionGroups.map(group => ({
    id: group.id,
    name: group.name,
    auto: group.auto,
    nodes: validNormalNames.filter(n => group.flags.some(flag => n.includes(flag)))
  }));

  const otherNodes = validNormalNames.filter(
    n => ![...allDefinedFlags].some(flag => n.includes(flag))
  );
  resolvedRegionGroups.push({
    id: USER_CONFIG.otherRegionGroup.id,
    name: USER_CONFIG.otherRegionGroup.name,
    auto: USER_CONFIG.otherRegionGroup.auto,
    nodes: otherNodes
  });

  const activeRegionGroups = resolvedRegionGroups.filter(g => g.nodes.length > 0);
  const allRegionGroupNames = activeRegionGroups.map(g => g.name);

  // -------------------------------------------------------------------------
  // 4. 生成链式代理节点 (dialer-proxy)
  // -------------------------------------------------------------------------
  const manualChainNodeNames = [];
  const autoChainNodeNames = [];

  if (hasStaticIP) {
    // 继承静态配置块的所有协议参数，剔除辅助字段及可能误填的 name / dialer-proxy
    const {
      name: _ignoreName,
      "dialer-proxy": _ignoreDialer,
      region: _ignoreRegion,
      regions: _ignoreRegions,
      nodes: _ignoreNodes,
      ...staticTemplate
    } = rawStaticProxy;
    if (staticTemplate.username === "") delete staticTemplate.username;
    if (staticTemplate.password === "") delete staticTemplate.password;

    // 隐藏测速单探针：供外部低并发脚本切换前置并实测端到端延迟，不干扰日常流量
    if (validNormalNames.length > 0) {
      config.proxies.push({
        ...staticTemplate,
        name: probeProxyName,
        "dialer-proxy": probeGroupName
      });
    }

    // 手动前置链式入口：为 📶 Auto 与各非空地区组建立链式代理，供「🏠 静态IP(手动前置)」组内横向测速与切换
    const manualChainTargets = [
      ...(validNormalNames.length > 0 ? ["📶 Auto"] : []),
      ...allRegionGroupNames
    ];
    manualChainTargets.forEach(targetGroupName => {
      const manualChainNodeName = `${manualChainPrefix}${targetGroupName}`;
      manualChainNodeNames.push(manualChainNodeName);
      config.proxies.push({
        ...staticTemplate,
        name: manualChainNodeName,
        "dialer-proxy": targetGroupName
      });
    });

    // 自动链式优选源：优先使用 static-proxy.nodes 精选池；留空或全部未命中时回退至 region 地区编号
    if (USER_CONFIG.enableAutoChain) {
      const pinnedNames = Array.isArray(rawStaticProxy.nodes)
        ? [...new Set(rawStaticProxy.nodes.map(v => String(v ?? "").trim()).filter(Boolean))]
        : [];
      const validSet = new Set(validNormalNames);
            let matchedPinned = pinnedNames.filter(n => validSet.has(n));

            // 精确匹配全未命中时（如从聚合订阅切回单机场订阅），按当前订阅名校验归属并去前缀复用精选节点
            const cleanProfileName = String(profileName || "").trim();
            if (matchedPinned.length === 0 && pinnedNames.length > 0 && cleanProfileName) {
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

                // 1. 括号前缀（兼容 "[悦通] 🇭🇰 香港01" 与 "🇭🇰 [悦通] 香港01"）
                let m = trimmed.match(/^[\[\【「(]\s*([^\]\】」)]{1,24}?)\s*[\]\】」)][\s|｜:：/·\-_]*/);
                if (m) return { prefix: m[1].trim(), rest: trimmed.slice(m[0].length) };

                m = stripped.match(/^[\[\【「(]\s*([^\]\】」)]{1,24}?)\s*[\]\】」)][\s|｜:：/·\-_]*/);
                if (m) return { prefix: m[1].trim(), rest: stripped.slice(m[0].length) };

                // 2. 国旗之前的前缀（如 "良心云 🇭🇰 香港01"）
                const fm = trimmed.match(flagRegex);
                if (fm && fm.index > 0) {
                  const before = trimmed.slice(0, fm.index).replace(/^[\[\【「(\s]+|[\]\】」)\s|｜\-_:：/·]+$/g, "").trim();
                  if (before) return { prefix: before, rest: trimmed.slice(fm.index) };
                }

                // 3. 显式分隔符前缀（如 "🇭🇰 良心云 | 香港01"）
                m = stripped.match(/^([^|｜:：/]{1,20}?)\s*[|｜:：/]\s*/);
                if (m) return { prefix: m[1].trim(), rest: stripped.slice(m[0].length) };

                // 4. 空格/短横线前缀（如 "🇭🇰 良心云 香港01"）
                m = stripped.match(/^([^\s\-_]{1,20})(?:\s+|\s*[-_]\s*)/);
                if (m) return { prefix: m[1].trim(), rest: stripped.slice(m[0].length) };

                // 5. 无分隔符直接拼接订阅名（如 "🇭🇰 良心云香港01"）
                if (stripped.toLowerCase().startsWith(prof.toLowerCase())) {
                  return { prefix: prof, rest: stripped.slice(prof.length).replace(/^[\s|｜:：/·\-_]+/, "") };
                }

                return null;
              };

              const liveKeyMap = new Map();
              validNormalNames.forEach(nodeName => {
                const key = buildCoreKey(nodeName, nodeName);
                if (!liveKeyMap.has(key)) liveKeyMap.set(key, nodeName);
              });

              const fallbackMatched = [];
              pinnedNames.forEach(pinned => {
                const parsed = extractPrefixAndRest(pinned, cleanProfileName);
                if (!parsed || !isAirportMatch(parsed.prefix, cleanProfileName)) return;
                const matchedNode = liveKeyMap.get(buildCoreKey(pinned, parsed.rest));
                if (matchedNode) fallbackMatched.push(matchedNode);
              });
              matchedPinned = [...new Set(fallbackMatched)];
            }

      const targetRegionIds = parseRegionIds(rawStaticProxy.region ?? rawStaticProxy.regions);
      const regionNodes = [...new Set(
        activeRegionGroups
          .filter(g => targetRegionIds.includes(g.id))
          .flatMap(g => g.nodes)
      )];

      const autoChainSourceNodes = matchedPinned.length > 0 ? matchedPinned : regionNodes;

      autoChainSourceNodes.forEach(nodeName => {
        const autoChainNodeName = `${autoChainPrefix}${nodeName}`;
        autoChainNodeNames.push(autoChainNodeName);
        config.proxies.push({
          ...staticTemplate,
          name: autoChainNodeName,
          "dialer-proxy": nodeName
        });
      });
    }
  }

  const hasManualStaticGroup = hasStaticIP && manualChainNodeNames.length > 0;
  const hasAutoStaticGroup = hasStaticIP && autoChainNodeNames.length > 0;

  // -------------------------------------------------------------------------
  // 5. 构建策略组 (proxy-groups)
  // -------------------------------------------------------------------------
  // 各地区隐藏自动组采用 lazy: false（纯机场测速不触及静态 IP），保证手动前置跨地区链式测速随时处于热态
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
    // 高风控 / AI / Google 专用出口
    {
      name: "🚩 CustomIP",
      type: "select",
      proxies: [
        ...(hasManualStaticGroup ? [staticManualGroupName] : []),
        ...(hasAutoStaticGroup ? [staticAutoGroupName] : []),
        ...allRegionGroupNames,
        "📶 Auto"
      ]
    },

    // 手动前置静态链路组（组内直接测速「目标地区当前激活节点 -> 静态IP」端到端延迟）
    ...(hasManualStaticGroup ? [{
      name: staticManualGroupName,
      type: "select",
      proxies: manualChainNodeNames
    }] : []),

    // 静态链路自动测速组（可见，lazy: true 避免后台对静态 IP 空转测速，tolerance: 20 降低切换滞后）
    ...(hasAutoStaticGroup ? [{
      name: staticAutoGroupName,
      type: "url-test",
      url: "https://www.gstatic.com/generate_204",
      interval: 300,
      timeout: 10000,
      tolerance: 20,
      lazy: true,
      "expected-status": "204",
      proxies: autoChainNodeNames
    }] : []),

    // 常规海外流量出口
    {
      name: "✈️ Overseas",
      type: "select",
      proxies: ["🚩 CustomIP", ...allRegionGroupNames, "📶 Auto"]
    },

    // 各非空地区手动选择组（首项挂载对应的隐藏自动测速组）
    ...activeRegionGroups.map(g => ({
      name: g.name,
      type: "select",
      proxies: [g.auto, ...g.nodes, "DIRECT"]
    })),

    // 独立专项策略组
    {
      name: "▶️ YouTube",
      type: "select",
      proxies: ["🚩 CustomIP", "✈️ Overseas", ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "🌎️ IPmodify",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🚩 CustomIP", ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "🔘 Option",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🚩 CustomIP", ...allRegionGroupNames, "📶 Auto"]
    },
    {
      name: "🎮 Game",
      type: "select",
      proxies: ["✈️ Overseas", "DIRECT", "🚩 CustomIP", ...allRegionGroupNames, "📶 Auto"]
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
      proxies: ["✈️ Overseas", "DIRECT", "🚩 CustomIP", ...allRegionGroupNames, "📶 Auto"]
    },

    // 全局有效节点自动测速（lazy: false 保证作为手动前置入口时随时指向最优机场节点）
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

    // 隐藏测速前置选择器（仅外部低并发脚本通过 REST API 调度，面板不可见）
    ...(hasStaticIP && validNormalNames.length > 0 ? [{
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

  // 规则顺序：局域网/NTP -> 探测屏蔽 -> 个人与广告规则 -> 国内与豁免服务 -> 海外 QUIC 阻断 -> 业务规则 -> 兜底
  config.rules = [
    // 局域网与 NTP 时间同步优先直连
    "GEOIP,LAN,DIRECT,no-resolve",
    "AND,((NETWORK,UDP),(DST-PORT,123)),DIRECT",
    ...pickRulesets(["LocalAreaNetwork"]),

    // 屏蔽单栈 IP 探测接口与前端遥测端点，ping0.cc 主站走 CustomIP 检测出口质量
    "AND,((NETWORK,UDP),(DST-PORT,443),(DOMAIN-SUFFIX,ping0.cc)),REJECT",
    "DOMAIN,ipv4.ping0.cc,REJECT",
    "DOMAIN,ipv4.icanhazip.com,REJECT",
    "DOMAIN,ipv4.ip.sb,REJECT",
    "DOMAIN,browser-intake-datadoghq.com,REJECT",
    "DOMAIN,openai.qualtrics.com,REJECT",
    "DOMAIN-SUFFIX,ping0.cc,🚩 CustomIP",

    // 个人最高优先级规则与广告/劫持拦截
    ...pickRulesets(["CustomIP", "Direct", "Proxy", "UnBan", "Reject", "Hijacking", "BanAD", "BanProgramAD"]),

    // 国内直连服务与 Apple 豁免（位于 QUIC 阻断前，保障国内 HTTP/3 与 Apple 推送正常）
    ...pickRulesets(["HoYoverse", "ChinaMedia", "ChinaDomain", "Apple"]),
    "DOMAIN-SUFFIX,cn,DIRECT",
    "GEOIP,CN,DIRECT",

    // 阻断剩余海外流量的 UDP 443 (QUIC)，促使客户端回退至 TCP
    "AND,((NETWORK,UDP),(DST-PORT,443)),REJECT",

    // 海外核心业务与兜底分流
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

  // 通过 #策略组名 指定海外 DoH 的代理出口，使 DNS 解析出口与流量出口一致
  const foreignDohViaGroup = groupName => [
    `https://1.1.1.1/dns-query#${groupName}`,
    `https://1.0.0.1/dns-query#${groupName}`,
    `https://8.8.8.8/dns-query#${groupName}`
  ];

  const nameserverPolicy = {
    "+.ping0.cc": foreignDohViaGroup("🚩 CustomIP")
  };

  // 自动将所有需要域名解析的规则集同步绑定至对应策略组的 DNS 出口
  USER_CONFIG.rulesets.forEach(item => {
    if (item.group === "REJECT" || item.noResolve) return;
    const policyKey = `rule-set:script_${item.id}`;
    nameserverPolicy[policyKey] = item.group === "DIRECT"
      ? cnEncryptedDns
      : foreignDohViaGroup(item.group);
  });

  // Fake-IP 过滤白名单（系统连通性探测、国内网银与运营商认证域名）
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
    "prefer-h3": false,                        // 配合 respect-rules 时关闭 DoH HTTP/3 避免潜在兼容问题
    "respect-rules": true,                     // DNS 请求遵循分流规则（需搭配 proxy-server-nameserver 使用）
    "use-hosts": true,
    "use-system-hosts": true,
    "fake-ip-filter": fakeIpFilter,
    "default-nameserver": [
      "tls://223.5.5.5",
      "tls://1.12.12.12"
    ],
    nameserver: cnEncryptedDns,
    "direct-nameserver": cnEncryptedDns,
    "proxy-server-nameserver": cnEncryptedDns, // 代理节点域名走国内加密 DNS 解析，防止循环依赖
    "nameserver-policy": nameserverPolicy
  };

  return config;
}
