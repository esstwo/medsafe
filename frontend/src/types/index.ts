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

export interface Citation {
  source_type: string
  source_id: string
  title: string | null
  url: string | null
  section: string | null
}

export interface Attribution {
  symptom: string
  drug_name: string
  rxcui: string | null
  likelihood: 'probable' | 'possible' | 'unlikely' | 'unknown'
  evidence_summary: string
  source: Citation | null
}

export interface FAERSResult {
  drug_name: string
  rxcui: string | null
  total_reports: number
  serious_outcomes: number
  top_reactions: string[]
  data_sparse: boolean
}

export interface SafetyBriefing {
  session_id: string
  generated_at: string
  medications: Medication[]
  interactions: Interaction[]
  symptom_attributions: Attribution[] | null
  adverse_events: FAERSResult[] | null
  provider_questions: string[]
  disclaimer: string
  sources: Citation[]
}

export interface AddDrugResponse {
  new_medication: Medication
  new_interactions: Interaction[]
}

export interface AttributionResponse {
  attributions: Attribution[]
}
