import os
import json
import requests
import time
from datetime import datetime, timedelta

# ================= 配置区域 =================
# 建议使用 DeepSeek (https://www.deepseek.com/) 便宜且好用
API_KEY = os.environ.get("LLM_API_KEY") 
API_BASE_URL = "https://api.deepseek.com" 

# 搜索关键词
TOPICS = "topic:artificial-intelligence OR topic:machine-learning OR topic:quantitative-finance OR topic:agent"
# ===========================================

# 【更新点 1】加载历史记录，防止重复
def load_history():
    if os.path.exists("history.json"):
        with open("history.json", "r", encoding="utf-8") as f:
            return set(json.load(f)) # 用集合(Set)存储，查询更快
    return set()

def save_history(history_set):
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(list(history_set), f) # 转回列表保存

def get_github_repos(period="month", exclude_names=set()):
    """获取 GitHub 项目，并过滤掉已存在的"""
    api_url = "https://api.github.com/search/repositories"
    
    # 【更新点 2】为了保证不重复，我们请求更多的数据(per_page=30)，然后在本地筛选
    if period == "month":
        date_since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        query = f"({TOPICS}) created:>{date_since}"
    else:
        query = f"({TOPICS})"

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": 30  # 获取多一点，方便过滤
    }
    
    print(f"正在搜索 GitHub ({period})...")
    resp = requests.get(api_url, params=params)
    
    if resp.status_code != 200:
        print("GitHub API Error:", resp.text)
        return []
    
    raw_items = resp.json().get("items", [])
    valid_items = []
    
    # 【更新点 3】筛选逻辑
    for item in raw_items:
        if item['full_name'] not in exclude_names:
            valid_items.append(item)
            if len(valid_items) >= 5: # 只需要前5个新的
                break
    
    return valid_items

def analyze_with_ai(repo_data):
    """调用 AI 生成中文解读"""
    print(f"正在分析项目: {repo_data['name']}...")
    
    prompt = f"""
    项目名称: {repo_data['name']}
    项目描述: {repo_data['description']}
    项目地址: {repo_data['html_url']}
    
    请作为一位技术专家，为初学者生成该项目的中文介绍。
    输出必须是纯 JSON 格式，无 markdown 标记。
    字段: title_cn, one_liner, tags(数组), summary, deep_dive(包含 principle, application, opportunity, critical)。
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload)
        content = resp.json()['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"AI 分析失败: {e}")
        return {
            "title_cn": repo_data['name'],
            "one_liner": "AI 暂时休息了，请直接查看原项目。",
            "tags": ["AI"],
            "summary": repo_data['description'],
            "deep_dive": {"principle": "暂无", "application": "暂无", "opportunity": "暂无", "critical": "暂无"}
        }

def main():
    # 1. 读取历史记录
    history_set = load_history()
    
    final_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "trending": [],
        "all_time": []
    }

    # 2. 获取本月新星（带过滤）
    month_repos = get_github_repos("month", history_set)
    for repo in month_repos:
        ai_analysis = analyze_with_ai(repo)
        final_data["trending"].append({"repo_info": repo, "analysis": ai_analysis})
        history_set.add(repo['full_name']) # 加入历史记录
        time.sleep(1) # 休息一下防止API超频

    # 3. 获取历史殿堂（带过滤）
    all_time_repos = get_github_repos("all_time", history_set)
    for repo in all_time_repos:
        ai_analysis = analyze_with_ai(repo)
        final_data["all_time"].append({"repo_info": repo, "analysis": ai_analysis})
        history_set.add(repo['full_name']) # 加入历史记录
        time.sleep(1)

    # 4. 保存显示数据
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    # 5. 【更新点 4】保存新的历史记录
    save_history(history_set)
    print("数据更新完成！历史记录已保存。")

if __name__ == "__main__":
    main()