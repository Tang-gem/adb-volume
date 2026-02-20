import re
import requests
import json
import time
import random
import hashlib
import urllib
import pyperclip
from datetime import datetime
import os
from dataclasses import dataclass, field
import sys

# ====== 关键参数（可随时修改） ======
BV_IDS = [
    "BV1TeZMBLEiM",
    "BV1fJcczHEmG"
]  # 需要爬取的BV号列表（支持5个）
MIN_PRICE = 900  # 价格筛选下限（元）
CHECK_INTERVAL = (1, 2)  # 轮询间隔秒（随机）
MAX_PRICE_DURATION = 8  # 最高价有效时长（秒）
CLEAR_SCREEN = False  # 是否每轮清屏（True/False），False仅更新状态行
SOUND_ENABLE = True  # 是否启用声音提示

# 正则表达式，?为任意字符任意长度
PATTERN = re.compile(r'王者荣耀.*我的小马糕今天.*块，复制链接来我的市集出售，马年上分大吉！')

@dataclass
class VideoMonitor:
    """单个视频监控状态类"""
    bv_id: str
    oid: str = ""
    title: str = "未识别"
    start_time: str = ""
    last_max_price: float = 0.0
    last_max_price_time: float = 0.0
    last_clip: str = ""
    processed_comment_ids: set = field(default_factory=set)
    last_comment_count: int = 0
    price_remaining: str = "无"
    status: str = "未开始"

# 全局监控实例字典
video_monitors = {}
global_status = ""

def play_alert_sound():
    """播放系统提示音（跨平台兼容）- 修改为Windows调节音量的提示音"""
    if not SOUND_ENABLE:
        return
    
    try:
        # Windows系统 - 使用调节音量的经典提示音（SystemAsterisk）
        if os.name == 'nt':
            import winsound
            # 调用系统预设的音效：SystemAsterisk（调节音量的提示音）
            # 可选的系统音效：SystemExclamation/SystemHand/SystemQuestion/SystemAsterisk
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        # macOS/Linux系统（保持原有逻辑不变）
        else:
            # 使用系统内置的音频播放命令
            import subprocess
            # 尝试多种音频播放方式，确保兼容性
            try:
                # macOS
                subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=True, capture_output=True)
            except:
                try:
                    # Linux
                    subprocess.run(['aplay', '/usr/share/sounds/alsa/Front_Center.wav'], check=True, capture_output=True)
                except:
                    # 通用方案 - 打印ASCII响铃字符
                    print('\a', end='', flush=True)
                    # 连续响铃3次
                    for _ in range(2):
                        time.sleep(0.2)
                        print('\a', end='', flush=True)
    except Exception as e:
        # 声音播放失败不影响主程序运行
        print_error(f"播放提示音失败：{e}")

# 以下函数均保持不变，省略重复代码...
def clear_terminal():
    """清屏（跨平台）"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_Header():
    """获取请求头"""
    try:
        with open('bili_cookie.txt','r') as f:
            cookie = f.read().strip()
        header = {
            "Cookie": cookie,
            "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'
        }
        return header
    except FileNotFoundError:
        print_error("未找到bili_cookie.txt文件")
        raise
    except Exception as e:
        print_error(f"获取请求头失败：{e}")
        raise

def get_current_time():
    """获取格式化的当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_status(msg, is_important=False):
    """打印全局状态信息（控制刷屏）"""
    global global_status
    global_status = f"[{get_current_time()}] {msg}"
    if is_important:
        # 重要信息单独一行显示，非重要信息仅更新状态行
        print(f"\033[36m{global_status}\033[0m")
    else:
        # 覆盖当前行，不换行
        print(f"\r{global_status.ljust(80)}", end="", flush=True)

def print_error(msg):
    """打印错误信息"""
    print(f"\033[31m[{get_current_time()}] 错误：{msg}\033[0m")  # 红色显示错误

def print_success(msg):
    """打印成功信息"""
    print(f"\n\033[32m[{get_current_time()}] ✅ {msg}\033[0m")  # 绿色显示成功

def print_alert(msg):
    """打印告警信息（新高价）"""
    print(f"\n{'='*60}")
    print(f"\033[1;33m[{get_current_time()}] 🚨 {msg}\033[0m")  # 黄色加粗
    print(f"{'='*60}\n")

