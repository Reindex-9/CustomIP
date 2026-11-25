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
# v0.2 2026-11-26  适配 Scripts v3.3 多静态 IP、达标全量导出与双端格式化输出

# ================= 基础配置区 =================
CONTROLLER = "http://127.0.0.1:9097"      # Clash Verge 外部控制地址
SECRET = "set-your-secret"                # 外部控制 Secret（无密码留空 ""）

PROBE_GROUP = "🧪 测速前置"
PROBE_PROXY_PREFIX = "🧪 静态测速探针|"

TEST_URL = "https://www.gstatic.com/generate_204"
EXPECTED_STATUS = "204"
TIMEOUT_MS = 5000                         # 单次测速超时（毫秒）

# 测速候选初筛（留空 [] 测全量；可按需在此排除高倍率专线，如 EXCLUDE_KEYWORDS = ["3x", "5x", "IEPL"]）
INCLUDE_KEYWORDS = []
EXCLUDE_KEYWORDS = []

# 已知机场规范名（优先精准匹配，适合前缀与节点本体无空格/分隔符的情况）
KNOWN_AIRPORTS = []

# 机场别名映射（旧名 -> 规范名）：机场改名或换缩写后自动合并历史记录
AIRPORT_ALIASES = {}

DEFAULT_AIRPORT = "未标注机场"             # 单机场订阅且未传 --airport 时的默认归属名

# 测速节奏与两阶段复测参数（严格并发=1，降低静态 IP 风控风险）
SLEEP_BETWEEN_NODES = 0.30                # 每次探测后休眠（秒）
SWITCH_SETTLE_SEC = 0.08                  # 切换隐藏前置后等待（秒）
TOP_N_VERIFY = 15                         # 第一阶段胜出后进入第二阶段复测的候选数
VERIFY_ROUNDS = 3                         # 第二阶段交叉复测轮数

# 历史评分算法参数（单 IP 历史分单位近似毫秒，越低越好）
HALF_LIFE_IP_DAYS = 14.0                  # 单静态 IP 历史半衰期（天）
HALF_LIFE_GLOBAL_DAYS = 21.0              # 跨 IP 通用底座历史半衰期（天）
PEAK_WEIGHT = 1.4                         # 晚高峰（19:30-23:30）批次权重
NORMAL_WEIGHT = 1.0                       # 非晚高峰批次权重
BAYES_PRIOR_M = 1.0                       # 贝叶斯平滑先验权重（防止新节点仅测 1 次偶然偏快直接霸榜）
FAIL_PENALTY_MS = 400.0                   # 部分丢包折算延迟惩罚
ALL_FAIL_SCORE_MS = 1500.0                # 全超时等效惩罚分
PHASE1_JITTER_FLOOR_MS = 15.0             # 第一阶段单次测速的保守抖动修正

# 达标筛选与前端排序参数（导出 nodes 本身不设总上限，由客户端按前 15 个截断显示）
# 达标条件：历史可用率 >= 70% 且 历史分 <= min(650, max(榜首分 * 1.30, 榜首分 + 60))
MIN_HISTORY_AVAIL = 0.70                  # 达标最低历史可用率
QUALIFY_SCORE_RATIO = 1.30                # 相对榜首分的倍数宽容上限（适配欧美等高延迟 IP）
QUALIFY_SCORE_ADD_MS = 60.0               # 相对榜首分的绝对宽容值（适配港日等低延迟 IP）
QUALIFY_MAX_SCORE_MS = 650.0              # 达标历史分绝对封顶（防整体网络劣化时矮子里拔将军）
DISPLAY_TOP_LIMIT = 15                    # 客户端面板单组显示上限（用于规划前 15 位的跨机场均衡）
DISPLAY_SOFT_CAP_PER_AIRPORT = 5          # >=3 家机场时，前 15 展示位中单机场软上限（超出部分排至 16+ 位，不丢弃）

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "static_chain_history.db")
EXPORT_YAML_PATH = os.path.join(SCRIPT_DIR, "latest_recommendation.yaml")
EXPORT_JS_PATH = os.path.join(SCRIPT_DIR, "latest_recommendation_flclash.js")
# ==============================================

