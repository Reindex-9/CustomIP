function main(config) {
  if (!config.proxies || config.proxies.length === 0) return config;

  // 1. 节点名称重命名：匹配关键字并添加国旗 Emoji
  const emojiMap = [
    { regex: /香港|深港|沪港|京港|港|HK|Hong Kong/i, emoji: "🇭🇰" },
    { regex: /台湾|台灣|台北|台中|新北|彰化|TW|Taiwan/i, emoji: "🇹🇼" },
    { regex: /日本|东京|大阪|京日|苏日|沪日|上日|深日|广日|川日|JP|Japan/i, emoji: "🇯🇵" },
    { regex: /新加坡|狮城|SG|Singapore/i, emoji: "🇸🇬" },
    { regex: /美国|美國|凤凰城|洛杉矶|西雅图|芝加哥|纽约|俄勒冈|弗吉尼亚|沪美|United States|US|us/i, emoji: "🇺🇸" },
    { regex: /韩|韓|首尔|春川|KR|Korea|KOR/i, emoji: "🇰🇷" },
    { regex: /英国|英國|UK|uk|United Kingdom/i, emoji: "🇬🇧" },
    { regex: /德国|德國|Germany|DE|Ger/i, emoji: "🇩🇪" },
    { regex: /法国|法國|France|FR/i, emoji: "🇫🇷" },
    { regex: /意大利|Italy/i, emoji: "🇮🇹" },
    { regex: /加拿大|Canada/i, emoji: "🇨🇦" },
    { regex: /澳门|澳門|Macau/i, emoji: "🇲🇴" }
  ];

  config.proxies.forEach(proxy => {
    for (let item of emojiMap) {
      if (item.regex.test(proxy.name)) {
        // 防止机场自带 emoji 导致重复添加
        if (!proxy.name.includes(item.emoji)) {
          proxy.name = `${item.emoji} ${proxy.name}`;
        }
        break; // 匹配到一个国家后就跳出循环
      }
    }
  });

  // 2. 获取加上 Emoji 之后的所有订阅节点名称
  const proxyNames = config.proxies.map(p => p.name);

  // 辅助函数：通过正则表达式严格匹配节点
  function getProxiesByRegex(regexStr) {
    const regex = new RegExp(regexStr, "i");
    return proxyNames.filter(name => regex.test(name));
  }

  // 3. 彻底重写 proxy-groups (策略组)
  config["proxy-groups"] = [
    {
      name: "🚩 CustomIP",
      type: "select",
      proxies: ["🌐 北美", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家"]
    },
    {
      name: "✈️ Proxy",
      type: "select",
      proxies: ["🚩 CustomIP", "🌐 北美", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家"]
    },
    {
      name: "🌐 北美",
      type: "select",
      proxies: getProxiesByRegex("^(?=.*(?:美国|美國|凤凰城|洛杉矶|西雅图|芝加哥|纽约|俄勒冈|弗吉尼亚|沪美|United States|US|us|加拿大|Canada)).*$").concat(["DIRECT"])
    },
    {
      name: "🌐 欧洲",
      type: "select",
      proxies: getProxiesByRegex("^(?=.*(?:德国|德國|Germany|DE|Ger|英国|英國|UK|uk|法国|法國|France|FR|意大利)).*$").concat(["DIRECT"])
    },
    {
      name: "🌐 港澳台",
      type: "select",
      proxies: getProxiesByRegex("^(?=.*(?:香港|深港|沪港|京港|港|HK|Hong Kong|澳门|澳門|Macau|台湾|台灣|台北|台中|新北|彰化|TW|Taiwan)).*$").concat(["DIRECT"])
    },
    {
      name: "🌐 日韩新",
      type: "select",
      proxies: getProxiesByRegex("^(?=.*(?:日本|东京|大阪|京日|苏日|沪日|上日|深日|广日|川日|JP|Japan|韩|韓|首尔|春川|KR|Korea|KOR|新加坡|狮城|SG|Singapore)).*$").concat(["DIRECT"])
    },
    {
      name: "🌐 冷门国家",
      type: "select",
      proxies: getProxiesByRegex("^((?!剩余|套餐|到期|流量|更新|网址|重置|官网|美国|美國|凤凰城|洛杉矶|西雅图|芝加哥|纽约|俄勒冈|弗吉尼亚|沪美|United States|US|us|加拿大|Canada|德国|德國|Germany|DE|Ger|英国|英國|UK|uk|法国|法國|France|FR|意大利|香港|深港|沪港|京港|港|HK|Hong Kong|澳门|澳門|Macau|台湾|台灣|台北|台中|新北|彰化|TW|Taiwan|日本|东京|大阪|京日|苏日|沪日|上日|深日|广日|川日|JP|Japan|韩|韓|首尔|春川|KR|Korea|KOR|新加坡|狮城|SG|Singapore).)*$").concat(["DIRECT"])
    },
    {
      name: "🔖 Info",
      type: "select",
      proxies: getProxiesByRegex("^(?=.*(?:剩余|套餐|到期|流量|更新|网址|重置|官网)).*$")
    },
    {
      name: "♾️ Final",
      type: "select",
      proxies: ["✈️ Proxy", "DIRECT", "🚩 CustomIP", "🌐 北美", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家"]
    },
    {
      name: "🌎️ IPmodify",
      type: "select",
      proxies: ["DIRECT", "✈️ Proxy", "🚩 CustomIP", "🌐 北美", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家"]
    },
    {
      name: "🔘 Option",
      type: "select",
      proxies: ["DIRECT", "✈️ Proxy", "🚩 CustomIP", "🌐 北美", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新", "🌐 冷门国家"]
    },
    {
      name: "🎮 Game",
      type: "select",
      proxies: ["✈️ Proxy", "DIRECT", "🚩 CustomIP", "🌐 冷门国家", "🌐 北美", "🌐 欧洲", "🌐 港澳台", "🌐 日韩新"]
    },
    {
      name: "📶 Auto",
      type: "url-test",
      url: "http://www.gstatic.com/generate_204",
      interval: 300,
      tolerance: 50,
      proxies: getProxiesByRegex("^((?!music|𝐌𝐮𝐬𝐢𝐜|Unbolck|网易云|音乐|Music|Netease|🎶|手游|游戏|game).)*$")
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

  // 4. 彻底重写 rule-providers (规则提供者)
  const rawRulesets = [
    ["🚩 CustomIP", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/CustomIP.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/Direct.list"],
    ["✈️ Proxy", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/Proxy.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/wlxuf/add_rule/main/direct-amend.list"],
    ["✈️ Proxy", "https://raw.githubusercontent.com/wlxuf/add_rule/main/proxy-amend.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/LocalAreaNetwork.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/UnBan.list"],
    ["REJECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list"],
    ["🚫 Reject", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list"],
    ["🚫 Reject", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyListChina.list"],
    ["REJECT", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Hijacking/Hijacking.list"],
    ["🚫 Reject", "https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ruleset/Reject.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OpenAI/OpenAI.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Bing/Bing.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Ruleset/GoogleCNProxyIP.list"],
    ["🚩 CustomIP", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Google/Google.list"],
    ["🔘 Option", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Microsoft/Microsoft.list"],
    ["🔘 Option", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Apple/Apple.list"],
    ["🌎️ IPmodify", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/refs/heads/master/rule/Clash/XiaoHongShu/XiaoHongShu.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/HoYoverse/HoYoverse.list"],
    ["🎮 Game", "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Game/Game.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaMedia.list"],
    ["✈️ Proxy", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyMedia.list"],
    ["✈️ Proxy", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ProxyGFWlist.list"],
    ["DIRECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list"],
    ["DIRECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaCompanyIp.list"],
    ["🎯 Direct", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/Download.list"],
    ["DIRECT", "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaIp.list"]
  ];

  config["rule-providers"] = {};
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
      interval: 86400
    };
    
    // 注入分流规则
    customRules.push(`RULE-SET,${providerName},${targetGroup}`);
  });

  // 5. 追加末尾特殊规则
  customRules.push("GEOIP,CN,🎯 Direct,no-resolve");
  customRules.push("MATCH,♾️ Final");

  // 将构造好的规则覆盖原有系统规则
  config.rules = customRules;

  return config;
}
