import argparse
import datetime
import json
import math
import os
import re
import sqlite3
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
# =================== 版本信息 =================
# v0.2 2026-11-24 新增历史数据库与多维评分功能。自动在同目录创建 static_chain_history.db 持久化所有批次，并生成 latest_recommendation.yaml 供参考复制。

# ================= 基础配置区 =================
CONTROLLER = "http://127.0.0.1:9097"      # Clash Verge 外部控制地址
SECRET = "set-your-secret"                # 外部控制 Secret（无密码留空 ""）

PROBE_GROUP = "🧪 测速前置"
PROBE_PROXY_PREFIX = "🧪 静态测速探针|"

TEST_URL = "https://www.gstatic.com/generate_204"
EXPECTED_STATUS = "204"
TIMEOUT_MS = 5000                         # 单次测速超时（毫秒）

# 可选初筛过滤（留空 [] 则测全部有效节点）
# 示例：INCLUDE_KEYWORDS = ["🇺🇸", "🇯🇵", "🇭🇰", "🇸🇬"]
INCLUDE_KEYWORDS = []
EXCLUDE_KEYWORDS = []

# 可选：手动声明已知机场前缀，优先精准匹配（适合前缀无空格/分隔符的命名）
# 示例：KNOWN_AIRPORTS = ["橘子云", "蓝鲸", "AirportA"]
KNOWN_AIRPORTS = []
DEFAULT_AIRPORT = "未标注机场"             # 单机场订阅且未传 --airport 时的默认归属名

# 测速节奏与复测参数
SLEEP_BETWEEN_NODES = 0.30                # 每次探测后休眠（秒），保护静态 IP
SWITCH_SETTLE_SEC = 0.08                  # 切换隐藏前置后等待（秒）
TOP_N_VERIFY = 15                         # 进入第二阶段复测的候选数
VERIFY_ROUNDS = 3                         # 第二阶段交叉复测轮数

# 历史评分算法参数
HALF_LIFE_IP_DAYS = 14.0                  # 当前静态 IP 历史半衰期（天）
HALF_LIFE_GLOBAL_DAYS = 21.0              # 跨 IP 整体历史半衰期（天）
PEAK_WEIGHT = 1.4                         # 晚高峰（19:30-23:30）批次权重
NORMAL_WEIGHT = 1.0                       # 非晚高峰批次权重
BAYES_PRIOR_M = 1.5                       # 贝叶斯平滑先验权重（等效测试次数）
FAIL_PENALTY_MS = 400.0                   # 部分丢包折算延迟惩罚
ALL_FAIL_SCORE_MS = 1500.0                # 全超时等效惩罚分
PHASE1_JITTER_FLOOR_MS = 15.0             # 第一阶段单次测速的保守抖动修正

# 最终精选池参数
FINAL_PICK = 8                            # 输出进 nodes 的推荐节点数
MAX_PER_AIRPORT = 3                       # >=3 家机场时，单机场最大席位数
DIVERSITY_SCORE_RATIO = 1.65              # 跨机场多样性兜底质量上限（相对榜首分倍数）
MIN_HISTORY_AVAIL = 0.50                  # 入选精选池的最低历史可用率

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "static_chain_history.db")
EXPORT_YAML_PATH = os.path.join(SCRIPT_DIR, "latest_recommendation.yaml")
# ==============================================

# 强制绕过系统代理，防止请求本地 127.0.0.1 进入 Clash 环路
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
LEADING_FLAGS_RE = re.compile(r"^(?:[\U0001F1E6-\U0001F1FF]{2}|\s)+")

# 避免单机场订阅里把常见地名或线路词误识别为机场名
NON_AIRPORT_TOKENS = {
    "香港", "台湾", "台灣", "澳门", "澳門", "日本", "东京", "大阪", "新加坡", "狮城",
    "美国", "美國", "洛杉矶", "西雅图", "圣何塞", "纽约", "芝加哥", "凤凰城", "俄勒冈", "弗吉尼亚",
    "韩国", "韓國", "首尔", "英国", "英國", "伦敦", "德国", "德國", "法兰克福", "法国", "法國", "巴黎",
    "荷兰", "荷蘭", "意大利", "加拿大", "土耳其", "阿根廷", "印度", "巴西", "尼日利亚", "菲律宾",
    "印尼", "马来西亚", "泰国", "越南", "乌克兰", "埃及", "巴基斯坦", "俄罗斯", "澳大利亚", "澳洲",
    "深港", "沪港", "京港", "沪日", "京日", "苏日", "广日", "川日", "沪美",
    "HK", "TW", "MO", "JP", "SG", "US", "KR", "UK", "GB", "DE", "FR", "IT", "NL", "CA",
    "TR", "AR", "IN", "BR", "NG", "PH", "ID", "MY", "TH", "VN", "UA", "EG", "PK", "RU", "AU",
    "IEPL", "IPLC", "BGP", "GIA", "CN2", "V1", "V2", "V3", "PRO", "VIP", "STD", "LITE",
    "DIRECT", "AUTO", "PROXY", "IPV4", "IPV6", "UDP", "TCP", "TLS", "WS", "GRPC"
}


