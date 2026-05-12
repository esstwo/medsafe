import axios from 'axios'
import type { ConfirmResponse, Medication, NormalizeResponse } from '@/types'

const api = axios.create({ baseURL: '/api' })

export async function normalizeMedications(text: string): Promise<NormalizeResponse> {
  const { data } = await api.post<NormalizeResponse>('/medications/normalize', {
    medications: text,
  })
  return data
}

export async function confirmMedications(medications: Medication[]): Promise<ConfirmResponse> {
  const { data } = await api.post<ConfirmResponse>('/medications/confirm', { medications })
  return data
}