# 强制绕过系统代理，防止访问本地 127.0.0.1 控制接口进入 Clash 环路
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
LEADING_FLAGS_RE = re.compile(r"^(?:[\U0001F1E6-\U0001F1FF]{2}|\s)+")

# 地名与常见线路词白名单，防止单机场订阅把地区词误识别为机场前缀
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
    """剥离机场前缀与国旗，提取稳定核心名，使节点在换前缀或单/聚合订阅互切时能延续历史记录。"""
    s = LEADING_FLAGS_RE.sub("", node_name).strip()

    tokens = set()
    for t in (raw_airport, canonical_airport, *get_aliases_for_canonical(canonical_airport)):
        t_clean = str(t or "").strip()
        if t_clean and t_clean != DEFAULT_AIRPORT:
            tokens.add(t_clean)

    # 按长度降序剥离，防止短词抢先截断长词（如「XX」截断「XX机场」）
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
    """构造稳定节点主键（规范机场名::国旗::核心节点名），用于历史评分归并。"""
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
    """推断每个节点的规范机场名：优先级为 --airport > 已知机场/别名表 > 括号/国旗前/分隔符前缀。"""
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

        # 1. 优先匹配已知机场名或别名
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

        # 2. 括号前缀（兼容 "[机场] 🇭🇰 香港01" 与 "🇭🇰 [机场] 香港01"）
        m_bracket = (
            re.match(r"^[\[\【「(]([^\]\】」)]{1,24})[\]\】」)]", name.strip())
            or re.match(r"^[\[\【「(]([^\]\】」)]{1,24})[\]\】」)]", stripped)
        )
        if m_bracket:
            cand = m_bracket.group(1).strip()
            if not is_non_airport_token(cand):
                raw_result[name] = cand
                continue

        # 3. 国旗之前的前缀（典型 Sub-Store：机场A 🇭🇰 香港01）
        if flag_match and flag_match.start() > 0:
            before_flag = name[:flag_match.start()].strip()
            before_clean = re.sub(r"^[\[\【「(\s]+|[\]\】」)\s|\-_:：/·]+$", "", before_flag).strip()
            if before_clean and not is_non_airport_token(before_clean):
                raw_result[name] = before_clean
                continue

        # 4. 显式分隔符前缀（| ｜ : ： /）
        m_delim = re.match(r"^([^|｜:：/]{1,20}?)\s*[|｜:：/]\s*\S", stripped)
        if m_delim:
            cand = m_delim.group(1).strip()
            if not is_non_airport_token(cand):
                raw_result[name] = cand
                continue

        # 5. 弱分隔符（空格 / - / _）：后续通过跨国旗复现校验，防止误判地名
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


def discover_probes_and_nodes():
    """自动发现全部生效的静态 IP 隐藏探针与候选节点（兼容 v3.3「名称|键」及 v3.2 单键格式）。"""
    _, all_proxies_resp = api_request("GET", "/proxies", timeout=8)
    proxies_dict = (all_proxies_resp or {}).get("proxies", {})

    probes = []
    for pname in proxies_dict.keys():
        if not pname.startswith(PROBE_PROXY_PREFIX):
            continue
        rest = pname[len(PROBE_PROXY_PREFIX):].strip()
        if "|" in rest:
            display_name, static_ip = rest.split("|", 1)
            display_name = display_name.strip() or static_ip.strip()
            static_ip = static_ip.strip()
        else:
            display_name = rest
            static_ip = rest
        probes.append({
            "name": display_name,
            "static_ip": static_ip,
            "proxy_name": pname,
        })

    if not probes:
        raise RuntimeError(
            f"未找到前缀为「{PROBE_PROXY_PREFIX}」的隐藏探针。\n"
            "请确认已更新 Scripts.js 至 v3.3、在 Merge.yaml 填好有效静态 IP 并重载订阅。"
        )

    probe_group_info = proxies_dict.get(PROBE_GROUP)
    if not probe_group_info or not isinstance(probe_group_info.get("all"), list):
        raise RuntimeError(f"未找到隐藏策略组「{PROBE_GROUP}」，请确认已重载 Scripts v3.3。")

    all_nodes = probe_group_info.get("all", [])
    return probes, all_nodes


