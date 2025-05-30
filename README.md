参考网络配置修改留档自用。  
注：直接修改本地设置，才能实时更改分流结果；github代码修改后会延迟更新，修改文件名可以立即更新

# App配置下载
Shadowrocket：https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/ShodowrocketConfig.conf  
QuantumulX：https://raw.githubusercontent.com/Reindex-9/CustomIP/refs/heads/main/QuantumulX_MyConfig.conf  
注：raw链下载配置可能失败，换成镜像站地址即可。  

# ACL4SSR——订阅链接转换  
自定义配置raw链：https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ACL4SSRrules.ini  
自定义配置镜像链接：https://raw.gitmirror.com/Reindex-9/CustomIP/main/ACL4SSR_rules.ini  

ACL4SSR订阅转换：https://acl4ssr-sub.github.io/  
使用方法：“ACL4SSR在线订阅转换”，点击“进阶模式”，导入订阅链接，远程配置把这个仓库里面的“.ini”结尾的文件地址填上去，转换导入clash即可。  
> 参考：https://github.com/Wzieee/custom-network-rules
> 参考配置：https://github.com/ACL4SSR/ACL4SSR/tree/master/Clash/config  

  
# 规则匹配参数
- 域名匹配
  - DOMAIN-KEYWORD：域名关键字匹配，通常采用主机名，但只要域名中含有特定的关键字，就会被这个规则匹配
  - DOMAIN-SUFFIX：域名后缀匹配
  - DOMAIN：全域名（= 子域名+ 主域名 + 顶级域名 ）匹配
  - 域名说明
    - 顶级域名：表示网站的类型或所属的地理区域；位于网址结构中的最后部分；常见的顶级域名包括 ".com"（商业用途）、".org"（非营利组织）、".net"（网络服务提供商）、".gov"（政府机构）以及国家代码顶级域名如 ".cn"（中国）、".uk"（英国）等
    - 主域名：= 二级域名+顶级域名，网址的核心部分，代表网站的主体
    - 子域名：主域名下的一个分支，用于组织和区分网站的不同部分或服务
    - 示例：网站`docs.microsoft.com`，子域名`docs`，主域名`microsoft.com`，顶级域名`.com`
- IP段匹配
  - IP-CIDR：目标IP 段匹配（IPv4，匹配IPv6的关键字为IP-CIDR6）
  - SRC-IP-CIDR：源 IP 段匹配
  - GEOIP：GEOIP 数据库（国家代码）匹配，将IP匹配IP归属地
- DST-PORT：目标端口匹配
- SRC-PORT：源端口匹配
- PROCESS-NAME：源进程名匹配（e.g. steam.exe）
- RULE-SET：Rule Provider 规则匹配
- MATCH：全匹配
  
# 特定App
## Clash——paser处理  
### 策略组
- **模式**  
**CustomIP**（根据地区切换节点）；**Auto**（自动测速）；**OutSide**（国外网站默认）；**Option**（自选模式）；**PROXY**（选择节点）；**Reject**（广告拦截；反劫持）；**Final**（黑白名单模式：未命中规则默认直连/代理）。  
- **地区分类**  
北美，欧洲，港澳台，日韩新，大洋洲，冷门国家  
  
> 原地址：https://github.com/Fndroid/clash_for_windows_pkg/issues/2193  
> 使用方法：Clash-设置（Settings）-配置（Profiles）-配置文件预处理（Pasers）  

## Shadowrocket
参考配置：https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/lazy_group.conf

## V2Ray
绕过大陆（白名单模式）：如果访问的网站在白名单内，该网站直连；反之如果不在白名单内，则通过代理。FINAL代理。
黑名单模式：如果访问的网站在黑名单内，该网站通过代理；如果不在黑名单内，则直连。FINAL直连。

# 常见问题  
1. 使用RAW链接可能导致配置下载超时，使用镜像加速域名替换RAW链接以避免出错。  
```
  - 将 *raw.githubusercontent.com* 替换为 *raw.githubusercontents.com* => 后面加个s  
  - https://cdn.jsdelivr.net/gh/用户名/仓库名@分支名/文件夹/文件名.list => 使用新CDN链接
```  
2. 若用paser更新配置后出现“context deadline exceeded”，或订阅链接转换后保存失败提示下载配置超时，关闭代理模式再重新更新保存，或者换个网络。如果还是都解决不了，复制转换后的链接到浏览器，直接下载文件，再导入Clash。  
# 规则集排序自定义
| 顺序 | 类别 | 规则集 | 作者 | 说明 |
| :----: | :----: | :----- | :----: | :----- |
| 1 | DIRECT直连 |  |  | 优先级最高 |
|  |  | LocalAreaNetwork.list | acl4ssr | 局域网地址 |
|  |  | UnBan.list | acl4ssr | ？ |
| 2 | REJECT拦截 |  |  | 去广告，反劫持 |
|  |  | BanAD.list | acl4ssr | 广告联盟。只包含常见广告关键字，无副作用 |
|  |  | BanProgramAD.list | acl4ssr | 应用内广告拦截，可能有轻微副作用 |
|  |  | BanEasyListChina.list | acl4ssr | AdblockPlus中的中国所有的屏蔽域名 |
|  |  | Hijacking.list | lhie1 | 反劫持 |
| 3 | 特殊直连 | GoogleCN，AsianTV | | 根据需求添加 |
| 4 | 特殊代理 | Netflix，OneDrive |  | 根据需求添加 |
| 5 | 可选 | Microsoft，Apple | | 可直连也可代理 |
| 6 | 一般代理 |  |  |  |
|  |  | ProxyLite.list | acl4ssr |  |
|  |  | ProxyGFWlist.list | acl4ssr |  |
| 7 | 一般直连 |  |  |  |
|  |  | ChinaDomain.list | acl4ssr |  |
|  |  | ChinaCompanyIp.list | acl4ssr |  |
| 8 | GEOIP定位 |  |  | 根据IP地址定位该IP的地理信息。例如```GEOIP,US,USProxy```表明，若访问的IP在GeoIP数据库中的地理位置为美国(US)则使用USProxy策略。
| 9 | FINAL兜底 |  |  | 若未命中规则，使用终极策略 |
> 原地址：https://gist.github.com/Teraflopst/d53f1dbc3dcc350154c1beba03290a4b  