def init_video_monitor(bv_id):
    """初始化单个视频监控实例"""
    print_status(f"正在初始化视频 {bv_id} 基本信息...")
    try:
        resp = requests.get(f"https://www.bilibili.com/video/{bv_id}/", headers=get_Header(), timeout=10)
        resp.raise_for_status()
        
        # 提取OID
        obj_oid = re.compile(f'"aid":(?P<id>.*?),"bvid":"{bv_id}"')
        oid_match = obj_oid.search(resp.text)
        if not oid_match:
            raise ValueError("未能提取到视频OID")
        oid = oid_match.group('id')
        
        # 提取标题
        obj_title = re.compile(r'<title data-vue-meta="true">(?P<title>.*?)</title>')
        title_match = obj_title.search(resp.text)
        title = title_match.group('title') if title_match else "未识别"
        
        # 创建监控实例
        monitor = VideoMonitor(
            bv_id=bv_id,
            oid=oid,
            title=title,
            start_time=get_current_time()
        )
        video_monitors[bv_id] = monitor
        
        print_success(f"视频 {bv_id} 信息获取成功 - 标题：{title[:20]}...")
        return monitor
    except Exception as e:
        print_error(f"初始化视频 {bv_id} 失败：{e}")
        raise

def md5(code):
    """生成MD5哈希值"""
    try:
        MD5 = hashlib.md5()
        MD5.update(code.encode('utf-8'))
        return MD5.hexdigest()
    except Exception as e:
        print_error(f"MD5加密失败：{e}")
        raise

