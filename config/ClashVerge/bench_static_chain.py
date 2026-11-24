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
# v0.1 2026-11-24

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

# 已知机场规范名（优先精准匹配，适合前缀与节点本体无空格/分隔符的情况）
# 示例：KNOWN_AIRPORTS = ["规范名1", "规范名2"]
KNOWN_AIRPORTS = []

# 机场别名映射（旧名 -> 规范名）：解决机场改名/缩写后历史记录自动合并
# 示例：AIRPORT_ALIASES = {
#     "旧机场名": "新机场名",
# }
AIRPORT_ALIASES = {}

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


def canonicalize_airport(name):
    """按 AIRPORT_ALIASES 将机场名映射为规范名，支持多级链式别名。"""
    cur = str(name or "").strip() or DEFAULT_AIRPORT
    seen = set()
    while cur in AIRPORT_ALIASES and cur not in seen:
        seen.add(cur)
        nxt = str(AIRPORT_ALIASES[cur]).strip()
        if not nxt:
            break
        cur = nxt
    return cur


def get_aliases_for_canonical(canonical_airport):
    """返回映射到指定规范机场名的全部旧别名集合（用于核心节点名剥离）。"""
    aliases = set()
    for old_name in AIRPORT_ALIASES.keys():
        if canonicalize_airport(old_name) == canonical_airport:
            aliases.add(str(old_name).strip())
    return aliases


