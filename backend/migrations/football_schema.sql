-- =============================================
-- Football Oracle - PostgreSQL Database Schema
-- MiroFish 足球預測系統數據庫設計
-- =============================================

-- 聯賽表
CREATE TABLE IF NOT EXISTS leagues (
    league_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50),
    season VARCHAR(20) NOT NULL,
    api_league_id INTEGER,
    logo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(api_league_id, season)
);

-- 球場表
CREATE TABLE IF NOT EXISTS venues (
    venue_id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    city VARCHAR(100),
    country VARCHAR(50),
    capacity INTEGER,
    altitude_meters INTEGER DEFAULT 0,
    pitch_type VARCHAR(30) DEFAULT 'natural',  -- natural, artificial, hybrid
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    atmosphere_rating DECIMAL(3,1) DEFAULT 5.0,  -- 1-10
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 球隊表
CREATE TABLE IF NOT EXISTS teams (
    team_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(10),
    league_id INTEGER REFERENCES leagues(league_id),
    venue_id INTEGER REFERENCES venues(venue_id),
    api_team_id INTEGER,
    logo_url TEXT,
    founded INTEGER,
    coach_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(api_team_id)
);

-- 球員表
CREATE TABLE IF NOT EXISTS players (
    player_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    team_id INTEGER REFERENCES teams(team_id),
    api_player_id INTEGER,
    position VARCHAR(20),  -- GK, DEF, MID, FWD
    nationality VARCHAR(50),
    date_of_birth DATE,
    market_value BIGINT,  -- 身價（歐元）
    preferred_foot VARCHAR(10),  -- left, right, both
    height_cm INTEGER,
    weight_kg INTEGER,
    shirt_number INTEGER,
    photo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(api_player_id)
);

-- 裁判表
CREATE TABLE IF NOT EXISTS referees (
    referee_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    nationality VARCHAR(50),
    total_matches INTEGER DEFAULT 0,
    avg_yellow_cards DECIMAL(4,2) DEFAULT 0,
    avg_red_cards DECIMAL(4,2) DEFAULT 0,
    avg_fouls DECIMAL(5,2) DEFAULT 0,
    avg_penalties DECIMAL(4,2) DEFAULT 0,
    strictness_rating DECIMAL(3,1) DEFAULT 5.0,  -- 1-10
    controversy_index DECIMAL(4,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 比賽表
CREATE TABLE IF NOT EXISTS matches (
    match_id SERIAL PRIMARY KEY,
    league_id INTEGER REFERENCES leagues(league_id),
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    venue_id INTEGER REFERENCES venues(venue_id),
    referee_id INTEGER REFERENCES referees(referee_id),
    match_date TIMESTAMP NOT NULL,
    matchday INTEGER,
    status VARCHAR(20) DEFAULT 'SCHEDULED',  -- SCHEDULED, LIVE, FINISHED, POSTPONED
    home_score INTEGER,
    away_score INTEGER,
    home_ht_score INTEGER,
    away_ht_score INTEGER,
    api_match_id INTEGER,
    -- 天氣數據
    weather_condition VARCHAR(30),  -- Clear, Rain, Snow, Cloudy, Wind
    temperature_celsius DECIMAL(4,1),
    humidity_percent INTEGER,
    wind_speed_ms DECIMAL(4,1),
    -- 陣型
    home_formation VARCHAR(10),
    away_formation VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(api_match_id)
);

-- 球員比賽統計表
CREATE TABLE IF NOT EXISTS player_match_stats (
    stat_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    is_starter BOOLEAN DEFAULT FALSE,
    minutes_played INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    shots_on_target INTEGER DEFAULT 0,
    passes INTEGER DEFAULT 0,
    pass_accuracy DECIMAL(5,2),
    tackles INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_cards INTEGER DEFAULT 0,
    fouls_committed INTEGER DEFAULT 0,
    fouls_drawn INTEGER DEFAULT 0,
    rating DECIMAL(3,1),  -- 比賽評分 1-10
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, player_id)
);

-- 球隊賽季統計表
CREATE TABLE IF NOT EXISTS team_season_stats (
    stat_id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(team_id),
    league_id INTEGER REFERENCES leagues(league_id),
    season VARCHAR(20) NOT NULL,
    position INTEGER,  -- 排名
    played INTEGER DEFAULT 0,
    won INTEGER DEFAULT 0,
    drawn INTEGER DEFAULT 0,
    lost INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    goal_difference INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    home_won INTEGER DEFAULT 0,
    home_drawn INTEGER DEFAULT 0,
    home_lost INTEGER DEFAULT 0,
    away_won INTEGER DEFAULT 0,
    away_drawn INTEGER DEFAULT 0,
    away_lost INTEGER DEFAULT 0,
    clean_sheets INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, league_id, season)
);

-- 傷病名單表
CREATE TABLE IF NOT EXISTS injuries (
    injury_id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    injury_type VARCHAR(100),
    severity VARCHAR(20),  -- minor, moderate, severe
    start_date DATE,
    expected_return DATE,
    status VARCHAR(20) DEFAULT 'injured',  -- injured, doubtful, recovered
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 裁判比賽記錄表
CREATE TABLE IF NOT EXISTS referee_match_records (
    record_id SERIAL PRIMARY KEY,
    referee_id INTEGER REFERENCES referees(referee_id),
    match_id INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    yellow_cards_given INTEGER DEFAULT 0,
    red_cards_given INTEGER DEFAULT 0,
    penalties_given INTEGER DEFAULT 0,
    fouls_called INTEGER DEFAULT 0,
    home_team_fouls INTEGER DEFAULT 0,
    away_team_fouls INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(referee_id, match_id)
);

-- 預測表
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    prediction_type VARCHAR(50) NOT NULL,  -- full, ml_only, quick
    -- ML 預測結果
    ml_home_win_prob DECIMAL(5,4),
    ml_draw_prob DECIMAL(5,4),
    ml_away_win_prob DECIMAL(5,4),
    ml_predicted_home_goals DECIMAL(4,2),
    ml_predicted_away_goals DECIMAL(4,2),
    ml_over_2_5_prob DECIMAL(5,4),
    ml_confidence DECIMAL(5,4),
    -- 群體智能預測結果
    agent_home_win_prob DECIMAL(5,4),
    agent_draw_prob DECIMAL(5,4),
    agent_away_win_prob DECIMAL(5,4),
    agent_consensus_level VARCHAR(20),  -- low, moderate, high
    agent_total_agents INTEGER,
    agent_voting_details JSONB,
    agent_key_arguments JSONB,
    -- 綜合預測結果
    combined_home_win_prob DECIMAL(5,4),
    combined_draw_prob DECIMAL(5,4),
    combined_away_win_prob DECIMAL(5,4),
    combined_predicted_score VARCHAR(10),  -- e.g. "2-1"
    combined_confidence DECIMAL(5,4),
    prediction_narrative TEXT,
    -- 實際結果（賽後填入）
    actual_result VARCHAR(10),  -- home_win, draw, away_win
    actual_score VARCHAR(10),
    accuracy_score DECIMAL(5,4),
    -- 元數據
    simulation_id VARCHAR(50),
    feature_importance JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 智能體模擬記錄表
CREATE TABLE IF NOT EXISTS simulation_records (
    simulation_id VARCHAR(50) PRIMARY KEY,
    match_id INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    zep_graph_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'CREATED',  -- CREATED, PREPARING, RUNNING, COMPLETED, FAILED
    total_agents INTEGER,
    simulation_rounds INTEGER,
    agent_config JSONB,
    voting_results JSONB,
    discussion_summary TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 索引
-- =============================================

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_match ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_match_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_injuries_player ON injuries(player_id);
CREATE INDEX IF NOT EXISTS idx_injuries_status ON injuries(status);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_type ON predictions(prediction_type);
CREATE INDEX IF NOT EXISTS idx_team_season_stats_team ON team_season_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_simulation_records_match ON simulation_records(match_id);

-- =============================================
-- 觸發器：自動更新 updated_at
-- =============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DO $$
DECLARE
    t text;
BEGIN
    FOR t IN
        SELECT unnest(ARRAY['leagues', 'teams', 'players', 'referees', 'matches', 'injuries', 'predictions'])
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%s_updated_at ON %s;
            CREATE TRIGGER update_%s_updated_at
                BEFORE UPDATE ON %s
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END $$;