def get_latest_comments(monitor):
    """获取单个视频最新的10条评论"""
    print_status(f"正在获取视频 {monitor.bv_id} 最新评论...")
    try:
        mode = 2
        plat = 1
        type = 1
        web_location = 1315875
        wts = int(time.time())
        pagination_str = '{"offset":""}'
        
        # 构造参数并生成w_rid
        code = (
            f"mode={mode}&oid={monitor.oid}&pagination_str={urllib.parse.quote(pagination_str)}"
            f"&plat={plat}&seek_rpid=&type={type}&web_location={web_location}&wts={wts}"
            + 'ea1db124af3c7062474693fa704f4ff8'
        )
        w_rid = md5(code)
        
        # 构造请求URL
        url = (
            f"https://api.bilibili.com/x/v2/reply/wbi/main?oid={monitor.oid}&type={type}&mode={mode}"
            f"&pagination_str={urllib.parse.quote(pagination_str, safe=':')}&plat=1&seek_rpid="
            f"&web_location=1315875&w_rid={w_rid}&wts={wts}"
        )
        
        # 发送请求
        resp = requests.get(url, headers=get_Header(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # 提取评论
        comments = data['data']['replies'][:10] if data['data']['replies'] else []
        monitor.last_comment_count = len(comments)
        print_status(f"视频 {monitor.bv_id} 成功获取 {len(comments)} 条最新评论")
        return comments
    except Exception as e:
        print_error(f"获取视频 {monitor.bv_id} 评论失败：{e}")
        return []

def extract_price(text):
    """从评论中提取价格"""
    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*块', text)
    if match:
        price = float(match.group(1))
        return price
    return None

def check_price_validity(monitor):
    """检查单个视频当前最高价是否仍在有效期内"""
    if monitor.last_max_price_time == 0:
        monitor.price_remaining = "无"
        return False
    elapsed = time.time() - monitor.last_max_price_time
    remaining = MAX_PRICE_DURATION - elapsed
    if remaining > 0:
        monitor.price_remaining = f"{remaining:.1f}秒"
        return True
    else:
        monitor.price_remaining = "已过期"
        return False

def print_summary():
    """打印所有视频的汇总信息"""
    if CLEAR_SCREEN:
        clear_terminal()
    
    # 构建汇总信息
    summary = f"\n【多视频监控汇总】{'='*40}\n"
    summary += f"监控时间：{get_current_time()}\n"
    summary += f"价格筛选下限：{MIN_PRICE} 元 | 最高价有效期：{MAX_PRICE_DURATION} 秒 | 轮询间隔：{CHECK_INTERVAL[0]}-{CHECK_INTERVAL[1]} 秒 | 声音提示：{'开启' if SOUND_ENABLE else '关闭'}\n"
    summary += "-" * 60 + "\n"
    
    # 逐个视频信息
    for bv_id, monitor in video_monitors.items():
        summary += (
            f"BV号：{bv_id} | 标题：{monitor.title[:25]:<25} | "
            f"最新评论数：{monitor.last_comment_count:2d} | "
            f"最高价：{monitor.last_max_price if monitor.last_max_price > 0 else '无':>6} | "
            f"有效期：{monitor.price_remaining:<8} | "
            f"状态：{monitor.status[:20]}\n"
        )
    
    summary += "-" * 60 + "\n"
    summary += f"全局状态：{global_status}\n"
    summary += f"按 Ctrl+C 终止程序\n"
    
    # 清屏后打印汇总（仅在CLEAR_SCREEN=True时清屏）
    if CLEAR_SCREEN:
        print(summary)
    else:
        # 仅更新状态行，不刷屏
        pass

def process_video_comments(monitor):
    """处理单个视频的评论"""
    # 1. 获取最新评论
    comments = get_latest_comments(monitor)
    
    # 2. 筛选符合条件的评论
    filtered = []
    for c in comments:
        comment_id = c.get("rpid")
        
        # 跳过已处理的评论
        if comment_id in monitor.processed_comment_ids:
            continue
        
        # 标记为已处理
        monitor.processed_comment_ids.add(comment_id)
        
        content = c["content"]["message"]
        
        # 匹配正则表达式
        if not PATTERN.search(content):
            continue
        
        # 提取价格
        price = extract_price(content)
        if not price:
            continue
        
        # 价格筛选
        if price <= MIN_PRICE:
            continue
        
        # 符合所有条件
        filtered.append((price, content, comment_id))
    
    # 3. 处理筛选结果
    if filtered:
        # 按价格降序排序
        filtered.sort(reverse=True, key=lambda x: x[0])
        max_price, max_content, max_comment_id = filtered[0]
        
        # 检查当前最高价是否有效，且新价格是否更高
        price_valid = check_price_validity(monitor)
        
        if not price_valid and max_price > monitor.last_max_price:
            # 更新最高价状态
            monitor.last_max_price = max_price
            monitor.last_max_price_time = time.time()
            monitor.last_clip = max_content
            
            # 复制到剪贴板
            pyperclip.copy(max_content)
            
            # 播放提示音
            play_alert_sound()
            
            # 打印新高价提示
            print_alert(f"视频 {monitor.bv_id} 发现新高价！{max_price} 元（已复制到剪贴板）")
        
        # 更新状态
        monitor.status = f"找到 {len(filtered)} 条符合条件评论，最高价：{max_price} 元"
        print_status(f"视频 {monitor.bv_id} {monitor.status}", is_important=True)
    else:
        # 更新状态
        monitor.status = "未找到符合条件的评论"
        print_status(f"视频 {monitor.bv_id} {monitor.status}")
        
        # 清理过期的已处理评论ID（避免集合过大）
        if len(monitor.processed_comment_ids) > 100:
            monitor.processed_comment_ids = set(list(monitor.processed_comment_ids)[-50:])
    
    # 4. 检查并重置过期的最高价
    if monitor.last_max_price > 0 and not check_price_validity(monitor):
        monitor.last_max_price = 0
        monitor.last_max_price_time = 0
        monitor.last_clip = ""
        monitor.status = "最高价已过期，重置状态"
        print_status(f"视频 {monitor.bv_id} {monitor.status}", is_important=True)

if __name__ == "__main__":
    try:
        # 初始化所有视频监控实例
        print_status("开始初始化所有视频监控实例...", is_important=True)
        for bv_id in BV_IDS:
            if bv_id.strip():  # 跳过空值
                init_video_monitor(bv_id)
        
        # 打印初始汇总
        print_summary()
        
        # 打印监控信息
        print(f"\n【监控规则】")
        print(f"- 监控视频数量：{len(video_monitors)} 个")
        print(f"- 价格筛选下限：{MIN_PRICE} 元")
        print(f"- 最高价有效期：{MAX_PRICE_DURATION} 秒")
        print(f"- 轮询间隔：{CHECK_INTERVAL[0]}-{CHECK_INTERVAL[1]} 秒")
        print(f"- 声音提示：{'开启' if SOUND_ENABLE else '关闭'}")
        print(f"- 按 Ctrl+C 终止程序\n")
        print("-"*60 + "\n")
        
        # 主监控循环
        while True:
            # 逐个处理每个视频
            for bv_id, monitor in video_monitors.items():
                process_video_comments(monitor)
                # 每个视频之间增加短暂随机延迟，避免请求过于集中
                time.sleep(random.uniform(0.1, 0.3))
            
            # 打印汇总信息
            print_summary()
            
            # 等待下一轮检查
            sleep_time = random.uniform(*CHECK_INTERVAL)
            print_status(f"本轮监控完成，等待 {sleep_time:.2f} 秒后开始下一轮...")
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print(f"\n\n[{get_current_time()}] 用户手动终止程序")
    except Exception as e:
        print_error(f"\n程序异常终止：{e}")