def extract_core_name(node_name, raw_airport, canonical_airport):
    """剥离机场前缀与国旗，提取稳定的核心节点名，兼容改前缀与单机场/聚合订阅互切。"""
    s = LEADING_FLAGS_RE.sub("", node_name).strip()

    tokens = set()
    for t in (raw_airport, canonical_airport, *get_aliases_for_canonical(canonical_airport)):
        t_clean = str(t or "").strip()
        if t_clean and t_clean != DEFAULT_AIRPORT:
            tokens.add(t_clean)

    # 按长度降序尝试剥离前缀（避免短名抢先截断长名，如“良心云”截断“良心云机场”）
    for tok in sorted(tokens, key=len, reverse=True):
        esc = re.escape(tok)
        m_bracket = re.match(rf"^[\[\【「(]\s*{esc}\s*[\]\】」)][\s|｜:：/·\-_]*", s)
        if m_bracket:
            s = s[m_bracket.end():].strip()
            break
        m_bare = re.match(rf"^{esc}[\s|｜:：/·\-_]*", s)
        if m_bare:
            s = s[m_bare.end():].strip()
            break

    s = FLAG_RE.sub("", s)
    s = re.sub(r"\s*·\s*", "·", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else node_name.strip()


def make_node_key(node_name, raw_airport, canonical_airport=None):
    """构造跨前缀变化与单/聚合订阅通用的稳定节点主键：规范机场名::国旗::核心节点名。"""
    canon = canonical_airport if canonical_airport is not None else canonicalize_airport(raw_airport)
    flag_match = FLAG_RE.search(node_name)
    flag = flag_match.group(0) if flag_match else ""
    core = extract_core_name(node_name, raw_airport, canon)
    return f"{canon}::{flag}::{core}"


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
    if re.fullmatch(r"[\d.]+[xX倍]?", t):
        return True
    if FLAG_RE.search(t):
        return True
    return False


def build_airport_map(node_names, forced_airport=None):
    """为当前订阅节点推断规范机场名：支持 --airport、KNOWN_AIRPORTS/别名表与 Sub-Store 前缀识别。"""
    if forced_airport:
        canon = canonicalize_airport(forced_airport)
        return {n: canon for n in node_names}

    known_pool = set()
    for k in KNOWN_AIRPORTS:
        if k and str(k).strip():
            known_pool.add(str(k).strip())
    for k, v in AIRPORT_ALIASES.items():
        if k and str(k).strip():
            known_pool.add(str(k).strip())
        if v and str(v).strip():
            known_pool.add(str(v).strip())
    known_sorted = sorted(known_pool, key=len, reverse=True)

    raw_result = {}
    space_candidates = {}
    token_flags = {}
    token_counts = {}

    for name in node_names:
        flag_match = FLAG_RE.search(name)
        node_flag = flag_match.group(0) if flag_match else ""
        stripped = LEADING_FLAGS_RE.sub("", name).strip()

        # 1. 优先匹配已知机场名 / 别名（按长度降序）
        matched_known = None
        for known in known_sorted:
            esc = re.escape(known)
            if (
                re.match(rf"^[\[\【「(]\s*{esc}\s*[\]\】」)]", name)
                or re.match(rf"^[\[\【「(]\s*{esc}\s*[\]\】」)]", stripped)
                or name.startswith(known)
                or stripped.startswith(known)
            ):
                matched_known = known
                break
        if matched_known:
            raw_result[name] = matched_known
            continue

        # 2. 优先匹配括号前缀（同时兼容 [悦通] 悦·🇭🇰 香港01 与 🇭🇰 [悦通] 悦·香港01）
        m_bracket = (
            re.match(r"^[\[\【「(]([^\]\】」)]{1,24})[\]\】」)]", name.strip())
            or re.match(r"^[\[\【「(]([^\]\】」)]{1,24})[\]\】」)]", stripped)
        )
        if m_bracket:
            cand = m_bracket.group(1).strip()
            if not is_non_airport_token(cand):
                raw_result[name] = cand
                continue

        # 3. 位于国旗之前的前缀（典型 Sub-Store：机场A 🇭🇰 香港01）
        if flag_match and flag_match.start() > 0:
            before_flag = name[:flag_match.start()].strip()
            before_clean = re.sub(r"^[\[\【「(\s]+|[\]\】」)\s|\-_:：/·]+$", "", before_flag).strip()
            if before_clean and not is_non_airport_token(before_clean):
                raw_result[name] = before_clean
                continue

        # 4. 剥离前导国旗后的显式分隔符（| ｜ ： : /）
        m_delim = re.match(r"^([^|｜:：/]{1,20}?)\s*[|｜:：/]\s*\S", stripped)
        if m_delim:
            cand = m_delim.group(1).strip()
            if not is_non_airport_token(cand):
                raw_result[name] = cand
                continue

        # 5. 弱分隔符（空格 / - / _）：结合跨国旗复现校验防止误判单机场地名
        m_weak = re.match(r"^([^\s\-_]{1,20})(?:\s+|\s*[-_]\s*)\S", stripped)
        if m_weak:
            cand = m_weak.group(1).strip()
            if not is_non_airport_token(cand):
                space_candidates[name] = (cand, node_flag)
                token_counts[cand] = token_counts.get(cand, 0) + 1
                token_flags.setdefault(cand, set()).add(node_flag)
                continue

        raw_result[name] = DEFAULT_AIRPORT

    for name, (cand, _) in space_candidates.items():
        distinct_flags = {f for f in token_flags.get(cand, set()) if f}
        if len(distinct_flags) >= 2 or token_counts.get(cand, 0) >= 3:
            raw_result[name] = cand
        else:
            raw_result[name] = DEFAULT_AIRPORT

    return {n: canonicalize_airport(ap) for n, ap in raw_result.items()}


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
            "请确认已更新 Scripts.js 至 v3.2、在 Merge.yaml 填好有效静态 IP 并重载订阅。"
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


def query_ip_history_ranking(conn, static_ip, live_key_to_node, now_ts):
    """按归一化主键计算当前静态 IP 的历史最优榜（时间衰减 + 晚高峰加权 + 贝叶斯平滑）。"""
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
    for node_name, raw_airport, ok_c, tot_c, avg_ms, jitter_ms, eff_score, tested_at, is_peak in rows:
        canon_ap = canonicalize_airport(raw_airport)
        node_key = make_node_key(node_name, raw_airport, canon_ap)
        if live_key_to_node is not None and node_key not in live_key_to_node:
            continue

        display_name = live_key_to_node[node_key] if live_key_to_node is not None else node_name
        age_days = max(0.0, (now_ts - tested_at) / 86400.0)
        decay = 0.5 ** (age_days / HALF_LIFE_IP_DAYS)
        w = decay * (PEAK_WEIGHT if is_peak else NORMAL_WEIGHT)

        entry = grouped.setdefault(node_key, {
            "node_key": node_key,
            "node_name": display_name,
            "airport": canon_ap,
            "sum_w": 0.0,
            "sum_w_eff": 0.0,
            "sum_w_avail": 0.0,
            "sum_w_avg": 0.0,
            "sum_w_ok": 0.0,
            "runs": 0,
            "last_avg": None,
            "last_eff": eff_score,
        })
        entry["node_name"] = display_name
        entry["airport"] = canon_ap
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
            "node_key": e["node_key"],
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


def query_global_history_ranking(conn, live_key_to_node, now_ts):
    """按归一化主键计算跨静态 IP 的整体最优节点榜与各机场综合表现榜。"""
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
    for node_name, raw_airport, ok_c, tot_c, rel_score, static_ip, tested_at, is_peak in rows:
        canon_ap = canonicalize_airport(raw_airport)
        node_key = make_node_key(node_name, raw_airport, canon_ap)
        if live_key_to_node is not None and node_key not in live_key_to_node:
            continue

        display_name = live_key_to_node[node_key] if live_key_to_node is not None else node_name
        age_days = max(0.0, (now_ts - tested_at) / 86400.0)
        decay = 0.5 ** (age_days / HALF_LIFE_GLOBAL_DAYS)
        w = decay * (PEAK_WEIGHT if is_peak else NORMAL_WEIGHT)

        entry = grouped.setdefault(node_key, {
            "node_key": node_key,
            "node_name": display_name,
            "airport": canon_ap,
            "sum_w": 0.0,
            "sum_w_rel": 0.0,
            "sum_w_avail": 0.0,
            "runs": 0,
            "ips": set(),
        })
        entry["node_name"] = display_name
        entry["airport"] = canon_ap
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
        global_score = (w * w_rel + BAYES_PRIOR_M * 50.0) / (w + BAYES_PRIOR_M)
        item = {
            "node_key": e["node_key"],
            "node_name": e["node_name"],
            "airport": e["airport"],
            "global_score": global_score,
            "avail": w_avail,
            "runs": e["runs"],
            "ip_count": len(e["ips"]),
        }
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
    picked_keys = set()
    airport_counts = {}

    for item in usable:
        if len(picked) >= FINAL_PICK:
            break
        if item["history_score"] > score_ceiling:
            continue
        ap = item["airport"]
        if airport_counts.get(ap, 0) >= effective_cap:
            continue
        picked.append(item)
        picked_keys.add(item["node_key"])
        airport_counts[ap] = airport_counts.get(ap, 0) + 1

    if len(picked) < FINAL_PICK:
        for item in usable:
            if len(picked) >= FINAL_PICK:
                break
            if item["node_key"] in picked_keys:
                continue
            picked.append(item)
            picked_keys.add(item["node_key"])

    return picked, effective_cap


def handle_list_airports(conn):
    rows = conn.execute(
        """
        SELECT airport, COUNT(*) AS sample_cnt, COUNT(DISTINCT node_name) AS node_cnt, MAX(node_name)
        FROM samples
        GROUP BY airport
        ORDER BY sample_cnt DESC
        """
    ).fetchall()
    if not rows:
        print("历史数据库暂无任何记录。")
        return
    print("数据库内已记录机场清单：")
    for ap, sample_cnt, node_cnt, example_node in rows:
        canon = canonicalize_airport(ap)
        alias_note = f" -> 映射为 [{canon}]" if canon != ap else ""
        print(f"  - {ap}{alias_note} | 样本 {sample_cnt} 条 | 节点 {node_cnt} 个 | 示例: {example_node}")


def handle_merge_airport(conn, old_ap, new_ap, replace_pair=None, keep_node_name=False, auto_yes=False):
    """合并历史库中的机场名，并可选同步修正 node_name 中的旧前缀文本。"""
    old_ap = old_ap.strip()
    new_ap = new_ap.strip()
    rows = conn.execute(
        "SELECT id, node_name FROM samples WHERE airport = ?",
        (old_ap,),
    ).fetchall()
    if not rows:
        print(f"未在数据库中找到机场名为「{old_ap}」的历史记录。")
        return

    old_sub, new_sub = (replace_pair[0], replace_pair[1]) if replace_pair else (old_ap, new_ap)
    do_replace = (not keep_node_name) and (old_sub != "") and (old_sub != new_sub)

    preview_map = {}
    for _, node_name in rows:
        if node_name in preview_map:
            continue
        new_node_name = node_name.replace(old_sub, new_sub, 1) if do_replace else node_name
        preview_map[node_name] = new_node_name
        if len(preview_map) >= 8:
            break

    print(f"即将合并历史记录：{len(rows)} 条样本")
    print(f"  机场名：{old_ap}  -->  {new_ap}")
    if do_replace:
        print(f"  节点名局部替换（首次命中）：{old_sub!r}  -->  {new_sub!r}")
    else:
        print("  节点名：保持不变")
    print("  变更示例：")
    for before, after in preview_map.items():
        mark = "（不变）" if before == after else f" --> {after}"
        print(f"    {before}{mark}")

    if not auto_yes:
        ans = input("\n确认写入数据库？[y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消，未修改数据库。")
            return

    cur = conn.cursor()
    if do_replace:
        updates = [
            (new_ap, node_name.replace(old_sub, new_sub, 1), row_id)
            for row_id, node_name in rows
        ]
        cur.executemany("UPDATE samples SET airport = ?, node_name = ? WHERE id = ?", updates)
    else:
        cur.execute("UPDATE samples SET airport = ? WHERE airport = ?", (new_ap, old_ap))
    conn.commit()
    print(f"合并完成，已更新 {len(rows)} 条历史样本。")


def export_recommendation_yaml(static_ip, now_iso, picked, effective_cap):
    lines = [
        f"# 生成时间: {now_iso}",
        f"# 目标静态 IP: {static_ip}",
        f"# 单机场上限: {effective_cap}（精选池总数: {len(picked)}）",
        "# 说明: 请人工核对后手动复制到本地 Merge.yaml 的 static-proxy 下，不会自动改动原存档。",
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

    if current_records and ip_ranking:
        ok_sorted = sorted([r for r in current_records if r["ok_count"] > 0], key=lambda x: x["eff_score"])
        top20_cut = max(3, math.ceil(len(ok_sorted) * 0.2))
        top20_keys = {r["node_key"] for r in ok_sorted[:top20_cut]}
        new_stars = [item for item in ip_ranking if item["is_new"] and item["node_key"] in top20_keys]
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
    parser.add_argument("--list-airports", action="store_true", help="列出历史数据库中所有机场名与示例节点")
    parser.add_argument(
        "--merge-airport",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="将历史库中的旧机场名合并至新机场名（默认同时把节点名中的 OLD 替换为 NEW）",
    )
    parser.add_argument(
        "--replace-text",
        nargs=2,
        metavar=("OLD_TEXT", "NEW_TEXT"),
        help="配合 --merge-airport 使用，自定义节点名中的替换片段（如处理 悦通悦 -> [悦通] 悦）",
    )
    parser.add_argument(
        "--keep-node-name",
        action="store_true",
        help="配合 --merge-airport 使用，仅改机场归属列，不改节点名文本",
    )
    parser.add_argument("--yes", action="store_true", help="配合 --merge-airport 跳过交互确认")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    now_dt = datetime.datetime.now()
    now_ts = int(now_dt.timestamp())
    now_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if args.list_airports:
            handle_list_airports(conn)
            return

        if args.merge_airport:
            handle_merge_airport(
                conn,
                args.merge_airport[0],
                args.merge_airport[1],
                replace_pair=args.replace_text,
                keep_node_name=args.keep_node_name,
                auto_yes=args.yes,
            )
            return

        if args.report_only:
            static_ip = args.ip
            live_key_to_node = None
            if not static_ip:
                try:
                    static_ip, _, all_nodes = discover_probe_and_nodes()
                    airport_map = build_airport_map(all_nodes, args.airport)
                    live_key_to_node = {
                        make_node_key(n, airport_map[n], airport_map[n]): n
                        for n in all_nodes
                    }
                except Exception:
                    row = conn.execute("SELECT static_ip FROM runs ORDER BY tested_at DESC LIMIT 1").fetchone()
                    if not row:
                        print("数据库尚无历史记录，且无法连接 Clash Verge 外部控制。")
                        sys.exit(1)
                    static_ip = row[0]
                    print(f"提示：未连接 Clash Verge，离线展示最近一次测速的静态 IP（{static_ip}）历史榜单。")

            ip_ranking = query_ip_history_ranking(conn, static_ip, live_key_to_node, now_ts)
            global_ranking, airport_summary = query_global_history_ranking(conn, live_key_to_node, now_ts)
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
        live_key_to_node = {
            make_node_key(n, airport_map[n], airport_map[n]): n
            for n in all_nodes
        }
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
            ap = airport_map[node]
            records.append({
                "airport": ap,
                "node_name": node,
                "node_key": make_node_key(node, ap, ap),
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

        ip_ranking = query_ip_history_ranking(conn, static_ip, live_key_to_node, now_ts)
        global_ranking, airport_summary = query_global_history_ranking(conn, live_key_to_node, now_ts)
        picked, effective_cap = pick_diverse_nodes(ip_ranking)

        if picked:
            export_recommendation_yaml(static_ip, now_iso, picked, effective_cap)

        print_reports(static_ip, now_iso, records, ip_ranking, global_ranking, airport_summary, picked, effective_cap)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
