<template>
  <div class="match-card" :class="{ 'has-prediction': prediction }" @click="$emit('click', match)">
    <div class="match-header">
      <span class="league-badge">{{ match.league_code }}</span>
      <span class="match-date">{{ formatDate(match.match_date) }}</span>
      <span class="matchday" v-if="match.matchday">第{{ match.matchday }}輪</span>
    </div>

    <div class="match-teams">
      <div class="team home">
        <img v-if="match.home_crest" :src="match.home_crest" :alt="match.home_team" class="team-crest" />
        <span class="team-name">{{ match.home_team || match.home_tla }}</span>
      </div>

      <div class="match-score">
        <template v-if="match.status === 'FINISHED'">
          <span class="score">{{ match.home_score_ft }}</span>
          <span class="score-sep">-</span>
          <span class="score">{{ match.away_score_ft }}</span>
        </template>
        <template v-else>
          <span class="vs">對</span>
        </template>
      </div>

      <div class="team away">
        <span class="team-name">{{ match.away_team || match.away_tla }}</span>
        <img v-if="match.away_crest" :src="match.away_crest" :alt="match.away_team" class="team-crest" />
      </div>
    </div>

    <div class="prediction-bar" v-if="prediction">
      <div class="prob-segment home" :style="{ width: (prediction.combined_home_prob * 100) + '%' }">
        {{ (prediction.combined_home_prob * 100).toFixed(0) }}%
      </div>
      <div class="prob-segment draw" :style="{ width: (prediction.combined_draw_prob * 100) + '%' }">
        {{ (prediction.combined_draw_prob * 100).toFixed(0) }}%
      </div>
      <div class="prob-segment away" :style="{ width: (prediction.combined_away_prob * 100) + '%' }">
        {{ (prediction.combined_away_prob * 100).toFixed(0) }}%
      </div>
    </div>

    <div class="match-footer" v-if="prediction">
      <span class="prediction-label">
        預測：<strong>{{ prediction.predicted_result }}</strong>
      </span>
      <span class="confidence" v-if="prediction.confidence">
        {{ (prediction.confidence * 100).toFixed(0) }}% 置信度
      </span>
      <span class="consensus" v-if="prediction.consensus_level" :class="prediction.consensus_level">
        {{ prediction.consensus_level === 'high' ? '高' : prediction.consensus_level === 'medium' ? '中' : '低' }}
      </span>
    </div>

    <div class="match-meta" v-if="match.referee_name || match.weather_condition">
      <span v-if="match.referee_name" class="meta-item">裁判：{{ match.referee_name }}</span>
      <span v-if="match.weather_condition" class="meta-item">{{ match.weather_condition }} {{ match.temperature }}C</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  match: { type: Object, required: true },
  prediction: { type: Object, default: null },
})

defineEmits(['click'])

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-TW', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.match-card {
  border: 1px solid #EAEAEA;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #FFF;
}

.match-card:hover {
  border-color: #000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.match-card.has-prediction {
  border-left: 3px solid #FF4500;
}

.match-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #666;
}

.league-badge {
  background: #000;
  color: #FFF;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
}

.matchday {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.team {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.team.away {
  justify-content: flex-end;
  text-align: right;
}

.team-crest {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.team-name {
  font-weight: 600;
  font-size: 14px;
}

.match-score {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 60px;
  justify-content: center;
}

.score {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 800;
}

.score-sep {
  color: #999;
  font-size: 16px;
}

.vs {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #999;
  letter-spacing: 2px;
}

.prediction-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.prob-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0;
  min-width: 8%;
  transition: width 0.3s ease;
}

.prob-segment.home {
  background: #2563EB;
}

.prob-segment.draw {
  background: #9CA3AF;
}

.prob-segment.away {
  background: #DC2626;
}

.match-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.prediction-label strong {
  color: #000;
}

.confidence {
  font-family: 'JetBrains Mono', monospace;
}

.consensus {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}

.consensus.high {
  background: #DCFCE7;
  color: #166534;
}

.consensus.medium {
  background: #FEF9C3;
  color: #854D0E;
}

.consensus.low {
  background: #FEE2E2;
  color: #991B1B;
}

.match-meta {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
  color: #999;
}
</style>
