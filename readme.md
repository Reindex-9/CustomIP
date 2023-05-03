网络搬运后修改留档自用。  
emoji大全：https://emojixd.com/  
4.26策略组已统一，分流规则待整理。  

# ACL4SSR——订阅链接转换  
自定义配置raw链：https://raw.githubusercontent.com/Reindex-9/CustomIP/main/ACL4SSR_rules.ini  
参考配置：https://github.com/ACL4SSR/ACL4SSR/tree/master/Clash/config  
  
つつの订阅转换：https://m.sub.tsutsu.one/  
ACL4SSR订阅转换：https://acl4ssr-sub.github.io/  
  
原地址：https://github.com/Wzieee/custom-network-rules  
使用方法：“ACL4SSR在线订阅转换”，点击“进阶模式”，导入订阅链接，远程配置把这个仓库里面的“.ini”结尾的文件地址填上去，转换导入clash即可。  

# Clash——paser处理  
### 策略组
- **模式**  
**CustomIP**（根据地区切换节点）；**Auto**（自动测速）；**OutSide**（国外网站默认）；**Option**（自选模式）；**PROXY**（选择节点）；**Reject**（广告拦截；反劫持）；**Final**（黑白名单模式：未命中规则默认直连/代理）。  
- **地区分类**  
北美，欧洲，港澳台，日韩新，大洋洲，冷门国家  
  
原地址：https://github.com/Fndroid/clash_for_windows_pkg/issues/2193  
使用方法：Clash-设置（Settings）-配置（Profiles）-配置文件预处理（Pasers）  


# 常见问题  
1. 若用paser更新配置后出现“context deadline exceeded”错误提示无法切换配置，或订阅链接转换后提示下载配置超时，关闭代理模式再重新更新保存即可。  
2. 订阅链接转换后保存失败提示EOF，不一定配置有误，可能是后端的问题，切换一个。ACL4SSR的默认后端，个人在转换时经常出问题。
3. 若clash运行出现错误io：read/write on closed pipe，代表时间设定有问题，vmess协议对时间要求比较严格，清理缓存或删除订阅链接重新下载即可。

# 规则集排序自定义  
**1. 局域网地址**（必须有，一般直连）  
LocalAreaNetwork.list  
**2. 修正Unbreak**（主要防止跟后续拦截冲突，提前放行）  
Unbreak.list（ConnersHua）  
**3. 拦截Reject**（去广告，反劫持）  
BanAD.list ( acl4ssr 10分推荐)；BanProgramAD.list ( acl4ssr 10分推荐)；BanEasyListChina.list ( acl4ssr 5分推荐)；Reject.list (lhie1)  
**4. 特殊直连域名**（根据需求添加）  
GoogleCN.list （能直连的谷歌域名）；AsianTV.list (lhie1)；Special.list (lhie1,喜欢用BT下载的推荐)；Netease Music.list (lhie1，用网易云会员破解的加上)  
**5. 特殊代理域名**（根据需求添加）  
Netflix.list ( acl4ssr )；OneDrive.list ( acl4ssr )；GlobalTV.list (lhie1)；AppleNews.list（ConnersHua）；HKMTMedia.list（ConnersHua）  
**6. 可直连也可代理**（根据需求添加）  
Microsoft，Apple  
**7. 一般代理域名**（一般要加）  
ProxyLite.list( acl4ssr 10分推荐)；ProxyGFWlist.list( acl4ssr 7分推荐)  
**8. 一般直连域名**（一般要加）  
ChinaDomain.list ( acl4ssr 10分推荐)；ChinaCompanyIp.list ( acl4ssr 10分推荐)  
**9. GEO IP定位**  
根据IP地址(支持IPv4和IPv6), 定位该IP所在的 洲、经纬度、国家、省市、ASN 等信息。
例如在Quantumult(X)中，设置以下规则：{"GEOIP,US,USProxy" "GEOIP,CN,Direct"}
这段规则的意思是，如果访问的IP在GeoIP数据库中的地理位置为美国(US)，则使用USProxy这个策略内的服务器节点进行访问；如果是中国(CN)，则使用Direct策略。
设置GEOIP(CN)直连后在Google Play下载的Bing也走直连，显示Bing Chat无法在该地区使用。
**10. 兜底策略Final**  
FINAL 一般兜底代理，用GFW的可以选择兜底直连。
  
原地址：https://gist.github.com/Teraflopst/d53f1dbc3dcc350154c1beba03290a4b  
