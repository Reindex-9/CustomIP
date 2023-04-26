网络搬运后修改留档  
# Clash——paser处理  
### 策略组
- 模式  
**PROXY**（选择节点）；**CustomIP**（根据地区切换节点）；**Auto**（自动测速）；**Final**（黑白名单模式；切换直连/代理）；**Reject**（广告拦截；反劫持）  
- 地区分类  
北美，欧洲，港澳台，日韩新，大洋洲，冷门国家  
### 常见问题  
若用paser更新配置后出现“context deadline exceeded”错误，提示无法切换配置，关闭代理模式再重新更新即可。
### 参考  
emoji大全：https://emojixd.com/  
原地址1：https://github.com/Fndroid/clash_for_windows_pkg/issues/2193  
原地址2：https://github.com/Fndroid/clash_for_windows_pkg/issues/2729  

# 规则集排序自定义  

**1. 局域网地址**（必须有，一般直连）  
LocalAreaNetwork.list  
**2. 修正Unbreak**（主要防止跟后续拦截冲突，提前放行）  
Unbreak.list（ConnersHua）  
**3. 拦截Reject**（去广告，反劫持）  
BanAD.list ( acl4ssr 10分推荐)；BanProgramAD.list ( acl4ssr 10分推荐)；BanEasyListChina.list ( acl4ssr 5分推荐)；Reject.list (lhie1)  
**4. 特殊直连域名**（根据需求添加）  
GoogleCN.list （能直连的谷歌域名）；AsianTV.list (lhie1)；Special.list (lhie1,喜欢用BT下载的推荐)；Netease Music.list (lhie1，用网易云会员破解的加上)；
**5. 特殊代理域名**（根据需求添加）  
Netflix.list ( acl4ssr )；OneDrive.list ( acl4ssr )；GlobalTV.list (lhie1)；AppleNews.list（ConnersHua）；HKMTMedia.list（ConnersHua）  
**6. 可直连也可代理**（根据需求添加）  
Microsoft，Apple  
**7. 一般代理域名**（一般要加）  
ProxyLite.list( acl4ssr 10分推荐)；ProxyGFWlist.list( acl4ssr 7分推荐)  
**8. 一般直连域名**（一般要加）  
ChinaDomain.list ( acl4ssr 10分推荐)；ChinaCompanyIp.list ( acl4ssr 10分推荐)  
**9. GEO IP定位**  
GEOIP,CN 直连（10分推荐）  
**10. 兜底策略**  
FINAL 一般兜底代理 (10分推荐)；用GFW的可以选择兜底直连 (5分推荐)  
  
原地址：https://gist.github.com/Teraflopst/d53f1dbc3dcc350154c1beba03290a4b  
# Clash——订阅链接转换  
raw链：https://raw.githubusercontent.com/Reindex-9/CustomIP/main/Clash_custom-rules.ini  
参考配置：https://github.com/ACL4SSR/ACL4SSR/tree/master/Clash/config  
原地址：https://github.com/Wzieee/custom-network-rules  
在线转换地址：https://acl4ssr-sub.github.io/  
#### 使用方法  
“ACL4SSR在线订阅转换”，点击“进阶模式”，导入订阅链接（机场、自建的），远程配置把这个仓库里面的“.ini”结尾的文件地址填上去，转换导入clash即可
。
