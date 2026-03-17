<template>
  <div class="football-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH</div>
        <span class="module-badge">足球預測</span>
      </div>
      <nav class="header-nav">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="nav-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <!-- Content -->
    <main class="content">
      <!-- Matches Tab -->
      <section v-if="activeTab === 'matches'" class="tab-content">
        <div class="toolbar">
          <div class="league-filter">
            <button
              v-for="league in leagues"
              :key="league.code"
              class="league-btn"
              :class="{ active: selectedLeague === league.code }"
              @click="selectLeague(league.code)"
            >
              {{ league.code }}
            </button>
            <button class="league-btn" :class="{ active: !selectedLeague }" @click="selectLeague(null)">
              全部
            </button>
          </div>
          <div class="status-filter">
            <select v-model="selectedStatus" @change="loadMatches">
              <option value="">全部狀態</option>
              <option value="SCHEDULED">未開賽</option>
              <option value="FINISHED">已結束</option>
              <option value="IN_PLAY">進行中</option>
            </select>
          </div>
        </div>

        <div class="matches-grid" v-if="!loading">
          <FootballMatchCard
            v-for="match in matches"
            :key="match.id"
            :match="match"
            :prediction="getPredictionForMatch(match)"
            @click="openMatch(match)"
          />
          <div v-if="matches.length === 0" class="empty-state">
            未找到賽事。請先同步數據。
          </div>
        </div>
        <div v-else class="loading-state">載入賽事中...</div>
      </section>

      <!-- Predictions Tab -->
      <section v-if="activeTab === 'predictions'" class="tab-content">
        <div class="toolbar">
          <div class="league-filter">
            <button
              v-for="league in leagues"
              :key="league.code"
              class="league-btn"
              :class="{ active: selectedLeague === league.code }"
              @click="selectLeague(league.code)"
            >
              {{ league.code }}
            </button>
          </div>
          <button class="action-btn" @click="loadUpcomingPredictions" :disabled="predictionsLoading">
            刷新
          </button>
        </div>

        <div class="predictions-list" v-if="!predictionsLoading">
          <div v-for="pred in upcomingPredictions" :key="pred.match_id" class="prediction-row">
            <div class="pred-match">
              <span class="pred-league">{{ pred.league_code }}</span>
              <span class="pred-date">{{ formatDate(pred.match_date) }}</span>
              <span class="pred-teams">{{ pred.home_team }} vs {{ pred.away_team }}</span>
            </div>
            <div class="pred-result" v-if="pred.predicted_result">
              <span class="pred-label">{{ pred.predicted_result }}</span>
              <span class="pred-score" v-if="pred.predicted_score">{{ pred.predicted_score }}</span>
              <span class="pred-conf" v-if="pred.confidence">
                {{ (pred.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="pred-result empty" v-else>
              <button class="simulate-btn" @click="simulateMatch(pred.match_id)">
                預測
              </button>
            </div>
          </div>
          <div v-if="upcomingPredictions.length === 0" class="empty-state">
            未找到即將開始的賽事。
          </div>
        </div>
        <div v-else class="loading-state">載入預測中...</div>
      </section>

      <!-- Standings Tab -->
      <section v-if="activeTab === 'standings'" class="tab-content">
        <div class="toolbar">
          <div class="league-filter">
            <button
              v-for="league in leagues"
              :key="league.code"
              class="league-btn"
              :class="{ active: standingsLeague === league.code }"
              @click="loadStandings(league.code)"
            >
              {{ league.code }}
            </button>
          </div>
        </div>

        <div class="standings-table" v-if="standings.length > 0">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th class="team-col">球隊</th>
                <th>賽</th>
                <th>勝</th>
                <th>平</th>
                <th>負</th>
                <th>進球</th>
                <th>失球</th>
                <th>球差</th>
                <th class="points-col">積分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="team in standings" :key="team.team_name">
                <td class="pos">{{ team.position }}</td>
                <td class="team-col">
                  <img v-if="team.crest_url" :src="team.crest_url" class="table-crest" />
                  {{ team.team_name }}
                </td>
                <td>{{ team.played }}</td>
                <td>{{ team.won }}</td>
                <td>{{ team.drawn }}</td>
                <td>{{ team.lost }}</td>
                <td>{{ team.goals_for }}</td>
                <td>{{ team.goals_against }}</td>
                <td :class="{ positive: team.goal_difference > 0, negative: team.goal_difference < 0 }">
                  {{ team.goal_difference > 0 ? '+' : '' }}{{ team.goal_difference }}
                </td>
                <td class="points-col"><strong>{{ team.points }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state">選擇聯賽以查看排名。</div>
      </section>

      <!-- System Tab -->
      <section v-if="activeTab === 'system'" class="tab-content">
        <div class="system-grid">
          <div class="system-card">
            <h3>數據庫</h3>
            <div class="stat-row" v-for="(count, table) in dataStatus.table_counts" :key="table">
              <span class="stat-label">{{ table }}</span>
              <span class="stat-value">{{ count }}</span>
            </div>
          </div>

          <div class="system-card">
            <h3>機器學習模型</h3>
            <div class="stat-row" v-for="(info, model) in modelStatus" :key="model">
              <span class="stat-label">{{ model }}</span>
              <span class="stat-value status" :class="info.status || (info.file_exists ? 'trained' : 'not_trained')">
                {{ info.status || (info.file_exists ? '已訓練' : '未訓練') }}
              </span>
            </div>
          </div>

          <div class="system-card">
            <h3>數據源</h3>
            <div class="stat-row" v-for="(info, source) in dataStatus.data_sources" :key="source">
              <span class="stat-label">{{ source }}</span>
              <span class="stat-value" :class="{ configured: info.configured }">
                {{ info.configured ? '已配置' : '未配置' }}
              </span>
            </div>
          </div>

          <div class="system-card">
            <h3>操作</h3>
            <button class="action-btn full-width" @click="syncData" :disabled="syncing">
              {{ syncing ? '同步中...' : '完整數據同步' }}
            </button>
            <button class="action-btn full-width" @click="trainModels" :disabled="training" style="margin-top: 8px;">
              {{ training ? '訓練中...' : '訓練機器學習模型' }}
            </button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import FootballMatchCard from '@/components/FootballMatchCard.vue'
import {
  getLeagues, getMatches, getStandings as fetchStandings,
  getUpcomingPredictions as fetchPredictions, triggerSimulation,
  getDataStatus, getModelStatus, triggerSync, triggerTraining
} from '@/api/football'

const router = useRouter()

// Tab state
const tabs = [
  { key: 'matches', label: '賽事' },
  { key: 'predictions', label: '預測' },
  { key: 'standings', label: '排名' },
  { key: 'system', label: '系統' },
]
const activeTab = ref('matches')

// Data
const leagues = ref([])
const matches = ref([])
const upcomingPredictions = ref([])
const standings = ref([])
const dataStatus = ref({ table_counts: {}, data_sources: {} })
const modelStatus = ref({})

// Filters
const selectedLeague = ref(null)
const selectedStatus = ref('')
const standingsLeague = ref('PL')

// Loading states
const loading = ref(false)
const predictionsLoading = ref(false)
const syncing = ref(false)
const training = ref(false)

// Methods
const selectLeague = (code) => {
  selectedLeague.value = code
  loadMatches()
}

const loadMatches = async () => {
  loading.value = true
  try {
    const params = { limit: 50 }
    if (selectedLeague.value) params.league = selectedLeague.value
    if (selectedStatus.value) params.status = selectedStatus.value
    const res = await getMatches(params)
    matches.value = res.matches || []
  } catch (e) {
    console.error('Failed to load matches:', e)
  }
  loading.value = false
}

const loadUpcomingPredictions = async () => {
  predictionsLoading.value = true
  try {
    const params = { days: 14 }
    if (selectedLeague.value) params.league = selectedLeague.value
    const res = await fetchPredictions(params)
    upcomingPredictions.value = res.predictions || []
  } catch (e) {
    console.error('Failed to load predictions:', e)
  }
  predictionsLoading.value = false
}

const loadStandings = async (leagueCode) => {
  standingsLeague.value = leagueCode
  try {
    const res = await fetchStandings(leagueCode)
    standings.value = res.standings || []
  } catch (e) {
    console.error('Failed to load standings:', e)
  }
}

const loadSystemStatus = async () => {
  try {
    const [data, models] = await Promise.all([getDataStatus(), getModelStatus()])
    dataStatus.value = data || { table_counts: {}, data_sources: {} }
    modelStatus.value = models.models || {}
  } catch (e) {
    console.error('Failed to load system status:', e)
  }
}

const openMatch = (match) => {
  router.push({ name: 'FootballMatch', params: { matchId: match.id } })
}

const simulateMatch = async (matchId) => {
  try {
    await triggerSimulation(matchId)
    await loadUpcomingPredictions()
  } catch (e) {
    console.error('Simulation failed:', e)
  }
}

const syncData = async () => {
  syncing.value = true
  try {
    await triggerSync({ source: 'all' })
    await loadSystemStatus()
  } catch (e) {
    console.error('Sync failed:', e)
  }
  syncing.value = false
}

const trainModels = async () => {
  training.value = true
  try {
    await triggerTraining({})
    await loadSystemStatus()
  } catch (e) {
    console.error('Training failed:', e)
  }
  training.value = false
}

const getPredictionForMatch = (match) => {
  return upcomingPredictions.value.find(p => p.match_id === match.id) || null
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-TW', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

// Init
onMounted(async () => {
  try {
    const res = await getLeagues()
    leagues.value = res.leagues || []
  } catch (e) {
    console.error('Failed to load leagues:', e)
  }
  loadMatches()
  loadSystemStatus()
})
</script>

<style scoped>
.football-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  font-family: 'Space Grotesk', 'Noto Sans SC', sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  letter-spacing: 1px;
}

.header-nav {
  display: flex;
  gap: 4px;
}

.nav-btn {
  background: none;
  border: none;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s ease;
  font-family: inherit;
}

.nav-btn:hover {
  background: #F5F5F5;
  color: #000;
}

.nav-btn.active {
  background: #000;
  color: #FFF;
}

/* Content */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.league-filter {
  display: flex;
  gap: 4px;
}

.league-btn {
  background: #FFF;
  border: 1px solid #E5E5E5;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.league-btn:hover {
  border-color: #000;
}

.league-btn.active {
  background: #000;
  color: #FFF;
  border-color: #000;
}

.status-filter select {
  padding: 6px 12px;
  border: 1px solid #E5E5E5;
  border-radius: 4px;
  font-size: 12px;
  font-family: inherit;
  background: #FFF;
  cursor: pointer;
}

.action-btn {
  background: #000;
  color: #FFF;
  border: none;
  padding: 8px 20px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: #333;
}

.action-btn:disabled {
  background: #999;
  cursor: not-allowed;
}

.action-btn.full-width {
  width: 100%;
}

/* Matches Grid */
.matches-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 12px;
}

/* Predictions List */
.predictions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prediction-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.prediction-row:hover {
  border-color: #CCC;
}

.pred-match {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pred-league {
  background: #000;
  color: #FFF;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
}

.pred-date {
  color: #999;
  font-size: 12px;
  min-width: 120px;
}

.pred-teams {
  font-weight: 600;
  font-size: 13px;
}

.pred-result {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pred-label {
  background: #FF4500;
  color: #FFF;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}

.pred-score {
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 700;
}

.pred-conf {
  color: #666;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.simulate-btn {
  background: #FF4500;
  color: #FFF;
  border: none;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.simulate-btn:hover {
  background: #E03E00;
}

/* Standings Table */
.standings-table {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  overflow: hidden;
}

.standings-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.standings-table th {
  background: #000;
  color: #FFF;
  padding: 10px 12px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

.standings-table th.team-col,
.standings-table td.team-col {
  text-align: left;
}

.standings-table td {
  padding: 10px 12px;
  text-align: center;
  border-bottom: 1px solid #F5F5F5;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.standings-table td.team-col {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-crest {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

.standings-table td.pos {
  font-weight: 700;
}

.standings-table td.points-col {
  font-weight: 800;
  font-size: 14px;
}

.positive { color: #16A34A; }
.negative { color: #DC2626; }

/* System Grid */
.system-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.system-card {
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 20px;
}

.system-card h3 {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #F5F5F5;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 12px;
}

.stat-label {
  color: #666;
}

.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
}

.stat-value.configured {
  color: #16A34A;
}

.stat-value.trained {
  color: #16A34A;
}

.stat-value.not_trained {
  color: #999;
}

/* States */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  font-size: 14px;
}

.loading-state {
  text-align: center;
  padding: 60px 20px;
  color: #666;
  font-size: 14px;
}
</style>
