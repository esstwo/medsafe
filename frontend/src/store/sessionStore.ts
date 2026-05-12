import { create } from 'zustand'
import type { AnalysisResult, Attribution, Medication, SafetyBriefing } from '@/types'

type Step = 'input' | 'confirm' | 'analysis' | 'briefing'

interface SessionState {
  medications: Medication[]
  sessionId: string | null
  currentStep: Step
  isLoading: boolean
  warnings: string[]
  analysisResult: AnalysisResult | null
  briefing: SafetyBriefing | null
  symptoms: string
  symptomAttributions: Attribution[] | null
  setMedications: (meds: Medication[]) => void
  setStep: (step: Step) => void
  setLoading: (v: boolean) => void
  setSessionId: (id: string) => void
  setWarnings: (w: string[]) => void
  setAnalysisResult: (result: AnalysisResult) => void
  setBriefing: (b: SafetyBriefing) => void
  setSymptoms: (s: string) => void
  setSymptomAttributions: (a: Attribution[] | null) => void
}

export const useSessionStore = create<SessionState>((set) => ({
  medications: [],
  sessionId: null,
  currentStep: 'input',
  isLoading: false,
  warnings: [],
  analysisResult: null,
  briefing: null,
  symptoms: '',
  symptomAttributions: null,
  setMedications: (medications) => set({ medications }),
  setStep: (currentStep) => set({ currentStep }),
  setLoading: (isLoading) => set({ isLoading }),
  setSessionId: (sessionId) => set({ sessionId }),
  setWarnings: (warnings) => set({ warnings }),
  setAnalysisResult: (analysisResult) => set({ analysisResult }),
  setBriefing: (briefing) => set({ briefing }),
  setSymptoms: (symptoms) => set({ symptoms }),
  setSymptomAttributions: (symptomAttributions) => set({ symptomAttributions }),
}))
