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

export interface InteractionSource {
  type: 'drugbank' | 'fda_label' | 'faers'
  id: string
  section: string | null
  url: string | null
}

export interface Interaction {
  drug_a: Medication
  drug_b: Medication
  severity: 'major' | 'moderate' | 'minor' | 'unknown'
  mechanism: string | null
  mechanism_plain: string | null
  clinical_effect: string | null
  evidence_level: 'well-documented' | 'theoretical' | 'case-reports' | null
  source: InteractionSource | null
  confidence: 'high' | 'moderate' | 'low' | null
}

export interface AnalysisResult {
  session_id: string
  medications: Medication[]
  interactions: Interaction[]
}
