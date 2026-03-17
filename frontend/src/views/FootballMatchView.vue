<template>
  <div class="match-view">
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH</div>
        <span class="module-badge">足球預測</span>
        <span class="breadcrumb" @click="router.push({ name: 'Football' })">賽事</span>
        <span class="breadcrumb-sep">/</span>
        <span class="breadcrumb-current">賽事 #{{ matchId }}</span>
      </div>
    </header>

    <main class="content" v-if="match">
      <!-- Match Header -->
      <div class="match-hero">
        <div class="hero-team home">
          <img v-if="match.home_crest" :src="match.home_crest" class="hero-crest" />
          <div class="hero-name">{{ match.home_team }}</div>
        </div>
        <div class="hero-center">
          <div class="hero-score" v-if="match.status === 'FINISHED'">
            {{ match.home_score_ft }} - {{ match.away_score_ft }}
          </div>
          <div class="hero-vs" v-else>對</div>
          <div class="hero-info">
            <span>{{ match.league_name }}</span>
            <span>{{ formatDate(match.match_date) }}</span>
            <span v-if="match.matchday">第 {{ match.matchday }} 輪</span>
          </div>
          <div class="hero-status" :class="match.status.toLowerCase()">{{ match.status }}</div>
        </div>
        <div class="hero-team away">
          <img v-if="match.away_crest" :src="match.away_crest" class="hero-crest" />
          <div class="hero-name">{{ match.away_team }}</div>
        </div>
      </div>

      <!-- Prediction Section -->
      <div class="section">
        <div class="section-header">
          <h2>預測</h2>
          <button
            class="action-btn"
            @click="runPrediction"
            :disabled="predicting"
            v-if="match.status === 'SCHEDULED'"
          >
            {{ predicting ? '運行中...' : '運行預測' }}
          </button>
        </div>

        <div v-if="prediction" class="prediction-detail">
          <div class="pred-main">
            <div class="pred-result-big">{{ prediction.predicted_result }}</div>
            <div class="pred-score-big" v-if="prediction.predicted_score">{{ prediction.predicted_score }}</div>
            <div class="pred-confidence">
              {{ (prediction.confidence * 100).toFixed(0) }}% 置信度
              <span class="consensus-badge" :class="prediction.consensus_level">
                {{ prediction.consensus_level === 'high' ? '高共識' : prediction.consensus_level === 'medium' ? '中共識' : '低共識' }}
              </span>
            </div>
          </div>

          <div class="prob-bars">
            <div class="prob-row">
              <span class="prob-label">主場</span>
              <div class="prob-bar-bg">
                <div class="prob-bar home" :style="{ width: (prediction.combined_home_prob * 100) + '%' }"></div>
              </div>
              <span class="prob-pct">{{ (prediction.combined_home_prob * 100).toFixed(1) }}%</span>
            </div>
            <div class="prob-row">
              <span class="prob-label">平局</span>
              <div class="prob-bar-bg">
                <div class="prob-bar draw" :style="{ width: (prediction.combined_draw_prob * 100) + '%' }"></div>
              </div>
              <span class="prob-pct">{{ (prediction.combined_draw_prob * 100).toFixed(1) }}%</span>
            </div>
            <div class="prob-row">
              <span class="prob-label">客場</span>
              <div class="prob-bar-bg">
                <div class="prob-bar away" :style="{ width: (prediction.combined_away_prob * 100) + '%' }"></div>
              </div>
              <span class="prob-pct">{{ (prediction.combined_away_prob * 100).toFixed(1) }}%</span>
            </div>
          </div>

          <div class="pred-layers">
            <div class="layer-card">
              <h4>第一層：機器學習模型</h4>
              <div class="layer-weight">權重：{{ ((prediction.ml_weight || 0.4) * 100).toFixed(0) }}%</div>
            </div>
            <div class="layer-card">
              <h4>第二層：群體智能</h4>
              <div class="layer-weight">權重：{{ ((prediction.agent_weight || 0.6) * 100).toFixed(0) }}%</div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          尚無預測數據。點擊「運行預測」生成預測。
        </div>
      </div>

      <!-- Head to Head -->
      <div class="section">
        <h2>對戰記錄</h2>
        <div class="h2h-list" v-if="h2hMatches.length > 0">
          <div v-for="m in h2hMatches" :key="m.match_date" class="h2h-row">
            <span class="h2h-date">{{ formatShortDate(m.match_date) }}</span>
            <span class="h2h-home" :class="{ winner: m.home_score_ft > m.away_score_ft }">{{ m.home_team }}</span>
            <span class="h2h-score">{{ m.home_score_ft }} - {{ m.away_score_ft }}</span>
            <span class="h2h-away" :class="{ winner: m.away_score_ft > m.home_score_ft }">{{ m.away_team }}</span>
          </div>
        </div>
        <div v-else class="empty-state">暫無對戰記錄數據。</div>
      </div>

      <!-- Match Details -->
      <div class="section details-grid">
        <div class="detail-card" v-if="match.referee_name">
          <h4>裁判</h4>
          <p>{{ match.referee_name }}</p>
        </div>
        <div class="detail-card" v-if="match.weather_condition">
          <h4>天氣</h4>
          <p>{{ match.weather_condition }}, {{ match.temperature }}C</p>
          <p class="detail-sub">濕度：{{ match.humidity }}% | 風速：{{ match.wind_speed }} km/h</p>
        </div>
        <div class="detail-card" v-if="match.home_formation">
          <h4>陣型</h4>
          <p>主場：{{ match.home_formation }} | 客場：{{ match.away_formation }}</p>
        </div>
      </div>
    </main>

    <div v-else class="loading-state">載入賽事詳情中...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMatchDetail, getHeadToHead, getPrediction, triggerSimulation } from '@/api/football'

