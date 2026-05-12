import axios from 'axios'
import type { AnalysisResult, Medication } from '@/types'

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
