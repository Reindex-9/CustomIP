网络搬运后修改留档自用。  
emoji大全：https://emojixd.com/  

# ACL4SSR——订阅链接转换  
自定义配置raw链：https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ACL4SSR_rules.ini  
参考配置：https://github.com/ACL4SSR/ACL4SSR/tree/master/Clash/config  
  
つつの订阅转换：https://m.sub.tsutsu.one/  
ACL4SSR订阅转换：https://acl4ssr-sub.github.io/  
  
> 原地址：https://github.com/Wzieee/custom-network-rules  
> 使用方法：“ACL4SSR在线订阅转换”，点击“进阶模式”，导入订阅链接，远程配置把这个仓库里面的“.ini”结尾的文件地址填上去，转换导入clash即可。  

# Clash——paser处理  
### 策略组
- **模式**  
**CustomIP**（根据地区切换节点）；**Auto**（自动测速）；**OutSide**（国外网站默认）；**Option**（自选模式）；**PROXY**（选择节点）；**Reject**（广告拦截；反劫持）；**Final**（黑白名单模式：未命中规则默认直连/代理）。  
- **地区分类**  
北美，欧洲，港澳台，日韩新，大洋洲，冷门国家  
  
> 原地址：https://github.com/Fndroid/clash_for_windows_pkg/issues/2193  
> 使用方法：Clash-设置（Settings）-配置（Profiles）-配置文件预处理（Pasers）  


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
| 1 | 局域网Local |  |  | 一般直连 |
|  |  | LocalAreaNetwork.list | acl4ssr |  |
|  |  | UnBan.list | acl4ssr | ？ |
| 2 | 修正 | Unbreak.list | ConnersHua | 防止跟后续拦截冲突，提前放行 |
| 3 | 拦截 |  |  | 去广告，反劫持 |
|  |  | BanAD.list | acl4ssr | 广告联盟。只包含常见广告关键字，无副作用 |
|  |  | BanProgramAD.list | acl4ssr | 应用内广告拦截，可能有轻微副作用 |
|  |  | BanEasyListChina.list | acl4ssr | AdblockPlus中的中国所有的屏蔽域名 |
|  |  | Hijacking.list | lhie1 | 反劫持 |
| 4 | 特殊直连 | GoogleCN，AsianTV | | 根据需求添加 |
| 5 | 特殊代理 | Netflix，OneDrive |  | 根据需求添加 |
| 6 | 可选 | Microsoft，Apple | | 可直连也可代理 |
| 7 | 一般代理 |  |  |  |
|  |  | ProxyLite.list | acl4ssr |  |
|  |  | ProxyGFWlist.list | acl4ssr |  |
| 8 | 一般直连 |  |  |  |
|  |  | ChinaDomain.list | acl4ssr |  |
|  |  | ChinaCompanyIp.list | acl4ssr |  |
| 9 | GEOIP定位 |  |  | 根据IP地址定位该IP的地理信息。例如```GEOIP,US,USProxy```表明，若访问的IP在GeoIP数据库中的地理位置为美国(US)则使用USProxy策略。
| 10 | 兜底策略 |  |  | Final，若未命中规则，使用终极策略 |

> 原地址：https://gist.github.com/Teraflopst/d53f1dbc3dcc350154c1beba03290a4b  
