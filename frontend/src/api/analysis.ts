import axios from 'axios'
import type { AnalysisResult, Attribution, AttributionResponse, Medication } from '@/types'

const api = axios.create({ baseURL: '/api' })

export async function runFullAnalysis(
  medications: Medication[],
  sessionId: string,
): Promise<AnalysisResult> {
  const { data } = await api.post<AnalysisResult>('/analysis/full', {
    medications,
    session_id: sessionId,
  })
  return data
}

export async function attributeSymptoms(
  symptoms: string[],
  medications: Medication[],
  sessionId: string,
): Promise<Attribution[]> {
  const { data } = await api.post<AttributionResponse>('/analysis/symptoms', {
    symptoms,
    medications,
    session_id: sessionId,
  })
  return data.attributions
}
