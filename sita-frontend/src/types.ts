export type AnalysisResult = {
  severity?: string;
  category?: string;
  summary?: string;
  root_cause?: string;
  recommended_actions?: string[];
  [k: string]: any;
}
