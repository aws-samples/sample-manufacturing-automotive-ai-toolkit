/**
 * metricDefinitions - Metric Metadata Registry
 * 
 * Provides human-readable titles, descriptions, and calculation explanations
 * for metrics displayed in tooltips throughout the application.
 */
export interface MetricDefinition {
  title: string
  description: string
  calculation?: string
}

const metricDefinitions: Record<string, MetricDefinition> = {
  risk_score: {
    title: "Risk Score",
    description: "Overall safety risk assessment for this driving scenario based on detected anomalies and behavioral patterns.",
    calculation: "Calculated from anomaly severity, environmental complexity, and behavioral risk factors."
  },
  hil_priority: {
    title: "HIL Priority",
    description: "Hardware-in-Loop testing priority assessment indicating the value of this scenario for validation testing.",
    calculation: "Based on scenario uniqueness, safety criticality, and training data gaps."
  },
  anomaly_severity: {
    title: "Anomaly Severity",
    description: "Severity level of detected anomalies in this driving scenario.",
    calculation: "Derived from agent analysis of behavioral patterns and safety-critical events."
  },
  confidence: {
    title: "Confidence",
    description: "Model confidence in the analysis results.",
    calculation: "Based on data quality, sensor coverage, and analysis consistency."
  }
}

export function getMetricDefinition(key: string): MetricDefinition | undefined {
  return metricDefinitions[key]
}
