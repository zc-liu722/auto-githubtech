import os
import json
import requests
import time
from datetime import datetime, timedelta

# ================= 配置区域 =================
API_KEY = os.environ.get("LLM_API_KEY") 
API_BASE_URL = "https://api.deepseek.com" # 或 https://api.openai.com/v1

# 搜索关键词：使用更精准的 GitHub 语法
TOPICS = "ai or agent or quant"
# ===========================================

def load_history():
    if os.path.exists("history.json"):
        with open("history.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_history(history_set):
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(list(history_set), f)

def get_github_repos(period="month", exclude_names=set()):
    api_url = "https://api.github.com/search/repositories"
    
    if period == "month":
        date_since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        # 搜索逻辑：(AI 或 量化 或 智能体) 且 创建于近30天 且 Star > 5
        query = f"{TOPICS} created:>{date_since} stars:>5"
    else:
        # 历史排行：(AI 或 量化 或 智能体) 且 Star > 500
        query = f"{TOPICS} stars:>500"

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": 100 # 大幅增加初筛数量
    }
    
    print(f"正在尝试广域搜索: {query}")
    
    try:
        resp = requests.get(api_url, params=params, timeout=20)
        if resp.status_code != 200:
            print(f"GitHub 报错: {resp.status_code}")
            return []
        
        raw_items = resp.json().get("items", [])
        print(f"原始匹配总数: {len(raw_items)}")
        
        valid_items = []
        for item in raw_items:
            # 过滤掉已经看过的项目
            if item['full_name'] not in exclude_names:
                valid_items.append(item)
                # 网页每一栏我们要 5 个，所以这里抓 5 个就停
                if len(valid_items) >= 5:
                    break
        return valid_items
    except Exception as e:
        print(f"网络异常: {e}")
        return []

def analyze_with_ai(repo_data):
    """完整修复版：包含 headers 和 payload 逻辑"""
    if not API_KEY:
        print("错误: 未检测到 API_KEY")
        return None

    prompt = f"""
    项目: {repo_data['full_name']}
    描述: {repo_data['description']}
    要求: 以技术专家身份为小白写中文简介。专业术语保留英文加中文括号。
    格式: 严格 JSON。包含 title_cn, one_liner, tags(3个), summary, deep_dive(principle, application, opportunity, critical)。
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat", # 或 gpt-4o-mini
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
        content = resp.json()['choices'][0]['message']['content']
        # 清洗 Markdown 格式
        clean_content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_content)
    except Exception as e:
        print(f"AI 解析失败 ({repo_data['name']}): {e}")
        return None

def main():
    history_set = load_history()
    final_data = {"date": datetime.now().strftime("%Y-%m-%d"), "trending": [], "all_time": []}

    # 1. 获取本月热门
    month_repos = get_github_repos("month", history_set)
    for repo in month_repos:
        analysis = analyze_with_ai(repo)
        if analysis:
            final_data["trending"].append({"repo_info": repo, "analysis": analysis})
            history_set.add(repo['full_name'])
        time.sleep(1)

    # 2. 获取历史殿堂
    all_time_repos = get_github_repos("all_time", history_set)
    for repo in all_time_repos:
        analysis = analyze_with_ai(repo)
        if analysis:
            # 【修正点】这里改为存入 all_time 列表
            final_data["all_time"].append({"repo_info": repo, "analysis": analysis})
            history_set.add(repo['full_name'])
        time.sleep(1)

    # 3. 保存文件
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    save_history(history_set)
    print(f"更新成功！今日抓取 {len(final_data['trending']) + len(final_data['all_time'])} 个项目。")

if __name__ == "__main__":
    main()
