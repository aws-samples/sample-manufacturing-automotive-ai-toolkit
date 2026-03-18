/**
 * scene - Scene Type Definitions
 * 
 * TypeScript interfaces for scene data structures used throughout
 * the application including SceneDetail and related types.
 */
export interface SceneDetail {
  scene_id: string
  timestamp: string
  risk_score: number
  safety_score: number
  tags: string[]
  analysis_summary: string
  anomaly_detected: boolean
  anomaly_status: "CRITICAL" | "DEVIATION" | "NORMAL"
  all_camera_urls: {
    [key: string]: string
  }
  scene_understanding: {
    summary: string
    key_findings: string[]
    behavioral_insights: string[]
  }
  anomaly_analysis: {
    detected: boolean
    tier?: "baseline" | "critical" | "deviation"
    badge_status?: "CRITICAL" | "DEVIATION" | "NORMAL"
    risk_level: string
    description: string
    classification?: {
      anomaly_type?: string
      hil_testing_value?: string
      investment_priority?: string
      training_gap_addressed?: string
    }
    metrics: {
      [key: string]: number
    }
  }
  intelligence_insights: {
    business_impact: string
    training_value: string
    recommendations: string[]
  }
}