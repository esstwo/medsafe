import { create } from 'zustand'
import type { AnalysisResult, Medication } from '@/types'

type Step = 'input' | 'confirm' | 'analysis' | 'briefing'

interface SessionState {
  medications: Medication[]
  sessionId: string | null
  currentStep: Step
  isLoading: boolean
  warnings: string[]
  analysisResult: AnalysisResult | null
  setMedications: (meds: Medication[]) => void
  setStep: (step: Step) => void
  setLoading: (v: boolean) => void
  setSessionId: (id: string) => void
  setWarnings: (w: string[]) => void
  setAnalysisResult: (result: AnalysisResult) => void
}

export const useSessionStore = create<SessionState>((set) => ({
  medications: [],
  sessionId: null,
  currentStep: 'input',
  isLoading: false,
  warnings: [],
  analysisResult: null,
  setMedications: (medications) => set({ medications }),
  setStep: (currentStep) => set({ currentStep }),
  setLoading: (isLoading) => set({ isLoading }),
  setSessionId: (sessionId) => set({ sessionId }),
  setWarnings: (warnings) => set({ warnings }),
  setAnalysisResult: (analysisResult) => set({ analysisResult }),
}))