const props = defineProps({
  matchId: { type: [String, Number], required: true },
})

const router = useRouter()
const match = ref(null)
const prediction = ref(null)
const h2hMatches = ref([])
const predicting = ref(false)

const loadMatch = async () => {
  try {
    const res = await getMatchDetail(props.matchId)
    match.value = res.match
  } catch (e) {
    console.error('Failed to load match:', e)
  }
}

const loadPrediction = async () => {
  try {
    const res = await getPrediction(props.matchId)
    prediction.value = res.prediction || null
  } catch (e) {
    console.error('Failed to load prediction:', e)
  }
}

const loadH2H = async () => {
  try {
    const res = await getHeadToHead(props.matchId)
    h2hMatches.value = res.head_to_head || []
  } catch (e) {
    console.error('Failed to load h2h:', e)
  }
}

const runPrediction = async () => {
  predicting.value = true
  try {
    const res = await triggerSimulation(props.matchId)
    if (res.prediction) {
      await loadPrediction()
    }
  } catch (e) {
    console.error('Prediction failed:', e)
  }
  predicting.value = false
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-TW', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const formatShortDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-TW', { day: '2-digit', month: 'short', year: '2-digit' })
}

onMounted(() => {
  loadMatch()
  loadPrediction()
  loadH2H()
})
</script>

<style scoped>
.match-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
}

.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: #FFF;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  cursor: pointer;
}

.module-badge {
  background: #FF4500;
  color: #FFF;
  padding: 2px 10px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
}

.breadcrumb {
  color: #666;
  font-size: 13px;
  cursor: pointer;
}

.breadcrumb:hover { color: #000; }

.breadcrumb-sep { color: #CCC; font-size: 13px; }

.breadcrumb-current {
  color: #000;
  font-size: 13px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

/* Hero */
.match-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 12px;
  padding: 32px;
  margin-bottom: 24px;
}

.hero-team {
  text-align: center;
  flex: 1;
}

.hero-crest {
  width: 64px;
  height: 64px;
  object-fit: contain;
  margin-bottom: 8px;
}

.hero-name {
  font-weight: 700;
  font-size: 16px;
}

.hero-center {
  text-align: center;
  padding: 0 24px;
}

.hero-score {
  font-family: 'JetBrains Mono', monospace;
  font-size: 36px;
  font-weight: 800;
  letter-spacing: 4px;
}

.hero-vs {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  color: #999;
  letter-spacing: 4px;
}

.hero-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}

.hero-status {
  margin-top: 8px;
  font-size: 11px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  padding: 2px 10px;
  border-radius: 4px;
  display: inline-block;
}

.hero-status.finished { background: #F5F5F5; color: #666; }
.hero-status.scheduled { background: #DBEAFE; color: #1D4ED8; }
.hero-status.in_play { background: #DCFCE7; color: #166534; }

/* Section */
.section {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section h2 {
  font-size: 16px;
  font-weight: 700;
}

.action-btn {
  background: #FF4500;
  color: #FFF;
  border: none;
  padding: 8px 20px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover { background: #E03E00; }
.action-btn:disabled { background: #999; cursor: not-allowed; }

/* Prediction */
.prediction-detail { display: flex; flex-direction: column; gap: 20px; }

.pred-main { text-align: center; }

.pred-result-big {
  font-size: 28px;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
  color: #FF4500;
}

.pred-score-big {
  font-size: 20px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  margin-top: 4px;
}

.pred-confidence {
  font-size: 13px;
  color: #666;
  margin-top: 8px;
}

.consensus-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 8px;
}

.consensus-badge.high { background: #DCFCE7; color: #166534; }
.consensus-badge.medium { background: #FEF9C3; color: #854D0E; }
.consensus-badge.low { background: #FEE2E2; color: #991B1B; }

/* Probability Bars */
.prob-bars { display: flex; flex-direction: column; gap: 8px; }

.prob-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.prob-label {
  width: 50px;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
}

.prob-bar-bg {
  flex: 1;
  height: 8px;
  background: #F5F5F5;
  border-radius: 4px;
  overflow: hidden;
}

.prob-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.prob-bar.home { background: #2563EB; }
.prob-bar.draw { background: #9CA3AF; }
.prob-bar.away { background: #DC2626; }

.prob-pct {
  width: 50px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
}

/* Layers */
.pred-layers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.layer-card {
  padding: 16px;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
}

.layer-card h4 {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}

.layer-weight {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #666;
}

/* H2H */
.h2h-list { display: flex; flex-direction: column; gap: 6px; }

.h2h-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}

.h2h-row:nth-child(even) { background: #FAFAFA; }

.h2h-date {
  color: #999;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  min-width: 80px;
}

.h2h-home, .h2h-away { flex: 1; }
.h2h-away { text-align: right; }
.h2h-home.winner, .h2h-away.winner { font-weight: 700; }

.h2h-score {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  min-width: 40px;
  text-align: center;
}

/* Details Grid */
.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  padding: 0;
  background: none;
  border: none;
}

.detail-card {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 16px;
}

.detail-card h4 {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.detail-card p {
  font-size: 14px;
  font-weight: 600;
}

.detail-sub {
  font-size: 11px !important;
  color: #999 !important;
  font-weight: 400 !important;
  margin-top: 4px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
  font-size: 14px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  color: #666;
  font-size: 14px;
}
</style>
