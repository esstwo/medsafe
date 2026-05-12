import axios from 'axios'
import type { AnalysisResult, AddDrugResponse, SafetyBriefing, Medication } from '@/types'

const api = axios.create({ baseURL: '/api' })

export async function generateBriefing(
  analysisResult: AnalysisResult,
  includeFaers = true,
): Promise<SafetyBriefing> {
  const { data } = await api.post<SafetyBriefing>('/briefing/generate', {
    analysis_result: analysisResult,
    include_faers: includeFaers,
  })
  return data
}

export async function addDrug(
  existingMedications: Medication[],
  newDrug: string,
  sessionId: string,
): Promise<AddDrugResponse> {
  const { data } = await api.post<AddDrugResponse>('/analysis/add-drug', {
    existing_medications: existingMedications,
    new_drug: newDrug,
    session_id: sessionId,
  })
  return data
}
