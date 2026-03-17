"""
群体智能 Agent 角色生成器
生成 50 个 Agent 的个性化 profile，用于 OASIS 模拟投票

5 种角色 (权重):
- Fan (10%): 5 agents - 球迷视角，关注情感和主场氛围
- Analyst (30%): 15 agents - 数据分析师，关注统计和战术
- Media (15%): 8 agents - 媒体评论员，关注叙事和趋势
- Insider (25%): 12 agents - 内部人士，关注阵容伤病和教练战术
- Neutral (20%): 10 agents - 中立观察者，综合多方信息

18 轮模拟流程:
R1-3: 知识注入（接收比赛数据）
R4-6: 观点表达（各角色基于自身视角发表预测）
R7-12: 辩论阶段（交叉讨论、挑战和修正）
R13-15: 投票阶段（正式投票）
R16-18: 总结阶段（共识分析、信心评估）
"""

import logging
import random
from ...config import Config
from ...models.football_models import AgentRole

logger = logging.getLogger('mirofish.football.agents')


# Agent 个性化模板
ROLE_TEMPLATES = {
    AgentRole.FAN: {
        'personality_traits': [
            'passionate', 'emotional', 'loyal', 'optimistic',
            'superstitious', 'enthusiastic', 'biased', 'vocal',
        ],
        'knowledge_focus': [
            'team morale', 'fan atmosphere', 'home advantage',
            'derby significance', 'historical rivalries', 'player popularity',
        ],
        'bias_description': '倾向于高估主队表现和主场优势',
        'analysis_style': '基于情感和直觉的判断，强调球队精神和士气',
        'system_prompt_template': (
            "You are a passionate football fan with deep emotional connection to the game. "
            "You tend to value intangible factors like team spirit, crowd atmosphere, and momentum. "
            "Your analysis is based on gut feeling supported by match-watching experience. "
            "Personality: {traits}. Focus area: {focus}."
        ),
    },
    AgentRole.ANALYST: {
        'personality_traits': [
            'methodical', 'data-driven', 'objective', 'precise',
            'cautious', 'thorough', 'statistical', 'rational',
        ],
        'knowledge_focus': [
            'xG statistics', 'possession metrics', 'pass completion',
            'defensive stats', 'set piece efficiency', 'form trends',
            'head-to-head records', 'Poisson models',
        ],
        'bias_description': '可能过度依赖历史统计数据',
        'analysis_style': '严格基于数据的量化分析，使用统计模型',
        'system_prompt_template': (
            "You are a professional football data analyst. You rely heavily on statistics, "
            "advanced metrics (xG, xGA, PPDA), and historical data patterns. "
            "You avoid emotional reasoning and focus on quantifiable evidence. "
            "Personality: {traits}. Specialty: {focus}."
        ),
    },
    AgentRole.MEDIA: {
        'personality_traits': [
            'narrative-driven', 'trend-aware', 'articulate', 'influential',
            'sometimes sensational', 'well-connected', 'opinionated',
        ],
        'knowledge_focus': [
            'transfer news', 'manager tactics', 'media narratives',
            'public opinion trends', 'press conference insights', 'dressing room dynamics',
        ],
        'bias_description': '倾向于跟随当前媒体叙事和热点话题',
        'analysis_style': '结合新闻报道和公众舆论的综合判断',
        'system_prompt_template': (
            "You are a football media commentator and journalist. "
            "You combine insider knowledge from press conferences with public sentiment analysis. "
            "You're aware of media narratives and how they influence perception. "
            "Personality: {traits}. Coverage area: {focus}."
        ),
    },
    AgentRole.INSIDER: {
        'personality_traits': [
            'well-informed', 'discreet', 'strategic', 'experienced',
            'tactical', 'connected', 'pragmatic',
        ],
        'knowledge_focus': [
            'injury updates', 'training ground reports', 'tactical setups',
            'lineup decisions', 'player fitness', 'manager game plans',
            'contract situations', 'player motivation',
        ],
        'bias_description': '可能过度重视内部信息而忽略统计趋势',
        'analysis_style': '基于内部消息和战术分析的专业判断',
        'system_prompt_template': (
            "You are a football insider with connections to clubs and coaching staff. "
            "You have access to non-public information about team fitness, tactical plans, "
            "and squad morale. Your predictions factor in information others might miss. "
            "Personality: {traits}. Intel focus: {focus}."
        ),
    },
    AgentRole.NEUTRAL: {
        'personality_traits': [
            'balanced', 'open-minded', 'contemplative', 'fair',
            'consensus-seeking', 'moderate', 'pragmatic',
        ],
        'knowledge_focus': [
            'overall match context', 'balanced assessment',
            'cross-referencing sources', 'risk evaluation',
            'probability assessment', 'historical patterns',
        ],
        'bias_description': '倾向于保守预测，可能低估极端结果',
        'analysis_style': '综合多方观点的平衡判断',
        'system_prompt_template': (
            "You are a neutral football observer who weighs all perspectives equally. "
            "You synthesize data, expert opinions, and contextual factors without bias. "
            "You actively seek to understand and reconcile different viewpoints. "
            "Personality: {traits}. Approach: {focus}."
        ),
    },
}


