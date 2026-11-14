// JavaScript 预处理脚本，可用于ClashVerge、FIClash等软件
// 最新更新：2026-11-15
// 功能：
// 1.链式代理，需手动编辑文件配置静态IP相关字段
// 2.匹配关键字添加国旗 Emoji，且防止机场自带 emoji 导致重复添加
// 3.策略组：CustomIP、Proxy、Download、IPmodify、Option、Game、Final、Info、Direct、Reject以及地区策略组
function main(config) {
  if (!config.proxies || config.proxies.length === 0) return config;

  // 1. 节点名称重命名：匹配关键字并添加国旗 Emoji
  const hasCode = (name, code) =>
    new RegExp(`(?:^|[^A-Za-z])${code}(?=$|[^A-Za-z])`, "i").test(name);

  const country = {
    hk: n => /香港|深港|沪港|京港|港|Hong Kong/i.test(n) || hasCode(n, "HK"),
    tw: n => /台湾|台灣|台北|台中|新北|彰化|Taiwan/i.test(n) || hasCode(n, "TW"),
    jp: n => /日本|东京|大阪|京日|苏日|沪日|上日|深日|广日|川日|Japan/i.test(n) || hasCode(n, "JP"),
    sg: n => /新加坡|狮城|Singapore/i.test(n) || hasCode(n, "SG"),
    us: n => /美国|美國|凤凰城|洛杉矶|西雅图|芝加哥|纽约|俄勒冈|弗吉尼亚|沪美|United States/i.test(n) || hasCode(n, "US"),
    kr: n => /韩|韓|首尔|春川|Korea/i.test(n) || hasCode(n, "KR") || hasCode(n, "KOR"),
    uk: n => /英国|英國|United Kingdom/i.test(n) || hasCode(n, "UK"),
    de: n => /德国|德國|Germany/i.test(n) || hasCode(n, "DE") || hasCode(n, "GER"),
    fr: n => /法国|法國|France/i.test(n) || hasCode(n, "FR"),
    it: n => /意大利|Italy/i.test(n) || hasCode(n, "IT"),
    ca: n => /加拿大|Canada/i.test(n) || hasCode(n, "CA"),
    mo: n => /澳门|澳門|Macau|Macao/i.test(n) || hasCode(n, "MO")
  };

  const emojiMap = [
    ["hk", "🇭🇰"],
    ["tw", "🇹🇼"],
    ["jp", "🇯🇵"],
    ["sg", "🇸🇬"],
    ["us", "🇺🇸"],
    ["kr", "🇰🇷"],
    ["uk", "🇬🇧"],
    ["de", "🇩🇪"],
    ["fr", "🇫🇷"],
    ["it", "🇮🇹"],
    ["ca", "🇨🇦"],
    ["mo", "🇲🇴"]
  ];

  config.proxies.forEach(proxy => {
    for (const [key, emoji] of emojiMap) {
      if (country[key](proxy.name)) {
        // 防止机场自带 emoji 导致重复添加
        if (!proxy.name.includes(emoji)) {
          proxy.name = `${emoji} ${proxy.name}`;
        }
        break;  // 匹配到一个国家后就跳出循环
      }
    }
  });

  // =========================================================================
  // 👇 注入链式代理前置组与静态节点
  // =========================================================================
  const staticIPName = "🏠 专属静态IP";
  const frontSelectorName = "🪢 前置节点"; // 用于手动选择链式代理的前置策略组

  // 把需要拨号的静态节点条件注入到底层 proxies 列表里，const staticIPConfig配置静态节点
  const staticIPConfig = {
    type: "socks5",   // ⚠️ 需要修改，填节点类型，如vmess/ss/https/socks5
    server: "",       // ⚠️ 需要修改，填服务器IP
    port: 443,        // ⚠️ 需要修改，填端口号
    username: "",     // ⚠️ 需要修改，填用户名
    password: ""      // ⚠️ 需要修改，填密码
  };

  const hasStaticIP =
    typeof staticIPConfig.server === "string" &&
    staticIPConfig.server.trim() !== "" &&
    staticIPConfig.server !== "服务器IP或域名" &&
    Number.isInteger(Number(staticIPConfig.port)) &&
    Number(staticIPConfig.port) > 0;

  if (hasStaticIP) {
    const staticNode = {
      name: staticIPName,
      type: staticIPConfig.type,
      server: staticIPConfig.server.trim(),
      port: Number(staticIPConfig.port),
      "dialer-proxy": frontSelectorName     // 让静态IP（如果存在）通过前置节点连接
    };

    if (staticIPConfig.username) {
      staticNode.username = staticIPConfig.username;
    }

    if (staticIPConfig.password) {
      staticNode.password = staticIPConfig.password;
    }

    config.proxies.push(staticNode);
  }
  //  【代理协议鉴权字段说明】
  // 根据节点实际协议 (type) 修改上述字段：
  // 1. HTTP / SOCKS5 协议：依赖 username 和 password 字段。
  // 2. VMess / VLESS 协议：依赖 uuid 字段，无账号密码概念。
  // 3. SS (Shadowsocks) / Trojan 协议：依赖 password 字段。
  // =========================================================================

  // 2. 获取加上 Emoji 之后的订阅节点名称
  const proxyNames = config.proxies.map(p => p.name);

  // 辅助函数：根据国家匹配函数筛选节点
  function getProxiesByMatcher(matcher) {
    return proxyNames.filter(
      name => name !== staticIPName && matcher(name)    //排除静态 IP
    );
  }

  const isEurope = n =>         //判断欧洲节点
    country.de(n) ||
    country.uk(n) ||
    country.fr(n) ||
    country.it(n);

  const isGreaterAsia = n =>    //判断港澳台节点
    country.hk(n) ||
    country.mo(n) ||
    country.tw(n);

  const isEastAsia = n =>       //判断日韩新节点
    country.jp(n) ||
    country.kr(n) ||
    country.sg(n);

  const isMainRegion = n =>     //判断节点是否属于主流节点
    country.us(n) ||
    isEurope(n) ||
    isGreaterAsia(n) ||
    isEastAsia(n);

  const isInfoNode = n =>       //排除流量、到期、音乐、游戏等信息节点
    /剩余|套餐|到期|流量|更新|网址|重置|官网|防失联|静态IP|music|𝐌𝐮𝐬𝐢𝐜|Unbolck|网易云|音乐|Music|Netease|🎶|手游|游戏|game/i.test(n);

  // 3.  proxy-groups (策略组)
  config["proxy-groups"] = [
    {
      name: "🚩 CustomIP",
      type: "select",
      // 👇 把静态IP（如果存在）放进 CustomIP 组的第一个
      proxies: [
        ...(hasStaticIP ? [staticIPName] : []),
        "🇺🇸 美国",
        "🌐 欧洲",
        "🌐 港澳台",
        "🌐 日韩新",
        "🌐 冷门国家",
        "🗺️ AllNodes"
      ]
    },
    {
      name: "✈️ Overseas",
      type: "select",
      proxies: ["🚩 CustomIP", "🇺🇸 美国", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家", "🗺️ AllNodes"]
    },
    {
      name: "🇺🇸 美国",
      type: "select",
      proxies: getProxiesByMatcher(country.us).concat(["DIRECT"])
    },
    {
      name: "🌐 欧洲",
      type: "select",
      proxies: getProxiesByMatcher(isEurope).concat(["DIRECT"])
    },
    {
      name: "🌐 港澳台",
      type: "select",
      proxies: getProxiesByMatcher(isGreaterAsia).concat(["DIRECT"])
    },
    {
      name: "🌐 日韩新",
      type: "select",
      proxies: getProxiesByMatcher(isEastAsia).concat(["DIRECT"])
    },
    {
      name: "🌐 冷门国家",
      type: "select",
      proxies: getProxiesByMatcher(
        n => !isInfoNode(n) && !isMainRegion(n)
      ).concat(["DIRECT"])
    },
    {
      name: frontSelectorName,    // 前置节点手动选择组
      type: "select",
      proxies: ["📶 Auto", "🗺️ AllNodes", "🇺🇸 美国", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家"]
    },
    {
      name: "📶 Auto",       // 📶 全部节点，自动测速，可用于为静态IP挑选最快机场节点
      type: "url-test",
      url: "https://www.gstatic.com/generate_204",
      interval: 300,
      tolerance: 50,
      proxies: getProxiesByRegex("^((?!剩余|套餐|到期|流量|更新|网址|重置|官网|防失联|静态IP|music|𝐌𝐮𝐬𝐢𝐜|Unbolck|网易云|音乐|Music|Netease|🎶|手游|游戏|game).)*$")
    },
        {
      name: "🗺️ AllNodes",       // 全部节点，手动选择
      type: "select",
      proxies: getProxiesByRegex("^((?!剩余|套餐|到期|流量|更新|网址|重置|官网|防失联|静态IP|music|𝐌𝐮𝐬𝐢𝐜|Unbolck|网易云|音乐|Music|Netease|🎶|手游|游戏|game).)*$")
    },
    {
      name: "🔖 Info",
      type: "select",
      proxies: getProxiesByRegex("^(?=.*(?:剩余|套餐|到期|流量|更新|网址|重置|官网|防失联)).*$")
    },
    {
      name: "♾️ Final",
      type: "select",
      proxies: ["✈️ Overseas", "DIRECT", "🚩 CustomIP",  "🇺🇸 美国","🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家", "🗺️ AllNodes"]
    },
    {
      name: "🌎️ IPmodify",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🚩 CustomIP", "🇺🇸 美国", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家", "🗺️ AllNodes"]
    },
    {
      name: "🔘 Option",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🚩 CustomIP", "🇺🇸 美国", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家", "🗺️ AllNodes"]
    },
    {
      name: "🎮 Game",
      type: "select",
      proxies: ["✈️ Overseas", "DIRECT", "🚩 CustomIP", "🌐 冷门国家",  "🇺🇸 美国","🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🗺️ AllNodes"]
    },
    // 下载专用组，默认直连防偷跑，也可手动切换大流量节点
    {
      name: "📥 Download",
      type: "select",
      proxies: ["DIRECT", "✈️ Overseas", "🌐 冷门国家",  "🇺🇸 美国","🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🗺️ AllNodes"]
    },
    {
      name: "🎯 Direct",
      type: "select",
      proxies: ["DIRECT"]
    },
    {
      name: "🚫 Reject",
      type: "select",
      proxies: ["REJECT"]
    }
  ];

  // 容错处理：当某些国家分组无节点时自动补充 DIRECT 防止软件解析崩溃
  config["proxy-groups"].forEach(group => {
    if (!group.proxies || group.proxies.length === 0) {
      group.proxies = ["DIRECT"];
    }
  });

  // 4. 重写 rule-providers (规则集)
  const rawRulesets = [
    ["🚩 CustomIP", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/CustomIP.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/Direct.list"],
    ["✈️ Overseas", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/Proxy.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/wlxuf/add_rule/main/direct-amend.list"],
    ["✈️ Overseas", "https://raw.githubusercontent.com/wlxuf/add_rule/main/proxy-amend.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/LocalAreaNetwork.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/UnBan.list"],
    ["REJECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list"],
    ["🚫 Reject", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list"],
    ["🚫 Reject", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyListChina.list"],
    ["REJECT", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Hijacking/Hijacking.list"],
    ["🚫 Reject", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/Reject.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/ruleset/ruleset/AI.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/GoogleCNProxyIP.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Google/Google.list"],
    ["🔘 Option", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Microsoft/Microsoft.list"],
    ["🔘 Option", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Apple/Apple.list"],
    ["🌎️ IPmodify", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/refs/heads/master/rule/Clash/XiaoHongShu/XiaoHongShu.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/HoYoverse/HoYoverse.list"],
    ["🎮 Game", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Game/Game.list"],
    ["✈️ Overseas", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Telegram/Telegram.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaMedia.list"],
    ["✈️ Overseas", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyMedia.list"],
    ["✈️ Overseas", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyGFWlist.list"],
    ["DIRECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list"],
    ["DIRECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaCompanyIp.list"],
    ["📥 Download", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Download.list"],
    ["DIRECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaIp.list"]
  ];

  //第210-259行，保留订阅的 DNS 引用的规则集，清空其他订阅中的规则集
  const originalProviders = config["rule-providers"] || {};
  const dns = config.dns || {};
  const requiredProviders = new Set();

  function cleanPolicy(policy) {
    if (!policy || typeof policy !== "object") return policy;

    const result = {};

    for (const [key, value] of Object.entries(policy)) {
      const parts = String(key).split(",").map(x => x.trim()).filter(Boolean);

      const validParts = parts.filter(part => {
        const match = part.match(/^rule-set:(.+)$/i);
        return !match || Boolean(originalProviders[match[1].trim()]);
      });

      if (validParts.length > 0) {
        result[validParts.join(",")] = value;

        for (const part of validParts) {
          const match = part.match(/^rule-set:(.+)$/i);
          if (match) requiredProviders.add(match[1].trim());
        }
      }
    }

    return result;
  }

  dns["nameserver-policy"] = cleanPolicy(dns["nameserver-policy"]);

  dns["proxy-server-nameserver-policy"] = cleanPolicy(
    dns["proxy-server-nameserver-policy"]
  );

  if (Array.isArray(dns["fake-ip-filter"])) {
    dns["fake-ip-filter"] = dns["fake-ip-filter"].filter(item => {
      const match = String(item).match(/^RULE-SET,\s*([^,]+)/i);
      if (!match) return true;

      if (originalProviders[match[1].trim()]) {
        requiredProviders.add(match[1].trim());
        return true;
      }

      return false;
    });
  }

  const retainedProviders = {};

  for (const name of requiredProviders) {
    const provider = originalProviders[name];

    if (!provider) continue;

    retainedProviders[name] = { ...provider };

    if (provider.type === "http") {
      retainedProviders[name].proxy = "📶 Auto";
    }
  }

  config["rule-providers"] = retainedProviders;

  const customRules = [];

  rawRulesets.forEach((item, index) => {
    const targetGroup = item[0] === "REJECT" ? "🚫 Reject" : item[0];
    const url = item[1];
    const providerName = `user_rule_${index}`;
    
    // 注入 provider 配置
    config["rule-providers"][providerName] = {
      type: "http",
      behavior: "classical",
      format: "text",
      path: `./rules/${providerName}.list`,
      url: url,
      interval: 86400,
      proxy: "📶 Auto"  //规则文件下载和更新:通过Auto选择最快的节点下载。
    };
    
    // 注入分流规则
    customRules.push(`RULE-SET,${providerName},${targetGroup}`);
  });

  // 5. 追加末尾特殊规则
  customRules.unshift("AND,((NETWORK,UDP),(DST-PORT,443)),REJECT");   // 把拒绝 QUIC (UDP 443) 的规则强制插入到所有规则的最前面
  customRules.push("GEOIP,CN,🎯 Direct"); 
  customRules.push("MATCH,♾️ Final");

  // 将构造好的规则覆盖原有系统规则
  config.rules = customRules;

  return config;
}
