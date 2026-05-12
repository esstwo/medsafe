export interface Medication {
  rxcui: string | null
  name: string
  brand_names: string[]
  input_text: string
  dose: string | null
  frequency: string | null
  type: 'prescription' | 'otc' | 'supplement'
  confidence: number
  active_compounds: string[]
}

export interface NormalizeResponse {
  blocked: boolean
  message: string | null
  medications: Medication[]
  warnings: string[]
}

export interface ConfirmResponse {
  medications: Medication[]
  session_id: string
}