def match_probe_target(probes, target):
    """按显示名、存储键或子串唯一匹配目标静态 IP 探针。"""
    t = target.strip()
    exact = [p for p in probes if p["name"] == t or p["static_ip"] == t]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise RuntimeError(f"目标「{t}」命中多个探针，请使用更精确的名称或 IP:端口。")

    fuzzy = [p for p in probes if t.lower() in p["name"].lower() or t.lower() in p["static_ip"].lower()]
    if len(fuzzy) == 1:
        return fuzzy[0]
    if len(fuzzy) > 1:
        opts = ", ".join(f"{p['name']} ({p['static_ip']})" for p in fuzzy)
        raise RuntimeError(f"目标「{t}」匹配不唯一：{opts}")
    opts = ", ".join(f"{p['name']} ({p['static_ip']})" for p in probes)
    raise RuntimeError(f"未找到目标「{t}」。当前可用静态 IP：{opts}")

def choose_probes_for_benchmark(probes, target_arg, run_all):
    """解析本次要测速的静态 IP 列表：多探针且未指定目标时在交互终端提供菜单。"""
    if run_all:
        return probes
    if target_arg:
        return [match_probe_target(probes, target_arg)]
    if len(probes) == 1:
        return probes

    print("检测到多个静态 IP 探针：")
    for idx, p in enumerate(probes, 1):
        print(f"  {idx}. {p['name']} ({p['static_ip']})")
    print("  回车 / a. 全部顺序测速")
    print("  0 / q / Ctrl+C. 取消")

    if not sys.stdin.isatty():
        print("\n非交互环境请通过 --target <名称或IP> 指定单个目标，或传 --all 顺序全测。")
        sys.exit(1)

    try:
        ans = input("\n请选择要测速的编号（直接回车全测，0/q 或 Ctrl+C 取消）: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        sys.exit(0)

    if not ans or ans in ("a", "all"):
        return probes
    if ans in ("0", "q", "quit", "exit"):
        print("已取消。")
        sys.exit(0)
    if ans.isdigit() and 1 <= int(ans) <= len(probes):
        return [probes[int(ans) - 1]]
    print("无效选择。")
    sys.exit(1)

def test_one_node(probe_proxy_name, node_name):
    """将隐藏前置组切换至目标机场节点，再探测「机场节点 -> 静态 IP -> TEST_URL」端到端延迟。"""
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
    """单次综合等效延迟分 = 均延 + 0.5*抖动 + 丢包率*惩罚分（全超时返回固定高惩罚分）。"""
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
    """计算同批次相对分（0-100，60% 排名分 + 40% 相对中位速度优势），消除不同静态 IP 的物理基准延迟差异。"""
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


def get_last_tested_iso(conn, static_ip):
    row = conn.execute(
        "SELECT tested_at_iso FROM runs WHERE static_ip = ? ORDER BY tested_at DESC LIMIT 1",
        (static_ip,),
    ).fetchone()
    return row[0] if row else None


def query_ip_history_ranking(conn, static_ip, live_key_to_node, now_ts):
    """按归一化主键计算单静态 IP 历史榜（指数时间衰减 + 晚高峰加权 + 贝叶斯平滑）。"""
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
        # 样本量少时向全局中位数收缩，减少偶发快/慢测速带来的排名震荡
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

    # 排序优先级：达标可用率组 > 有存活记录组 > 全超时组；组内按历史分升序
    ranking.sort(key=lambda x: (0 if x["avail"] >= MIN_HISTORY_AVAIL else (1 if x["avail"] > 0 else 2), x["history_score"], -x["avail"]))
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


def select_recommended_nodes(ip_ranking):
    """
    达标全量筛选（不设输出总上限）+ 无达标机场最优兜底 + 前 15 展示位多机场均衡排序：
    1. 达标池：保留全部满足可用率与分数界限的节点
    2. 机场兜底：无达标节点但非全超时（avail > 0）的机场保留最优 1 个；全超时机场跳过
    3. 排序布局：[前 15 均衡展示区] -> [其余达标节点] -> [机场兜底节点]
       同一机场内全程严格按历史分从优到劣排列，保证切回单机场时截取前 15 个即为该机场最优
    """
    alive = [r for r in ip_ranking if r["avail"] > 0]
    if not alive:
        return [], {
            "best_score": None,
            "threshold": None,
            "qualified_count": 0,
            "fallback_count": 0,
            "soft_cap": 0,
        }

    # 阶段 1：计算动态达标阈值并收集全部达标节点
    avail_ok = [r for r in alive if r["avail"] >= MIN_HISTORY_AVAIL]
    if avail_ok:
        best_score = min(r["history_score"] for r in avail_ok)
        threshold = min(
            QUALIFY_MAX_SCORE_MS,
            max(best_score * QUALIFY_SCORE_RATIO, best_score + QUALIFY_SCORE_ADD_MS),
        )
        qualified = [
            {**r, "pick_status": "qualified"}
            for r in avail_ok
            if r["history_score"] <= threshold
        ]
    else:
        best_score = None
        threshold = None
        qualified = []

    qualified_airports = {r["airport"] for r in qualified}

    # 阶段 2：为无达标节点但存在存活记录的机场挑选唯一最优兜底节点
    alive_by_airport = {}
    for r in alive:
        alive_by_airport.setdefault(r["airport"], []).append(r)

    fallbacks = []
    for ap, items in alive_by_airport.items():
        if ap in qualified_airports:
            continue
        items_sorted = sorted(
            items,
            key=lambda x: (0 if x["avail"] >= MIN_HISTORY_AVAIL else 1, x["history_score"], -x["avail"]),
        )
        fallbacks.append({**items_sorted[0], "pick_status": "fallback"})

    fallbacks.sort(
        key=lambda x: (0 if x["avail"] >= MIN_HISTORY_AVAIL else 1, x["history_score"], -x["avail"])
    )

    # 阶段 3：仅对前 DISPLAY_TOP_LIMIT 位施加单机场软上限以平衡聚合展示，超出节点排至后段而非丢弃
    if len(qualified_airports) <= 1:
        soft_cap = DISPLAY_TOP_LIMIT
    elif len(qualified_airports) == 2:
        soft_cap = max(8, math.ceil(DISPLAY_TOP_LIMIT / 2.0))
    else:
        soft_cap = DISPLAY_SOFT_CAP_PER_AIRPORT

    front_picked = []
    front_keys = set()
    ap_counts = {}

    for item in qualified:
        if len(front_picked) >= DISPLAY_TOP_LIMIT:
            break
        ap = item["airport"]
        if ap_counts.get(ap, 0) >= soft_cap:
            continue
        front_picked.append(item)
        front_keys.add(item["node_key"])
        ap_counts[ap] = ap_counts.get(ap, 0) + 1

    remaining_qualified = [item for item in qualified if item["node_key"] not in front_keys]
    ordered = front_picked + remaining_qualified + fallbacks

    meta = {
        "best_score": best_score,
        "threshold": threshold,
        "qualified_count": len(qualified),
        "fallback_count": len(fallbacks),
        "soft_cap": soft_cap,
    }
    return ordered, meta


def handle_list_targets(conn):
    print("当前 Clash Verge 生效探针：")
    try:
        probes, _ = discover_probes_and_nodes()
        for idx, p in enumerate(probes, 1):
            last_iso = get_last_tested_iso(conn, p["static_ip"]) or "尚无测速记录"
            print(f"  {idx}. {p['name']} | 存储键: {p['static_ip']} | 最近测速: {last_iso}")
    except Exception as e:
        print(f"  （未连接 Clash Verge 或无探针：{e}）")

    rows = conn.execute(
        """
        SELECT static_ip, COUNT(*) AS run_cnt, MAX(tested_at_iso) AS last_time
        FROM runs
        GROUP BY static_ip
        ORDER BY MAX(tested_at) DESC
        """
    ).fetchall()
    print("\n历史数据库已记录静态 IP：")
    if not rows:
        print("  暂无记录。")
    else:
        for ip, run_cnt, last_time in rows:
            print(f"  - {ip} | 测速 {run_cnt} 次 | 最近: {last_time}")


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
    """合并历史库中的旧机场名，并可选同步替换 node_name 中的旧前缀片段。"""
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


def format_node_comment(item):
    avg_str = f"{item['weighted_avg']:.0f}ms" if item["weighted_avg"] is not None else "N/A"
    tags = []
    if item.get("pick_status") == "fallback":
        tags.append("兜底")
    if item.get("is_new"):
        tags.append("新")
    tag_str = f"[{'/'.join(tags)}] " if tags else ""
    return (
        f"{tag_str}{item['airport']} | 历史分 {item['history_score']:.1f} "
        f"| 均延 {avg_str} | 可用 {item['avail']*100:.0f}% ({item['runs']}次)"
    )


def export_recommendations(export_entries, now_iso):
    """同步导出 Merge.yaml 片段（YAML）与 FlClash 片段（JS，含全量与按机场拆分数组）。"""
    valid_entries = [e for e in export_entries if e["picked"]]
    if not valid_entries:
        return

    # 1. 导出 Merge.yaml 片段
    yaml_lines = [
        f"# 导出时间: {now_iso}",
        f"# 说明: 按静态 IP 分段导出全部达标节点及单机场兜底节点（客户端每组自动截取命中的前 {DISPLAY_TOP_LIMIT} 个显示）。",
        "# 用法: 将对应静态 IP 下的 nodes: 块复制到 Merge.yaml 对应条目中即可。",
        "",
    ]
    for entry in valid_entries:
        meta = entry["meta"]
        picked = entry["picked"]
        thr_str = f"<= {meta['threshold']:.1f}ms (可用率 >= {MIN_HISTORY_AVAIL*100:.0f}%)" if meta["threshold"] is not None else "无达标（仅兜底）"
        yaml_lines.append("# " + "=" * 68)
        yaml_lines.append(f"# 静态 IP: {entry['name']} ({entry['static_ip']}) | 最近测速: {entry['last_iso']}")
        yaml_lines.append(
            f"# 达标界限: {thr_str} | 共 {len(picked)} 个（达标 {meta['qualified_count']} + 机场兜底 {meta['fallback_count']}）"
        )
        yaml_lines.append("# " + "=" * 68)
        yaml_lines.append("    nodes:")
        for idx, item in enumerate(picked):
            if idx == DISPLAY_TOP_LIMIT:
                yaml_lines.append(f"      # --- 以下为第 {DISPLAY_TOP_LIMIT + 1}+ 位备选（切回单机场订阅时自动前移补位） ---")
            yaml_lines.append(
                f"      - {json.dumps(item['node_name'], ensure_ascii=False)}"
                f"  # {format_node_comment(item)}"
            )
        yaml_lines.append("")

    with open(EXPORT_YAML_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))

    # 2. 导出 FlClash JS 片段（提供完整列表与按机场拆分列表，消除 YAML/JS 手工转换）
    js_lines = [
        f"// 导出时间: {now_iso}",
        "// 说明: 供 FlClash 直接粘贴至 Scripts.js 顶部 STATIC_CONFIG.staticProxies 对应条目的 nodes 字段。",
        f"// 客户端会自动过滤当前订阅存活节点并最多显示前 {DISPLAY_TOP_LIMIT} 个。",
        "",
    ]
    for entry in valid_entries:
        meta = entry["meta"]
        picked = entry["picked"]
        thr_str = f"<= {meta['threshold']:.1f}ms" if meta["threshold"] is not None else "仅兜底"
        js_lines.append("// " + "=" * 68)
        js_lines.append(f"// 静态 IP: {entry['name']} ({entry['static_ip']}) | 最近测速: {entry['last_iso']}")
        js_lines.append(
            f"// 达标界限: {thr_str} | 共 {len(picked)} 个（达标 {meta['qualified_count']} + 机场兜底 {meta['fallback_count']}）"
        )
        js_lines.append("// " + "=" * 68)
        js_lines.append("// 【完整列表（适合聚合订阅或配合 currentAirport 使用）】")
        js_lines.append("nodes: [")
        for idx, item in enumerate(picked):
            if idx == DISPLAY_TOP_LIMIT:
                js_lines.append(f"  // --- 以下为第 {DISPLAY_TOP_LIMIT + 1}+ 位备选（单机场自动补位） ---")
            comma = "," if idx < len(picked) - 1 else ""
            js_lines.append(
                f"  {json.dumps(item['node_name'], ensure_ascii=False)}{comma}"
                f"  // {format_node_comment(item)}"
            )
        js_lines.append("],")

        by_airport = {}
        for item in picked:
            by_airport.setdefault(item["airport"], []).append(item)

        if len(by_airport) > 1 or (len(by_airport) == 1 and DEFAULT_AIRPORT not in by_airport):
            js_lines.append("")
            js_lines.append("// 【按机场拆分（适合 FlClash 单机场订阅按需复制）】")
            for ap, ap_items in by_airport.items():
                js_lines.append(f"// 机场: {ap}（共 {len(ap_items)} 个，已按优劣排序）")
                js_lines.append("nodes: [")
                for idx, item in enumerate(ap_items):
                    comma = "," if idx < len(ap_items) - 1 else ""
                    js_lines.append(
                        f"  {json.dumps(item['node_name'], ensure_ascii=False)}{comma}"
                        f"  // {format_node_comment(item)}"
                    )
                js_lines.append("],")
        js_lines.append("")

    with open(EXPORT_JS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(js_lines))