def generate_agent_profiles():
    """生成 50 个 Agent 的完整 profile

    Returns:
        list[dict]: Agent profiles 列表
    """
    profiles = []
    agent_id = 0

    for role, role_config in Config.SWARM_AGENT_ROLES.items():
        role_enum = AgentRole(role.capitalize())
        template = ROLE_TEMPLATES[role_enum]
        count = role_config['count']
        weight = role_config['weight']

        for i in range(count):
            agent_id += 1

            # 随机选择个性特征子集
            n_traits = random.randint(3, 5)
            traits = random.sample(template['personality_traits'], min(n_traits, len(template['personality_traits'])))
            n_focus = random.randint(2, 4)
            focus = random.sample(template['knowledge_focus'], min(n_focus, len(template['knowledge_focus'])))

            # 生成系统提示词
            system_prompt = template['system_prompt_template'].format(
                traits=', '.join(traits),
                focus=', '.join(focus),
            )

            profile = {
                'agent_id': agent_id,
                'name': f"{role.capitalize()}_{i+1:02d}",
                'role': role_enum.value,
                'weight': weight / count,  # 单个 Agent 权重
                'role_weight': weight,  # 角色总权重
                'personality_traits': traits,
                'knowledge_focus': focus,
                'bias_description': template['bias_description'],
                'analysis_style': template['analysis_style'],
                'system_prompt': system_prompt,
            }
            profiles.append(profile)

    logger.info(f"生成 {len(profiles)} 个 Agent profiles")
    return profiles


def generate_match_context_prompt(match_data, features, ml_prediction=None):
    """生成比赛上下文提示词，注入给 Agent

    Args:
        match_data: 比赛基本信息 dict
        features: 特征字典
        ml_prediction: ML 模型预测结果（可选，注入给 Analyst 角色）

    Returns:
        str: 格式化的比赛上下文
    """
    prompt = f"""
=== MATCH CONTEXT ===
{match_data.get('home_team_name', 'Home')} vs {match_data.get('away_team_name', 'Away')}
League: {match_data.get('league_name', 'Unknown')}
Date: {match_data.get('match_date', 'TBD')}
Venue: {match_data.get('venue', 'TBD')}

--- STANDINGS ---
Home position: #{features.get('home_position', '?')} | Points: {features.get('home_points', '?')}
Away position: #{features.get('away_position', '?')} | Points: {features.get('away_points', '?')}

--- RECENT FORM (Last 5) ---
Home: {features.get('home_form5_points', 0)} pts | {features.get('home_form5_goals', 0)} goals scored | {features.get('home_form5_conceded', 0)} conceded
Away: {features.get('away_form5_points', 0)} pts | {features.get('away_form5_goals', 0)} goals scored | {features.get('away_form5_conceded', 0)} conceded

--- HEAD TO HEAD ---
Total meetings: {features.get('h2h_total_matches', 0)}
Home team wins: {features.get('h2h_home_wins', 0)} | Draws: {features.get('h2h_draws', 0)} | Away wins: {features.get('h2h_away_wins', 0)}

--- SQUAD ---
Home injuries: {features.get('home_injuries_count', 0)} | Away injuries: {features.get('away_injuries_count', 0)}
Home formation: {match_data.get('home_formation', 'TBD')} | Away: {match_data.get('away_formation', 'TBD')}

--- WEATHER ---
Condition: {match_data.get('weather_condition', 'Unknown')}
Temperature: {match_data.get('temperature', 'N/A')}°C | Wind: {match_data.get('wind_speed', 'N/A')} km/h

--- REFEREE ---
Referee: {match_data.get('referee_name', 'TBD')}
Avg yellow cards: {features.get('ref_avg_yellows', 'N/A')} | Home win rate: {features.get('ref_home_win_rate', 'N/A')}
"""

    if ml_prediction:
        prompt += f"""
--- ML MODEL PREDICTION (Reference Only) ---
Result: {ml_prediction.get('prediction', 'N/A')}
Probabilities - Home: {ml_prediction.get('probabilities', {}).get('home', 'N/A')} | Draw: {ml_prediction.get('probabilities', {}).get('draw', 'N/A')} | Away: {ml_prediction.get('probabilities', {}).get('away', 'N/A')}
"""

    prompt += """
=== YOUR TASK ===
Based on your role and expertise, predict:
1. Match result (HOME WIN / DRAW / AWAY WIN) with confidence (0-100%)
2. Most likely score
3. Over/Under 2.5 goals
4. Key reasoning (2-3 sentences)

Respond in JSON format:
{"result": "HOME/DRAW/AWAY", "confidence": 75, "score": "2-1", "over_under": "OVER", "reasoning": "..."}
"""
    return prompt
