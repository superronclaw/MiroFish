/**
 * 足球预测系统 API 模块
 */
import service, { requestWithRetry } from './index'

// ===== 联赛 =====

export const getLeagues = () => {
  return service.get('/api/football/leagues')
}

export const getStandings = (leagueCode) => {
  return service.get(`/api/football/leagues/${leagueCode}/standings`)
}

export const getTeams = (leagueCode) => {
  return service.get(`/api/football/leagues/${leagueCode}/teams`)
}

// ===== 比赛 =====

export const getMatches = (params) => {
  return service.get('/api/football/matches', { params })
}

export const getMatchDetail = (matchId) => {
  return service.get(`/api/football/matches/${matchId}`)
}

export const getHeadToHead = (matchId) => {
  return service.get(`/api/football/matches/${matchId}/head-to-head`)
}

// ===== 预测 =====

export const getPrediction = (matchId) => {
  return service.get(`/api/football/predictions/match/${matchId}`)
}

export const getUpcomingPredictions = (params) => {
  return service.get('/api/football/predictions/upcoming', { params })
}

export const triggerSimulation = (matchId) => {
  return requestWithRetry(
    () => service.post(`/api/football/predictions/match/${matchId}/simulate`),
    2,
    2000
  )
}

// ===== 球员 =====

export const getPlayerStats = (playerId) => {
  return service.get(`/api/football/players/${playerId}/stats`)
}

// ===== 数据管理 =====

export const getDataStatus = () => {
  return service.get('/api/football/data/status')
}

export const triggerSync = (data) => {
  return requestWithRetry(
    () => service.post('/api/football/data/sync', data),
    2,
    1000
  )
}

// ===== 模型 =====

export const getModelStatus = () => {
  return service.get('/api/football/models/status')
}

export const triggerTraining = (data) => {
  return requestWithRetry(
    () => service.post('/api/football/models/train', data),
    1,
    1000
  )
}

// ===== 健康检查 =====

export const getHealth = () => {
  return service.get('/api/football/health')
}

export const getSchedulerStatus = () => {
  return service.get('/api/football/scheduler/status')
}