def api_request(method, path, body=None, timeout=10):
    url = f"{CONTROLLER.rstrip('/')}{path}"
    headers = {}
    if SECRET:
        headers["Authorization"] = f"Bearer {SECRET}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw) if raw else None


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tested_at INTEGER NOT NULL,
            tested_at_iso TEXT NOT NULL,
            static_ip TEXT NOT NULL,
            test_url TEXT NOT NULL,
            is_peak INTEGER NOT NULL,
            candidate_count INTEGER NOT NULL,
            batch_median_ms REAL
        );

        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES runs(id),
            static_ip TEXT NOT NULL,
            airport TEXT NOT NULL,
            node_name TEXT NOT NULL,
            ok_count INTEGER NOT NULL,
            total_count INTEGER NOT NULL,
            avg_ms REAL,
            min_ms REAL,
            max_ms REAL,
            jitter_ms REAL,
            eff_score REAL NOT NULL,
            phase INTEGER NOT NULL,
            rel_score REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_runs_ip_time ON runs(static_ip, tested_at);
        CREATE INDEX IF NOT EXISTS idx_samples_ip_node ON samples(static_ip, node_name);
        CREATE INDEX IF NOT EXISTS idx_samples_node ON samples(node_name);
        CREATE INDEX IF NOT EXISTS idx_samples_airport ON samples(airport);
        CREATE INDEX IF NOT EXISTS idx_samples_run ON samples(run_id);
    """)
    conn.commit()


def is_peak_hour(dt):
    hm = dt.hour * 60 + dt.minute
    return (19 * 60 + 30) <= hm <= (23 * 60 + 30)


def is_non_airport_token(token):
    t = token.strip()
    if not t or len(t) > 24:
        return True
    upper = t.upper()
    if upper in NON_AIRPORT_TOKENS or t in NON_AIRPORT_TOKENS:
        return True
    # 排除纯数字、倍率标签（如 1x / 0.5X / 2倍）与国旗
    if re.fullmatch(r"[\d.]+[xX倍]?", t):
        return True
    if FLAG_RE.search(t):
        return True
    return False


def build_airport_map(node_names, forced_airport=None):
    """为当前订阅的全部节点推断归属机场：支持 --airport 强制指定、KNOWN_AIRPORTS 与 Sub-Store 前缀自动识别。"""
    if forced_airport:
        return {n: forced_airport.strip() for n in node_names}

    known_sorted = sorted(
        [k.strip() for k in KNOWN_AIRPORTS if k and k.strip()],
        key=len,
        reverse=True,
    )

    result = {}
    space_candidates = {}  # node -> (token, flag)
    token_flags = {}       # token -> set of flags
    token_counts = {}      # token -> count

    for name in node_names:
        flag_match = FLAG_RE.search(name)
        node_flag = flag_match.group(0) if flag_match else ""
        stripped = LEADING_FLAGS_RE.sub("", name).strip()

        # 1. 优先匹配 KNOWN_AIRPORTS
        matched_known = None
        for known in known_sorted:
            if name.startswith(known) or stripped.startswith(known):
                matched_known = known
                break
            if re.match(rf"^[\[\【「(]\s*{re.escape(known)}\s*[\]\】」)]", stripped):
                matched_known = known
                break
        if matched_known:
            result[name] = matched_known
            continue

        # 2. 原名称中位于国旗之前的前缀（典型 Sub-Store：机场A 🇭🇰 香港01）
        if flag_match and flag_match.start() > 0:
            before_flag = name[:flag_match.start()].strip()
            before_clean = re.sub(r"^[\[\【「(\s]+|[\]\】」)\s|\-_:：/·]+$", "", before_flag).strip()
            if before_clean and not is_non_airport_token(before_clean):
                result[name] = before_clean
                continue

        # 3. 剥离前导国旗后的括号前缀（如 🇭🇰 [机场A] 香港01 / 🇭🇰 【机场A】香港01）
        m_bracket = re.match(r"^[\[\【「(]([^\]\】」)]{1,24})[\]\】」)]", stripped)
        if m_bracket:
            cand = m_bracket.group(1).strip()
            if not is_non_airport_token(cand):
                result[name] = cand
                continue

        # 4. 剥离前导国旗后的显式分隔符（| ｜ ： : /）
        m_delim = re.match(r"^([^|｜:：/]{1,20}?)\s*[|｜:：/]\s*\S", stripped)
        if m_delim:
            cand = m_delim.group(1).strip()
            if not is_non_airport_token(cand):
                result[name] = cand
                continue

        # 5. 弱分隔符（空格 / - / _）：先收集，稍后按跨国旗复现校验防止误判单机场地名
        m_weak = re.match(r"^([^\s\-_]{1,20})(?:\s+|\s*[-_]\s*)\S", stripped)
        if m_weak:
            cand = m_weak.group(1).strip()
            if not is_non_airport_token(cand):
                space_candidates[name] = (cand, node_flag)
                token_counts[cand] = token_counts.get(cand, 0) + 1
                token_flags.setdefault(cand, set()).add(node_flag)
                continue

        result[name] = DEFAULT_AIRPORT

    # 校验弱分隔符候选：至少跨 2 种国旗，或命中 >=3 个节点才认定为机场前缀
    for name, (cand, _) in space_candidates.items():
        distinct_flags = {f for f in token_flags.get(cand, set()) if f}
        if len(distinct_flags) >= 2 or token_counts.get(cand, 0) >= 3:
            result[name] = cand
        else:
            result[name] = DEFAULT_AIRPORT

    return result


def discover_probe_and_nodes():
    """自动从 Clash Verge API 发现当前生效的静态 IP 探针与可用候选节点。"""
    _, all_proxies_resp = api_request("GET", "/proxies", timeout=8)
    proxies_dict = (all_proxies_resp or {}).get("proxies", {})

    probe_proxy_name = None
    for pname in proxies_dict.keys():
        if pname.startswith(PROBE_PROXY_PREFIX):
            probe_proxy_name = pname
            break

    if not probe_proxy_name:
        raise RuntimeError(
            f"未找到前缀为「{PROBE_PROXY_PREFIX}」的隐藏探针。\n"
            "请确认已更新 ScriptsClash.js 至 v3.2、在 MergeClash.yaml 填好有效静态 IP 并重载订阅。"
        )

    probe_group_info = proxies_dict.get(PROBE_GROUP)
    if not probe_group_info or not isinstance(probe_group_info.get("all"), list):
        raise RuntimeError(f"未找到隐藏策略组「{PROBE_GROUP}」，请确认已重载 v3.2 脚本。")

    static_ip = probe_proxy_name[len(PROBE_PROXY_PREFIX):].strip()
    all_nodes = probe_group_info.get("all", [])
    return static_ip, probe_proxy_name, all_nodes


def test_one_node(probe_proxy_name, node_name):
    group_enc = urllib.parse.quote(PROBE_GROUP, safe="")
    probe_enc = urllib.parse.quote(probe_proxy_name, safe="")

    api_request("PUT", f"/proxies/{group_enc}", {"name": node_name}, timeout=5)
    time.sleep(SWITCH_SETTLE_SEC)

    params = urllib.parse.urlencode({
        "url": TEST_URL,
        "timeout": TIMEOUT_MS,
        "expected": EXPECTED_STATUS,
    })
    try:
        _, result = api_request(
            "GET",
            f"/proxies/{probe_enc}/delay?{params}",
            timeout=(TIMEOUT_MS / 1000.0) + 3.0,
        )
        delay = result.get("delay") if isinstance(result, dict) else None
        return float(delay) if isinstance(delay, (int, float)) and delay > 0 else None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise
        return None
    except (urllib.error.URLError, TimeoutError):
        return None


def calc_single_run_eff_score(ok_delays, total_count, phase):
    ok_count = len(ok_delays)
    if ok_count == 0:
        return None, None, None, None, ALL_FAIL_SCORE_MS
    avg_ms = sum(ok_delays) / ok_count
    min_ms = min(ok_delays)
    max_ms = max(ok_delays)
    jitter_ms = (max_ms - min_ms) if ok_count > 1 else (PHASE1_JITTER_FLOOR_MS if phase == 1 else 0.0)
    fail_rate = (total_count - ok_count) / float(total_count)
    eff_score = avg_ms + 0.5 * jitter_ms + fail_rate * FAIL_PENALTY_MS
    return avg_ms, min_ms, max_ms, jitter_ms, eff_score


def compute_relative_scores(records):
    """计算同批次相对分（0-100，越高越好），用于消除不同静态 IP 基准延迟差异以做跨 IP 统计。"""
    valid_scores = [r["eff_score"] for r in records if r["ok_count"] > 0]
    batch_median = statistics.median(valid_scores) if valid_scores else None

    sorted_indices = sorted(
        range(len(records)),
        key=lambda i: (0 if records[i]["ok_count"] > 0 else 1, records[i]["eff_score"]),
    )
    rank_map = {idx: rank for rank, idx in enumerate(sorted_indices)}
    total_n = max(len(records), 1)

    for idx, rec in enumerate(records):
        if rec["ok_count"] == 0 or batch_median is None:
            rec["rel_score"] = 0.0
            continue
        rank_pct = ((total_n - rank_map[idx]) / float(total_n)) * 100.0
        speed_adv = 50.0 + ((batch_median - rec["eff_score"]) / max(batch_median, 1.0)) * 100.0
        speed_adv = max(0.0, min(100.0, speed_adv))
        avail_ratio = rec["ok_count"] / float(rec["total_count"])
        rec["rel_score"] = round((0.6 * rank_pct + 0.4 * speed_adv) * avail_ratio, 2)

    return batch_median


def save_run_to_db(conn, now_ts, now_iso, static_ip, is_peak, records, batch_median):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO runs (tested_at, tested_at_iso, static_ip, test_url, is_peak, candidate_count, batch_median_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (now_ts, now_iso, static_ip, TEST_URL, 1 if is_peak else 0, len(records), batch_median),
    )
    run_id = cur.lastrowid

    rows = [
        (
            run_id,
            static_ip,
            r["airport"],
            r["node_name"],
            r["ok_count"],
            r["total_count"],
            r["avg_ms"],
            r["min_ms"],
            r["max_ms"],
            r["jitter_ms"],
            r["eff_score"],
            r["phase"],
            r["rel_score"],
        )
        for r in records
    ]
    cur.executemany(
        """
        INSERT INTO samples (
            run_id, static_ip, airport, node_name, ok_count, total_count,
            avg_ms, min_ms, max_ms, jitter_ms, eff_score, phase, rel_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return run_id


def query_ip_history_ranking(conn, static_ip, alive_set, now_ts, current_airport_map=None):
    """计算当前静态 IP 的历史最优榜（时间衰减 + 晚高峰加权 + 贝叶斯平滑）。"""
    rows = conn.execute(
        """
        SELECT s.node_name, s.airport, s.ok_count, s.total_count, s.avg_ms, s.jitter_ms,
               s.eff_score, r.tested_at, r.is_peak
        FROM samples s
        JOIN runs r ON s.run_id = r.id
        WHERE s.static_ip = ?
        ORDER BY r.tested_at ASC
        """,
        (static_ip,),
    ).fetchall()

    grouped = {}
    for node_name, airport, ok_c, tot_c, avg_ms, jitter_ms, eff_score, tested_at, is_peak in rows:
        if alive_set is not None and node_name not in alive_set:
            continue
        age_days = max(0.0, (now_ts - tested_at) / 86400.0)
        decay = 0.5 ** (age_days / HALF_LIFE_IP_DAYS)
        w = decay * (PEAK_WEIGHT if is_peak else NORMAL_WEIGHT)

        entry = grouped.setdefault(node_name, {
            "node_name": node_name,
            "airport": airport,
            "sum_w": 0.0,
            "sum_w_eff": 0.0,
            "sum_w_avail": 0.0,
            "sum_w_avg": 0.0,
            "sum_w_ok": 0.0,
            "runs": 0,
            "last_avg": None,
            "last_eff": eff_score,
        })
        entry["airport"] = (current_airport_map or {}).get(node_name, airport)
        entry["sum_w"] += w
        entry["sum_w_eff"] += w * eff_score
        entry["sum_w_avail"] += w * (ok_c / float(tot_c))
        if avg_ms is not None:
            entry["sum_w_avg"] += w * avg_ms
            entry["sum_w_ok"] += w
        entry["runs"] += 1
        entry["last_avg"] = avg_ms
        entry["last_eff"] = eff_score

    if not grouped:
        return []

    raw_effs = [e["sum_w_eff"] / e["sum_w"] for e in grouped.values() if e["sum_w"] > 0]
    global_prior = statistics.median(raw_effs) if raw_effs else 400.0

    ranking = []
    for e in grouped.values():
        w = e["sum_w"]
        w_eff = e["sum_w_eff"] / w
        w_avail = e["sum_w_avail"] / w
        w_avg = (e["sum_w_avg"] / e["sum_w_ok"]) if e["sum_w_ok"] > 0 else None
        bayes_score = (w * w_eff + BAYES_PRIOR_M * global_prior) / (w + BAYES_PRIOR_M)
        ranking.append({
            "node_name": e["node_name"],
            "airport": e["airport"],
            "history_score": bayes_score,
            "weighted_eff": w_eff,
            "weighted_avg": w_avg,
            "avail": w_avail,
            "runs": e["runs"],
            "is_new": e["runs"] <= 2,
            "last_avg": e["last_avg"],
        })

    ranking.sort(key=lambda x: (0 if x["avail"] >= MIN_HISTORY_AVAIL else 1, x["history_score"]))
    return ranking


def query_global_history_ranking(conn, alive_set, now_ts, current_airport_map=None):
    """计算跨所有静态 IP 的整体最优节点榜与各机场综合表现榜（基于标准化相对分）。"""
    rows = conn.execute(
        """
        SELECT s.node_name, s.airport, s.ok_count, s.total_count, s.rel_score,
               s.static_ip, r.tested_at, r.is_peak
        FROM samples s
        JOIN runs r ON s.run_id = r.id
        ORDER BY r.tested_at ASC
        """
    ).fetchall()

    grouped = {}
    for node_name, airport, ok_c, tot_c, rel_score, static_ip, tested_at, is_peak in rows:
        age_days = max(0.0, (now_ts - tested_at) / 86400.0)
        decay = 0.5 ** (age_days / HALF_LIFE_GLOBAL_DAYS)
        w = decay * (PEAK_WEIGHT if is_peak else NORMAL_WEIGHT)

        entry = grouped.setdefault(node_name, {
            "node_name": node_name,
            "airport": airport,
            "sum_w": 0.0,
            "sum_w_rel": 0.0,
            "sum_w_avail": 0.0,
            "runs": 0,
            "ips": set(),
        })
        entry["airport"] = (current_airport_map or {}).get(node_name, airport)
        entry["sum_w"] += w
        entry["sum_w_rel"] += w * rel_score
        entry["sum_w_avail"] += w * (ok_c / float(tot_c))
        entry["runs"] += 1
        entry["ips"].add(static_ip)

    node_ranking = []
    airport_buckets = {}

    for e in grouped.values():
        w = e["sum_w"]
        w_rel = e["sum_w_rel"] / w
        w_avail = e["sum_w_avail"] / w
        # 贝叶斯平滑向先验 50 分收缩（越高越好）
        global_score = (w * w_rel + BAYES_PRIOR_M * 50.0) / (w + BAYES_PRIOR_M)
        item = {
            "node_name": e["node_name"],
            "airport": e["airport"],
            "global_score": global_score,
            "avail": w_avail,
            "runs": e["runs"],
            "ip_count": len(e["ips"]),
            "alive": (alive_set is None) or (e["node_name"] in alive_set),
        }
        if item["alive"]:
            node_ranking.append(item)
            airport_buckets.setdefault(item["airport"], []).append(item)

    node_ranking.sort(key=lambda x: (-x["global_score"], -x["avail"]))

    airport_summary = []
    for airport, items in airport_buckets.items():
        items_sorted = sorted(items, key=lambda x: -x["global_score"])
        top_slice = items_sorted[:min(5, len(items_sorted))]
        top_avg = sum(i["global_score"] for i in top_slice) / len(top_slice)
        overall_avail = sum(i["avail"] for i in items) / len(items)
        airport_summary.append({
            "airport": airport,
            "node_count": len(items),
            "top5_score": top_avg,
            "avg_avail": overall_avail,
            "best_node": items_sorted[0]["node_name"],
        })

    airport_summary.sort(key=lambda x: (-x["top5_score"], -x["avg_avail"]))
    return node_ranking, airport_summary


def pick_diverse_nodes(ip_ranking):
    """按自适应单机场上限 + 质量兜底挑选最终推荐精选池。"""
    usable = [r for r in ip_ranking if r["avail"] >= MIN_HISTORY_AVAIL]
    if not usable:
        return [], 0

    unique_airports = {r["airport"] for r in usable}
    if len(unique_airports) <= 1:
        effective_cap = FINAL_PICK
    elif len(unique_airports) == 2:
        effective_cap = max(4, math.ceil(FINAL_PICK / 2.0))
    else:
        effective_cap = MAX_PER_AIRPORT

    best_score = usable[0]["history_score"]
    score_ceiling = best_score * DIVERSITY_SCORE_RATIO

    picked = []
    picked_names = set()
    airport_counts = {}

    # 第一轮：在质量护栏内按单机场上限选取，兼顾速度与多机场容灾
    for item in usable:
        if len(picked) >= FINAL_PICK:
            break
        if item["history_score"] > score_ceiling:
            continue
        ap = item["airport"]
        if airport_counts.get(ap, 0) >= effective_cap:
            continue
        picked.append(item)
        picked_names.add(item["node_name"])
        airport_counts[ap] = airport_counts.get(ap, 0) + 1

    # 第二轮：若不足 FINAL_PICK，放开上限从剩余合格节点按排名补齐
    if len(picked) < FINAL_PICK:
        for item in usable:
            if len(picked) >= FINAL_PICK:
                break
            if item["node_name"] in picked_names:
                continue
            picked.append(item)
            picked_names.add(item["node_name"])

    return picked, effective_cap


def export_recommendation_yaml(static_ip, now_iso, picked, effective_cap):
    lines = [
        f"# 生成时间: {now_iso}",
        f"# 目标静态 IP: {static_ip}",
        f"# 单机场上限: {effective_cap}（精选池总数: {len(picked)}）",
        "# 说明: 请人工核对后手动复制到本地 MergeClash.yaml 的 static-proxy 下，不会自动改动原存档。",
        "  nodes:",
    ]
    for item in picked:
        avg_str = f"{item['weighted_avg']:.0f}ms" if item["weighted_avg"] is not None else "N/A"
        tag = "[新] " if item["is_new"] else ""
        lines.append(
            f"    - {json.dumps(item['node_name'], ensure_ascii=False)}"
            f"  # {tag}{item['airport']} | 历史分 {item['history_score']:.1f} | 均延 {avg_str} | 可用 {item['avail']*100:.0f}% ({item['runs']}次)"
        )
    with open(EXPORT_YAML_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_reports(static_ip, now_iso, current_records, ip_ranking, global_ranking, airport_summary, picked, effective_cap):
    if current_records:
        ok_records = [r for r in current_records if r["ok_count"] > 0]
        ok_records.sort(key=lambda x: x["eff_score"])
        print("\n" + "=" * 72)
        print(f"一、本次测速最优 Top 10（静态 IP: {static_ip}）")
        print("=" * 72)
        for idx, r in enumerate(ok_records[:10], 1):
            phase_tag = f"{r['ok_count']}/{r['total_count']}"
            jitter_str = f"{r['jitter_ms']:.0f}ms" if r["jitter_ms"] is not None else "-"
            print(
                f"{idx:>2}. 均延 {r['avg_ms']:>5.1f}ms | 抖动 {jitter_str:<5} | 成功 {phase_tag:<3} "
                f"| [{r['airport']}] {r['node_name']}"
            )

    print("\n" + "=" * 72)
    print(f"二、当前静态 IP 历史最优 Top 15（静态 IP: {static_ip}，仅含当前存活节点）")
    print("=" * 72)
    if not ip_ranking:
        print("暂无该静态 IP 的历史记录。")
    else:
        for idx, item in enumerate(ip_ranking[:15], 1):
            avg_str = f"{item['weighted_avg']:>5.1f}ms" if item["weighted_avg"] is not None else "  N/A "
            new_tag = "[新]" if item["is_new"] else "    "
            print(
                f"{idx:>2}. {new_tag} 历史分 {item['history_score']:>5.1f} | 衰减均延 {avg_str} "
                f"| 可用 {item['avail']*100:>3.0f}% | {item['runs']:>2}次 | [{item['airport']}] {item['node_name']}"
            )

    # 新节点 / 新机场潜力观察区（历史 <=2 次且进入本次前 20%）
    if current_records and ip_ranking:
        ok_sorted = sorted([r for r in current_records if r["ok_count"] > 0], key=lambda x: x["eff_score"])
        top20_cut = max(3, math.ceil(len(ok_sorted) * 0.2))
        top20_names = {r["node_name"] for r in ok_sorted[:top20_cut]}
        new_stars = [item for item in ip_ranking if item["is_new"] and item["node_name"] in top20_names]
        if new_stars:
            print("\n--- 新节点 / 新机场潜力观察区（历史 <=2 次且本次进入前 20%）---")
            for item in new_stars[:8]:
                last_str = f"{item['last_avg']:.1f}ms" if item["last_avg"] is not None else "N/A"
                print(
                    f"  * [新] 本次 {last_str:<7} | 历史分 {item['history_score']:>5.1f} "
                    f"| {item['runs']}次 | [{item['airport']}] {item['node_name']}"
                )

    print("\n" + "=" * 72)
    print("三、跨静态 IP 整体最优 Top 10（相对表现分，满分 100，用于评估通用底座质量）")
    print("=" * 72)
    if not global_ranking:
        print("暂无跨 IP 历史记录。")
    else:
        for idx, item in enumerate(global_ranking[:10], 1):
            print(
                f"{idx:>2}. 综合分 {item['global_score']:>5.1f} | 可用 {item['avail']*100:>3.0f}% "
                f"| 跨 {item['ip_count']} IP / {item['runs']:>2}次 | [{item['airport']}] {item['node_name']}"
            )

    if airport_summary:
        print("\n--- 各机场综合底座表现（按 Top5 节点平均综合分排序）---")
        for idx, ap in enumerate(airport_summary, 1):
            print(
                f"{idx:>2}. {ap['airport']:<12} | Top5 均分 {ap['top5_score']:>5.1f} "
                f"| 整体可用 {ap['avg_avail']*100:>3.0f}% | 存活节点 {ap['node_count']:>3}"
            )

    print("\n" + "=" * 72)
    print(f"四、推荐精选池（单机场上限 {effective_cap}，已同步写入 {os.path.basename(EXPORT_YAML_PATH)}）")
    print("=" * 72)
    if not picked:
        print("暂无可推荐节点。")
    else:
        print("  nodes:")
        for item in picked:
            print(f"    - {json.dumps(item['node_name'], ensure_ascii=False)}")


def main():
    parser = argparse.ArgumentParser(description="Clash 静态链式代理低并发测速与历史评分工具")
    parser.add_argument("--airport", default=None, help="强制指定本次订阅归属的机场名（适合单机场订阅）")
    parser.add_argument("--report-only", action="store_true", help="仅查看历史榜单，不执行新测速")
    parser.add_argument("--ip", default=None, help="配合 --report-only 离线指定要查询的静态 IP（如 1.2.3.4:1080）")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    now_dt = datetime.datetime.now()
    now_ts = int(now_dt.timestamp())
    now_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if args.report_only:
            static_ip = args.ip
            alive_set = None
            airport_map = None
            if not static_ip:
                try:
                    static_ip, _, all_nodes = discover_probe_and_nodes()
                    alive_set = set(all_nodes)
                    airport_map = build_airport_map(all_nodes, args.airport)
                except Exception:
                    row = conn.execute("SELECT static_ip FROM runs ORDER BY tested_at DESC LIMIT 1").fetchone()
                    if not row:
                        print("数据库尚无历史记录，且无法连接 Clash Verge 外部控制。")
                        sys.exit(1)
                    static_ip = row[0]
                    print(f"提示：未连接 Clash Verge，离线展示最近一次测速的静态 IP（{static_ip}）历史榜单。")

            ip_ranking = query_ip_history_ranking(conn, static_ip, alive_set, now_ts, airport_map)
            global_ranking, airport_summary = query_global_history_ranking(conn, alive_set, now_ts, airport_map)
            picked, effective_cap = pick_diverse_nodes(ip_ranking)
            if picked:
                export_recommendation_yaml(static_ip, now_iso, picked, effective_cap)
            print_reports(static_ip, now_iso, [], ip_ranking, global_ranking, airport_summary, picked, effective_cap)
            return

        # 正常测速流程
        try:
            static_ip, probe_proxy_name, all_nodes = discover_probe_and_nodes()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print("鉴权失败：请检查脚本中的 SECRET 是否与 Clash Verge 外部控制一致。")
            else:
                print(f"API 返回异常状态码：{e.code}")
            sys.exit(1)
        except Exception as e:
            print(f"初始化失败：{e}")
            sys.exit(1)

        candidates = [
            n for n in all_nodes
            if (not INCLUDE_KEYWORDS or any(k in n for k in INCLUDE_KEYWORDS))
            and not any(k in n for k in EXCLUDE_KEYWORDS)
        ]
        if not candidates:
            print("没有符合筛选条件的候选节点。")
            sys.exit(1)

        airport_map = build_airport_map(all_nodes, args.airport)
        detected_airports = sorted({airport_map[n] for n in candidates})
        peak = is_peak_hour(now_dt)

        print(f"当前静态 IP：{static_ip} | 时段：{'晚高峰 (1.4x)' if peak else '常规 (1.0x)'}")
        print(f"识别到机场 ({len(detected_airports)})：{', '.join(detected_airports)}")
        print(f"候选节点：{len(candidates)} 个，预计第一阶段耗时约 {int(len(candidates) * (SLEEP_BETWEEN_NODES + 0.5))} 秒\n")
        print("=== 第一阶段：并发=1 全量初筛 ===")

        phase1_results = {}
        for idx, node in enumerate(candidates, 1):
            delay = test_one_node(probe_proxy_name, node)
            phase1_results[node] = delay
            status_str = f"{delay:.0f} ms" if delay is not None else "超时/失败"
            print(f"[{idx:>3}/{len(candidates)}] {status_str:<10} | [{airport_map[node]}] {node}")
            time.sleep(SLEEP_BETWEEN_NODES)

        phase1_ok = [(n, d) for n, d in phase1_results.items() if d is not None]
        phase1_ok.sort(key=lambda x: x[1])
        shortlist = [n for n, _ in phase1_ok[:TOP_N_VERIFY]]

        phase2_samples = {n: [] for n in shortlist}
        if shortlist and VERIFY_ROUNDS > 0:
            print(f"\n=== 第二阶段：Top {len(shortlist)} 节点 {VERIFY_ROUNDS} 轮交叉复测 ===")
            for r in range(1, VERIFY_ROUNDS + 1):
                print(f"--- 第 {r}/{VERIFY_ROUNDS} 轮 ---")
                for node in shortlist:
                    delay = test_one_node(probe_proxy_name, node)
                    phase2_samples[node].append(delay)
                    print(f"  {f'{delay:.0f} ms' if delay is not None else '失败':<8} | [{airport_map[node]}] {node}")
                    time.sleep(SLEEP_BETWEEN_NODES)

        # 整理全部候选节点本批次明细
        records = []
        for node in candidates:
            if node in phase2_samples and VERIFY_ROUNDS > 0:
                raw_list = phase2_samples[node]
                ok_delays = [d for d in raw_list if d is not None]
                total_c = len(raw_list)
                phase = 2
            else:
                d = phase1_results[node]
                ok_delays = [d] if d is not None else []
                total_c = 1
                phase = 1

            avg_ms, min_ms, max_ms, jitter_ms, eff_score = calc_single_run_eff_score(ok_delays, total_c, phase)
            records.append({
                "airport": airport_map[node],
                "node_name": node,
                "ok_count": len(ok_delays),
                "total_count": total_c,
                "avg_ms": avg_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "jitter_ms": jitter_ms,
                "eff_score": eff_score,
                "phase": phase,
                "rel_score": 0.0,
            })

        batch_median = compute_relative_scores(records)
        run_id = save_run_to_db(conn, now_ts, now_iso, static_ip, peak, records, batch_median)
        print(f"\n已写入历史数据库（批次 #{run_id}，路径：{DB_PATH}）")

        alive_set = set(all_nodes)
        ip_ranking = query_ip_history_ranking(conn, static_ip, alive_set, now_ts, airport_map)
        global_ranking, airport_summary = query_global_history_ranking(conn, alive_set, now_ts, airport_map)
        picked, effective_cap = pick_diverse_nodes(ip_ranking)

        if picked:
            export_recommendation_yaml(static_ip, now_iso, picked, effective_cap)

        print_reports(static_ip, now_iso, records, ip_ranking, global_ranking, airport_summary, picked, effective_cap)
    finally:
        conn.close()


if __name__ == "__main__":
    main()