def print_single_ip_report(target_name, static_ip, current_records, ip_ranking, picked, meta):
    label = f"{target_name} ({static_ip})" if target_name != static_ip else static_ip

    if current_records:
        ok_records = [r for r in current_records if r["ok_count"] > 0]
        ok_records.sort(key=lambda x: x["eff_score"])
        print("\n" + "=" * 74)
        print(f"一、本次测速最优 Top 10（{label}）")
        print("=" * 74)
        for idx, r in enumerate(ok_records[:10], 1):
            phase_tag = f"{r['ok_count']}/{r['total_count']}"
            jitter_str = f"{r['jitter_ms']:.0f}ms" if r["jitter_ms"] is not None else "-"
            print(
                f"{idx:>2}. 均延 {r['avg_ms']:>5.1f}ms | 抖动 {jitter_str:<5} | 成功 {phase_tag:<3} "
                f"| [{r['airport']}] {r['node_name']}"
            )

    thr_desc = (
        f"历史分 <= {meta['threshold']:.1f}ms 且可用率 >= {MIN_HISTORY_AVAIL*100:.0f}%"
        if meta["threshold"] is not None
        else "无达标节点（启用机场兜底）"
    )
    print("\n" + "=" * 74)
    print(f"二、当前静态 IP 历史最优 Top 15（{label}）")
    print(f"    达标界限：{thr_desc}")
    print("=" * 74)

    picked_status = {item["node_key"]: item["pick_status"] for item in picked}
    if not ip_ranking:
        print("暂无该静态 IP 的历史记录。")
    else:
        for idx, item in enumerate(ip_ranking[:15], 1):
            avg_str = f"{item['weighted_avg']:>5.1f}ms" if item["weighted_avg"] is not None else "  N/A "
            st = picked_status.get(item["node_key"])
            if st == "qualified":
                badge = "[达标]"
            elif st == "fallback":
                badge = "[兜底]"
            else:
                badge = "      "
            new_tag = "*" if item["is_new"] else " "
            print(
                f"{idx:>2}. {badge}{new_tag} 历史分 {item['history_score']:>5.1f} | 衰减均延 {avg_str} "
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

    print("\n" + "-" * 74)
    if not picked:
        print(f"推荐输出（{label}）：无可用节点（全部历史超时）。")
    else:
        print(
            f"推荐输出（{label}）：共导出 {len(picked)} 个节点"
            f"（达标 {meta['qualified_count']} + 机场兜底 {meta['fallback_count']}，"
            f"客户端面板自动显示命中前 {DISPLAY_TOP_LIMIT} 个）"
        )
        for idx, item in enumerate(picked[:DISPLAY_TOP_LIMIT], 1):
            tag = "[兜底] " if item["pick_status"] == "fallback" else ""
            print(f"  {idx:>2}. {tag}[{item['airport']}] {item['node_name']} ({item['history_score']:.1f})")
        if len(picked) > DISPLAY_TOP_LIMIT:
            print(f"  ... 其余 {len(picked) - DISPLAY_TOP_LIMIT} 个备选节点已完整写入导出文件。")


def print_global_report(global_ranking, airport_summary):
    print("\n" + "=" * 74)
    print("三、跨静态 IP 整体最优 Top 10（相对表现分，满分 100，用于评估通用底座质量）")
    print("=" * 74)
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


def run_benchmark_for_probe(conn, probe, candidates, airport_map, now_dt, now_ts, now_iso):
    """对单个静态 IP 执行两阶段串行测速（全量初筛 + Top N 交叉复测）并落库。"""
    static_ip = probe["static_ip"]
    probe_proxy_name = probe["proxy_name"]
    detected_airports = sorted({airport_map[n] for n in candidates})
    peak = is_peak_hour(now_dt)

    print("\n" + "#" * 74)
    print(f"开始测速：{probe['name']} ({static_ip}) | 时段：{'晚高峰 (1.4x)' if peak else '常规 (1.0x)'}")
    print(f"识别到机场 ({len(detected_airports)})：{', '.join(detected_airports)}")
    print(f"候选节点：{len(candidates)} 个，预计第一阶段耗时约 {int(len(candidates) * (SLEEP_BETWEEN_NODES + 0.5))} 秒")
    print("#" * 74)
    print("\n=== 第一阶段：并发=1 全量初筛 ===")

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

    # 交叉轮测而非单节点连测，降低瞬时波动对单个节点的偏向
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
    return records


def main():
    parser = argparse.ArgumentParser(description="Clash 多静态 IP 链式代理低并发测速与历史评分工具")
    parser.add_argument("--target", default=None, help="指定目标静态 IP（填 Merge.yaml 中的 name 或 IP:端口）")
    parser.add_argument("--ip", default=None, help="--target 的别名（兼容旧用法）")
    parser.add_argument("--all", action="store_true", help="对当前全部静态 IP 探针串行轮测（或在 --report-only 下查看全部）")
    parser.add_argument("--airport", default=None, help="强制指定本次订阅归属的机场名（适合单机场订阅）")
    parser.add_argument("--report-only", action="store_true", help="仅查看历史榜单并重新导出推荐文件，不执行新测速")
    parser.add_argument("--list-targets", action="store_true", help="列出当前生效探针与历史库内全部静态 IP")
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
        help="配合 --merge-airport 使用，自定义节点名中的替换片段",
    )
    parser.add_argument(
        "--keep-node-name",
        action="store_true",
        help="配合 --merge-airport 使用，仅改机场归属列，不改节点名文本",
    )
    parser.add_argument("--yes", action="store_true", help="配合 --merge-airport 跳过交互确认")
    args = parser.parse_args()

    target_arg = args.target or args.ip

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    now_dt = datetime.datetime.now()
    now_ts = int(now_dt.timestamp())
    now_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if args.list_targets:
            handle_list_targets(conn)
            return

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

        # 仅出榜与刷新导出模式（支持连接 Clash Verge 过滤当前存活节点，也支持离线读库）
        if args.report_only:
            live_key_to_node = None
            report_targets = []
            try:
                probes, all_nodes = discover_probes_and_nodes()
                airport_map = build_airport_map(all_nodes, args.airport)
                live_key_to_node = {
                    make_node_key(n, airport_map[n], airport_map[n]): n
                    for n in all_nodes
                }
                if target_arg:
                    try:
                        p = match_probe_target(probes, target_arg)
                        report_targets = [{"name": p["name"], "static_ip": p["static_ip"]}]
                    except RuntimeError:
                        # 允许查询数据库中存在但当前未启用的历史静态 IP
                        report_targets = [{"name": target_arg, "static_ip": target_arg}]
                else:
                    report_targets = [{"name": p["name"], "static_ip": p["static_ip"]} for p in probes]
            except Exception:
                if target_arg:
                    report_targets = [{"name": target_arg, "static_ip": target_arg}]
                elif args.all:
                    rows = conn.execute(
                        "SELECT static_ip FROM runs GROUP BY static_ip ORDER BY MAX(tested_at) DESC"
                    ).fetchall()
                    report_targets = [{"name": r[0], "static_ip": r[0]} for r in rows]
                else:
                    row = conn.execute("SELECT static_ip FROM runs ORDER BY tested_at DESC LIMIT 1").fetchone()
                    if row:
                        report_targets = [{"name": row[0], "static_ip": row[0]}]
                if not report_targets:
                    print("数据库尚无历史记录，且无法连接 Clash Verge 外部控制。")
                    sys.exit(1)
                print("提示：未连接 Clash Verge，以下为离线历史榜单。")

            export_entries = []
            for t in report_targets:
                ip_ranking = query_ip_history_ranking(conn, t["static_ip"], live_key_to_node, now_ts)
                picked, meta = select_recommended_nodes(ip_ranking)
                last_iso = get_last_tested_iso(conn, t["static_ip"]) or "无记录"
                print_single_ip_report(t["name"], t["static_ip"], [], ip_ranking, picked, meta)
                export_entries.append({
                    "name": t["name"],
                    "static_ip": t["static_ip"],
                    "last_iso": last_iso,
                    "picked": picked,
                    "meta": meta,
                })

            global_ranking, airport_summary = query_global_history_ranking(conn, live_key_to_node, now_ts)
            print_global_report(global_ranking, airport_summary)
            export_recommendations(export_entries, now_iso)
            if any(e["picked"] for e in export_entries):
                print(f"\n已更新导出文件：\n  - YAML (Merge): {EXPORT_YAML_PATH}\n  - JS (FlClash): {EXPORT_JS_PATH}")
            return

        # 正常测速流程
        try:
            all_probes, all_nodes = discover_probes_and_nodes()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print("鉴权失败：请检查脚本中的 SECRET 是否与 Clash Verge 外部控制一致。")
            else:
                print(f"API 返回异常状态码：{e.code}")
            sys.exit(1)
        except Exception as e:
            print(f"初始化失败：{e}")
            sys.exit(1)

        try:
            selected_probes = choose_probes_for_benchmark(all_probes, target_arg, args.all)
        except Exception as e:
            print(f"目标选择失败：{e}")
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

        # 串行轮测所选静态 IP（因共用同一个 🧪 测速前置 组，不可多进程并发执行）
        tested_records_by_ip = {}
        for probe in selected_probes:
            run_dt = datetime.datetime.now()
            run_ts = int(run_dt.timestamp())
            run_iso = run_dt.strftime("%Y-%m-%d %H:%M:%S")
            records = run_benchmark_for_probe(conn, probe, candidates, airport_map, run_dt, run_ts, run_iso)
            tested_records_by_ip[probe["static_ip"]] = records

        report_ts = int(datetime.datetime.now().timestamp())
        report_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        selected_ip_set = {p["static_ip"] for p in selected_probes}
        for probe in selected_probes:
            ip_ranking = query_ip_history_ranking(conn, probe["static_ip"], live_key_to_node, report_ts)
            picked, meta = select_recommended_nodes(ip_ranking)
            print_single_ip_report(
                probe["name"],
                probe["static_ip"],
                tested_records_by_ip.get(probe["static_ip"], []),
                ip_ranking,
                picked,
                meta,
            )

        global_ranking, airport_summary = query_global_history_ranking(conn, live_key_to_node, report_ts)
        print_global_report(global_ranking, airport_summary)

        # 汇集当前全部生效静态 IP 的历史推荐统一导出，避免单测某一个 IP 时覆盖其它 IP 的导出段落
        export_entries = []
        for probe in all_probes:
            ip_ranking = query_ip_history_ranking(conn, probe["static_ip"], live_key_to_node, report_ts)
            if not ip_ranking and probe["static_ip"] not in selected_ip_set:
                continue
            picked, meta = select_recommended_nodes(ip_ranking)
            last_iso = get_last_tested_iso(conn, probe["static_ip"]) or report_iso
            export_entries.append({
                "name": probe["name"],
                "static_ip": probe["static_ip"],
                "last_iso": last_iso,
                "picked": picked,
                "meta": meta,
            })

        export_recommendations(export_entries, report_iso)
        if any(e["picked"] for e in export_entries):
            print(f"\n已更新导出文件：\n  - YAML (Merge): {EXPORT_YAML_PATH}\n  - JS (FlClash): {EXPORT_JS_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
